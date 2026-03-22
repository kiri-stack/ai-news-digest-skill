#!/usr/bin/env python3
"""Publish an AI daily digest markdown report to HTML and update the archive."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_report_index


TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
SECTION_RE_TEMPLATE = r"^##\s+{heading}\s*$\n+(.+?)(?=\n##\s+|\Z)"
ITEM_HEADING_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"^- ([A-Za-z\u4e00-\u9fff ]+)[：:]\s*(.+)$", re.MULTILINE)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

SECTION_ALIASES = {
    "top_line": ["今日要点", "Top Line"],
    "developments": ["重点动态", "Key Developments"],
    "market_watch": ["行业观察", "Market Watch"],
    "watch_next": ["接下来值得关注", "Why Watch Next"],
}

FIELD_ALIASES = {
    "date": ["日期", "Date"],
    "what": ["发生了什么", "What happened"],
    "why": ["为什么重要", "Why it matters"],
    "sources": ["来源", "Sources"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        required=True,
        help="Report date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory that stores report files.",
    )
    parser.add_argument(
        "--markdown",
        help="Optional markdown path. Defaults to reports/ai-daily-digest-YYYY-MM-DD.md.",
    )
    parser.add_argument(
        "--html",
        help="Optional html path. Defaults to reports/ai-daily-digest-YYYY-MM-DD.html.",
    )
    parser.add_argument(
        "--index",
        help="Optional archive index path. Defaults to reports/index.html.",
    )
    parser.add_argument(
        "--init-markdown",
        action="store_true",
        help="Create a markdown template when the source markdown file does not exist.",
    )
    return parser.parse_args()


def default_markdown(date_str: str, reports_dir: pathlib.Path) -> pathlib.Path:
    return reports_dir / f"ai-daily-digest-{date_str}.md"


def default_html(date_str: str, reports_dir: pathlib.Path) -> pathlib.Path:
    return reports_dir / f"ai-daily-digest-{date_str}.html"


def default_index(reports_dir: pathlib.Path) -> pathlib.Path:
    return reports_dir / "index.html"


def ensure_markdown_template(markdown_path: pathlib.Path, date_str: str) -> None:
    timestamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z (UTC%z)")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        (
            f"# AI 日报 | {date_str}\n\n"
            f"> 覆盖范围：{date_str} 至 {date_str}\n"
            f"> 生成时间：{timestamp}\n\n"
            "## 今日要点\n\n"
            "用一句中文概括最重要的变化。\n\n"
            "## 重点动态\n\n"
            "### 1. <中文标题>\n\n"
            f"- 日期：{date_str}\n"
            "- 发生了什么：...\n"
            "- 为什么重要：...\n"
            "- 来源：[来源 1](https://...)\n\n"
            "## 行业观察\n\n"
            "- 模型与产品：...\n"
            "- 平台与接口：...\n"
            "- 政策与安全：...\n"
            "- 融资与合作：...\n\n"
            "## 接下来值得关注\n\n"
            "- ...\n"
        ),
        encoding="utf-8",
    )


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(
        SECTION_RE_TEMPLATE.format(heading=re.escape(heading)),
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_section_aliases(text: str, aliases: list[str]) -> str:
    for alias in aliases:
        section = extract_section(text, alias)
        if section:
            return section
    return ""


def parse_links(text: str) -> list[tuple[str, str]]:
    return [(label.strip(), url.strip()) for label, url in LINK_RE.findall(text)]


def render_inline_markdown(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in LINK_RE.finditer(text):
        parts.append(html.escape(text[last : match.start()]))
        label, url = match.groups()
        parts.append(f'<a href="{html.escape(url)}">{html.escape(label)}</a>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def parse_list_section(section_text: str) -> list[str]:
    items: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def parse_items(section_text: str) -> list[dict[str, object]]:
    matches = list(ITEM_HEADING_RE.finditer(section_text))
    items: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
        body = section_text[start:end].strip()
        raw_fields = {key.strip(): value.strip() for key, value in FIELD_RE.findall(body)}
        fields: dict[str, str] = {}
        for canonical, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in raw_fields:
                    fields[canonical] = raw_fields[alias]
                    break
        sources = parse_links(fields.get("sources", ""))
        items.append(
            {
                "title": match.group(1).strip(),
                "date": fields.get("date", ""),
                "what": fields.get("what", ""),
                "why": fields.get("why", ""),
                "sources": sources,
            }
        )
    return items


def parse_report(markdown_path: pathlib.Path) -> dict[str, object]:
    text = markdown_path.read_text(encoding="utf-8")
    title_match = TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else markdown_path.stem

    covered_range = ""
    generated_at = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("> Covered range:"):
            covered_range = stripped.removeprefix("> Covered range:").strip()
        elif stripped.startswith("> 覆盖范围："):
            covered_range = stripped.removeprefix("> 覆盖范围：").strip()
        elif stripped.startswith("> Generated at:"):
            generated_at = stripped.removeprefix("> Generated at:").strip()
        elif stripped.startswith("> 生成时间："):
            generated_at = stripped.removeprefix("> 生成时间：").strip()

    top_line = extract_section_aliases(text, SECTION_ALIASES["top_line"])
    developments = extract_section_aliases(text, SECTION_ALIASES["developments"])
    market_watch = extract_section_aliases(text, SECTION_ALIASES["market_watch"])
    why_watch_next = extract_section_aliases(text, SECTION_ALIASES["watch_next"])

    return {
        "title": title,
        "top_line": top_line,
        "covered_range": covered_range,
        "generated_at": generated_at,
        "items": parse_items(developments),
        "market_watch": parse_list_section(market_watch),
        "why_watch_next": parse_list_section(why_watch_next),
    }


def render_sources(sources: list[tuple[str, str]]) -> str:
    links = [
        f'<a href="{html.escape(url)}">{html.escape(label)}</a>'
        for label, url in sources
    ]
    return " ".join(links)


def render_bullets(items: list[str]) -> str:
    if not items:
        return "<p class=\"empty-copy\">No items.</p>"
    bullets = "\n".join(f"<li>{render_inline_markdown(item)}</li>" for item in items)
    return f"<ul>{bullets}</ul>"


def render_html(report: dict[str, object]) -> str:
    items = report["items"]
    if not isinstance(items, list):
        items = []

    stories_html = []
    nav_links = []
    for item in items:
        story_index = len(stories_html) + 1
        title = html.escape(str(item.get("title", "")))
        date_text = render_inline_markdown(str(item.get("date", "")))
        what_text = render_inline_markdown(str(item.get("what", "")))
        why_text = render_inline_markdown(str(item.get("why", "")))
        sources_html = render_sources(item.get("sources", []))
        story_id = f"story-{story_index}"
        nav_links.append(
            f"""
            <a class="story-nav-link" href="#{story_id}">
              <span class="story-nav-index">{story_index:02d}</span>
              <span class="story-nav-text">{title}</span>
            </a>
            """
        )
        stories_html.append(
            f"""
            <article class="story" id="{story_id}">
              <h3>{title}</h3>
              <div class="story-grid">
                <div class="story-row">
                  <div class="story-label">日期</div>
                  <div class="story-value">{date_text}</div>
                </div>
                <div class="story-row">
                  <div class="story-label">发生了什么</div>
                  <div class="story-value">{what_text}</div>
                </div>
                <div class="story-row">
                  <div class="story-label">为什么重要</div>
                  <div class="story-value">{why_text}</div>
                </div>
                <div class="story-row">
                  <div class="story-label">来源</div>
                  <div class="story-value source-list">{sources_html}</div>
                </div>
              </div>
            </article>
            """
        )

    story_count = len(items)
    title = html.escape(str(report["title"]))
    top_line = render_inline_markdown(str(report["top_line"]))
    covered_range = html.escape(str(report["covered_range"]))
    generated_at = html.escape(str(report["generated_at"]))
    market_watch = render_bullets(list(report["market_watch"]))
    why_watch_next = render_bullets(list(report["why_watch_next"]))
    nav_html = "".join(nav_links)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        --bg: #f2eee6;
        --paper: rgba(255, 251, 245, 0.93);
        --ink: #191714;
        --muted: #68615a;
        --line: rgba(25, 23, 20, 0.1);
        --accent: #7c3f00;
        --accent-soft: rgba(124, 63, 0, 0.12);
        --accent-cool: #0c6668;
        --card: rgba(255, 255, 255, 0.74);
        --shadow: 0 20px 60px rgba(55, 37, 21, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        color: var(--ink);
        font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(124, 63, 0, 0.14), transparent 28%),
          radial-gradient(circle at top right, rgba(12, 102, 104, 0.14), transparent 30%),
          linear-gradient(180deg, #f2eee6 0%, #f9f4ec 46%, #ede3d7 100%);
      }}

      .shell {{
        width: min(1140px, calc(100vw - 32px));
        margin: 24px auto 40px;
      }}

      .hero {{
        padding: 32px;
        border: 1px solid var(--line);
        border-radius: 28px;
        background: var(--paper);
        box-shadow: var(--shadow);
      }}

      .eyebrow {{
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      h1,
      h2,
      h3 {{
        margin: 0;
        font-family: "Fraunces", "Noto Serif SC", serif;
        font-weight: 700;
        line-height: 1.06;
      }}

      h1 {{
        margin-top: 16px;
        font-size: clamp(42px, 8vw, 72px);
        max-width: 800px;
      }}

      .lede {{
        max-width: 780px;
        margin-top: 18px;
        color: var(--muted);
        font-size: 18px;
        line-height: 1.75;
      }}

      .meta {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin-top: 28px;
      }}

      .meta-card {{
        position: relative;
        overflow: hidden;
        padding: 18px 18px 20px;
        border: 1px solid var(--line);
        border-radius: 22px;
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(250, 244, 236, 0.94));
      }}

      .meta-card::after {{
        content: "";
        position: absolute;
        inset: auto -28px -28px auto;
        width: 88px;
        height: 88px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(12, 102, 104, 0.12), transparent 70%);
      }}

      .meta-label {{
        display: block;
        margin-bottom: 10px;
        color: var(--muted);
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      .meta-value {{
        position: relative;
        z-index: 1;
        font-size: clamp(22px, 3vw, 32px);
        font-weight: 700;
        line-height: 1.15;
        font-family: "Fraunces", "Noto Serif SC", serif;
      }}

      .meta-note {{
        position: relative;
        z-index: 1;
        margin-top: 10px;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.6;
      }}

      .content-stack {{
        display: grid;
        gap: 22px;
        margin-top: 22px;
      }}

      .panel,
      .story,
      .insight-card {{
        border: 1px solid var(--line);
        border-radius: 24px;
        background: var(--paper);
        box-shadow: var(--shadow);
      }}

      .panel {{
        padding: 28px;
      }}

      .section-kicker {{
        margin-bottom: 14px;
        color: var(--accent-cool);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      .panel-title {{
        font-size: 30px;
        margin-bottom: 18px;
      }}

      .stories {{
        display: grid;
        gap: 16px;
      }}

      .story-nav-panel {{
        padding: 24px 28px;
      }}

      .story-nav-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }}

      .story-nav-link {{
        display: grid;
        grid-template-columns: 44px 1fr;
        gap: 12px;
        align-items: center;
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid rgba(25, 23, 20, 0.08);
        background: rgba(255, 255, 255, 0.68);
        text-decoration: none;
        color: var(--ink);
        transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
      }}

      .story-nav-link:hover {{
        transform: translateY(-1px);
        border-color: rgba(12, 102, 104, 0.25);
        box-shadow: 0 12px 28px rgba(55, 37, 21, 0.08);
        text-decoration: none;
      }}

      .story-nav-index {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 14px;
        background: rgba(12, 102, 104, 0.1);
        color: var(--accent-cool);
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 0.04em;
      }}

      .story-nav-text {{
        font-size: 15px;
        line-height: 1.55;
      }}

      .story {{
        scroll-margin-top: 24px;
        padding: 24px;
        background: var(--card);
      }}

      .story h3 {{
        font-size: 28px;
        margin-bottom: 12px;
      }}

      .story-grid {{
        display: grid;
        gap: 12px;
      }}

      .story-row {{
        display: grid;
        grid-template-columns: 140px 1fr;
        gap: 12px;
        align-items: start;
      }}

      .story-label {{
        color: var(--muted);
        font-size: 13px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding-top: 3px;
      }}

      .story-value {{
        font-size: 16px;
        line-height: 1.75;
      }}

      a {{
        color: var(--accent-cool);
        text-decoration: none;
      }}

      a:hover {{
        text-decoration: underline;
      }}

      .source-list {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}

      .source-list a {{
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid rgba(12, 102, 104, 0.18);
        background: rgba(12, 102, 104, 0.08);
        font-size: 14px;
      }}

      .insights-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
      }}

      .insight-card {{
        padding: 24px;
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 248, 240, 0.88));
      }}

      .insight-card h2 {{
        font-size: 26px;
        margin-bottom: 14px;
      }}

      .insight-card ul {{
        display: grid;
        gap: 10px;
      }}

      .insight-card li {{
        padding: 14px 16px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(25, 23, 20, 0.08);
      }}

      ul {{
        margin: 0;
        padding-left: 18px;
        line-height: 1.8;
      }}

      li + li {{
        margin-top: 8px;
      }}

      .empty-copy {{
        margin: 0;
        color: var(--muted);
      }}

      .footer {{
        margin-top: 20px;
        padding: 22px 24px;
        border: 1px solid var(--line);
        border-radius: 22px;
        background: rgba(255, 252, 246, 0.76);
        color: var(--muted);
        font-size: 14px;
        line-height: 1.7;
      }}

      @media (max-width: 920px) {{
        .meta {{
          grid-template-columns: 1fr;
        }}

        .story-nav-grid {{
          grid-template-columns: 1fr;
        }}

        .insights-grid {{
          grid-template-columns: 1fr;
        }}
      }}

      @media (max-width: 640px) {{
        .shell {{
          width: min(100vw - 20px, 100%);
          margin: 10px auto 24px;
        }}

        .hero,
        .panel,
        .story-nav-panel,
        .story,
        .insight-card {{
          padding: 20px;
          border-radius: 20px;
        }}

        .story h3 {{
          font-size: 24px;
        }}

        .panel-title {{
          font-size: 24px;
        }}

        .story-row {{
          grid-template-columns: 1fr;
          gap: 4px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <span class="eyebrow">AI 日报</span>
        <h1>{title}</h1>
        <p class="lede">{top_line}</p>
        <div class="meta">
          <div class="meta-card">
            <span class="meta-label">覆盖范围</span>
            <span class="meta-value">{covered_range}</span>
            <div class="meta-note">按精确日期展示统计窗口，避免把旧闻误判成今日动态。</div>
          </div>
          <div class="meta-card">
            <span class="meta-label">生成时间</span>
            <span class="meta-value">{generated_at}</span>
            <div class="meta-note">页面内容与 Markdown 日报同步渲染，时间戳可直接用于归档。</div>
          </div>
          <div class="meta-card">
            <span class="meta-label">条目数量</span>
            <span class="meta-value">{story_count} 条重点动态</span>
            <div class="meta-note">聚焦高信号条目，优先展示模型、平台、安全和产业落地相关变化。</div>
          </div>
        </div>
      </section>

      <section class="content-stack">
        <section class="panel story-nav-panel">
          <div class="section-kicker">快速浏览</div>
          <h2 class="panel-title">按编号快速跳转</h2>
          <div class="story-nav-grid">
            {nav_html}
          </div>
        </section>

        <div class="panel">
          <div class="section-kicker">重点动态</div>
          <h2 class="panel-title">今天值得关注的 AI 进展</h2>
          <div class="stories">
            {''.join(stories_html)}
          </div>
        </div>

        <div class="insights-grid">
          <section class="insight-card">
            <div class="section-kicker">行业观察</div>
            <h2>行业观察</h2>
            {market_watch}
          </section>

          <section class="insight-card">
            <div class="section-kicker">接下来值得关注</div>
            <h2>接下来值得关注</h2>
            {why_watch_next}
          </section>
        </div>
      </section>

      <footer class="footer">
        本页由同名 Markdown 日报渲染生成，并保持相同的来源结构与中文输出。
      </footer>
    </main>
  </body>
</html>
"""


def publish(markdown_path: pathlib.Path, html_path: pathlib.Path, index_path: pathlib.Path, reports_dir: pathlib.Path) -> None:
    report = parse_report(markdown_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(report), encoding="utf-8")
    build_report_index.write_index(reports_dir, index_path)


def main() -> int:
    args = parse_args()
    reports_dir = pathlib.Path(args.reports_dir).resolve()
    markdown_path = pathlib.Path(args.markdown).resolve() if args.markdown else default_markdown(args.date, reports_dir)
    html_path = pathlib.Path(args.html).resolve() if args.html else default_html(args.date, reports_dir)
    index_path = pathlib.Path(args.index).resolve() if args.index else default_index(reports_dir)

    if not markdown_path.exists():
        if not args.init_markdown:
            raise SystemExit(f"Markdown report not found: {markdown_path}")
        ensure_markdown_template(markdown_path, args.date)

    publish(markdown_path, html_path, index_path, reports_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
