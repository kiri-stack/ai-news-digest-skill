#!/usr/bin/env python3
"""Build an index page for AI daily digest reports."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import pathlib
import re
from dataclasses import dataclass


REPORT_RE = re.compile(r"^ai-daily-digest-(\d{4}-\d{2}-\d{2})\.(md|html)$")
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
TOP_LINE_RE = re.compile(
    r"^##\s+Top Line\s*$\n+(.+?)(?=\n##\s+|\Z)", re.MULTILINE | re.DOTALL
)
TOP_LINE_CN_RE = re.compile(
    r"^##\s+今日要点\s*$\n+(.+?)(?=\n##\s+|\Z)", re.MULTILINE | re.DOTALL
)
ITEM_RE = re.compile(r"^###\s+", re.MULTILINE)


@dataclass
class ReportEntry:
    date: str
    markdown_path: pathlib.Path | None
    html_path: pathlib.Path | None
    title: str
    top_line: str
    item_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing ai-daily-digest report files.",
    )
    parser.add_argument(
        "--output",
        default="reports/index.html",
        help="Output HTML file for the aggregated index page.",
    )
    return parser.parse_args()


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return " ".join(lines)


def read_markdown_metadata(markdown_path: pathlib.Path) -> tuple[str, str, int]:
    text = markdown_path.read_text(encoding="utf-8")
    title_match = TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else markdown_path.stem

    top_line_match = TOP_LINE_CN_RE.search(text) or TOP_LINE_RE.search(text)
    top_line = clean_text(top_line_match.group(1)) if top_line_match else ""
    item_count = len(ITEM_RE.findall(text))
    return title, top_line, item_count


def collect_reports(reports_dir: pathlib.Path) -> list[ReportEntry]:
    grouped: dict[str, dict[str, pathlib.Path]] = {}
    for path in reports_dir.iterdir():
        if not path.is_file():
            continue
        match = REPORT_RE.match(path.name)
        if not match:
            continue
        date_str, ext = match.groups()
        grouped.setdefault(date_str, {})[ext] = path

    entries: list[ReportEntry] = []
    for date_str, files in grouped.items():
        md_path = files.get("md")
        html_path = files.get("html")
        title = f"AI Daily Digest | {date_str}"
        top_line = ""
        item_count = 0
        if md_path:
            title, top_line, item_count = read_markdown_metadata(md_path)
        entries.append(
            ReportEntry(
                date=date_str,
                markdown_path=md_path,
                html_path=html_path,
                title=title,
                top_line=top_line,
                item_count=item_count,
            )
        )

    entries.sort(key=lambda item: item.date, reverse=True)
    return entries


def format_display_date(date_str: str) -> str:
    parsed = dt.date.fromisoformat(date_str)
    return parsed.strftime("%Y-%m-%d")


def render_entry(entry: ReportEntry) -> str:
    title = html.escape(entry.title)
    summary = html.escape(entry.top_line or "No summary available yet.")
    date_text = html.escape(format_display_date(entry.date))
    item_count = entry.item_count if entry.item_count else "N/A"

    links: list[str] = []
    if entry.html_path:
        links.append(
            f'<a class="chip chip-primary" href="{html.escape(entry.html_path.name)}">Open HTML</a>'
        )
    if entry.markdown_path:
        links.append(
            f'<a class="chip" href="{html.escape(entry.markdown_path.name)}">Read Markdown</a>'
        )

    return f"""
      <article class="card">
        <div class="card-top">
          <p class="card-date">{date_text}</p>
          <p class="card-count">{item_count} items</p>
        </div>
        <h2>{title}</h2>
        <p class="card-summary">{summary}</p>
        <div class="card-actions">
          {' '.join(links)}
        </div>
      </article>
    """


def render_page(entries: list[ReportEntry], generated_at: str) -> str:
    cards = "\n".join(render_entry(entry) for entry in entries)
    empty_state = """
      <article class="card empty">
        <h2>No reports yet</h2>
        <p class="card-summary">Add files named ai-daily-digest-YYYY-MM-DD.md or .html and rebuild the index.</p>
      </article>
    """
    cards_html = cards if cards else empty_state

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI Daily Digest Archive</title>
    <style>
      :root {{
        --bg: #f4efe6;
        --paper: rgba(255, 251, 245, 0.9);
        --ink: #191613;
        --muted: #675e55;
        --line: rgba(25, 22, 19, 0.1);
        --accent: #1f6b5d;
        --accent-soft: rgba(31, 107, 93, 0.12);
        --accent-warm: #c55a36;
        --shadow: 0 20px 60px rgba(46, 35, 22, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        color: var(--ink);
        font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(31, 107, 93, 0.14), transparent 26%),
          radial-gradient(circle at top right, rgba(197, 90, 54, 0.16), transparent 30%),
          linear-gradient(180deg, #f4efe6 0%, #f9f5ee 45%, #efe6da 100%);
      }}

      .page {{
        width: min(1160px, calc(100vw - 32px));
        margin: 24px auto 40px;
      }}

      .hero {{
        padding: 32px;
        border-radius: 28px;
        border: 1px solid var(--line);
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
      h2 {{
        margin: 0;
        font-family: "Fraunces", "Noto Serif SC", serif;
        font-weight: 700;
        line-height: 1.06;
      }}

      h1 {{
        margin-top: 16px;
        font-size: clamp(42px, 8vw, 72px);
        max-width: 780px;
      }}

      .lede {{
        max-width: 760px;
        margin: 18px 0 0;
        color: var(--muted);
        font-size: 18px;
        line-height: 1.75;
      }}

      .hero-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 24px;
      }}

      .meta-pill {{
        padding: 10px 14px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.72);
        color: var(--muted);
        font-size: 14px;
      }}

      .archive {{
        margin-top: 22px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 18px;
      }}

      .card {{
        padding: 24px;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: var(--paper);
        box-shadow: var(--shadow);
      }}

      .card-top {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 14px;
        color: var(--muted);
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      .card h2 {{
        font-size: 30px;
      }}

      .card-summary {{
        margin: 14px 0 0;
        color: var(--muted);
        font-size: 16px;
        line-height: 1.75;
      }}

      .card-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 22px;
      }}

      .chip {{
        display: inline-flex;
        align-items: center;
        padding: 10px 14px;
        border-radius: 999px;
        border: 1px solid rgba(25, 22, 19, 0.12);
        color: var(--ink);
        text-decoration: none;
        background: rgba(255, 255, 255, 0.72);
      }}

      .chip-primary {{
        border-color: rgba(31, 107, 93, 0.18);
        background: rgba(31, 107, 93, 0.12);
        color: var(--accent);
      }}

      .footer {{
        margin-top: 20px;
        padding: 20px 24px;
        border-radius: 22px;
        border: 1px solid var(--line);
        background: rgba(255, 251, 245, 0.76);
        color: var(--muted);
        font-size: 14px;
        line-height: 1.7;
      }}

      .empty {{
        grid-column: 1 / -1;
      }}

      @media (max-width: 640px) {{
        .page {{
          width: min(100vw - 20px, 100%);
          margin: 10px auto 24px;
        }}

        .hero,
        .card,
        .footer {{
          padding: 20px;
          border-radius: 20px;
        }}

        .card h2 {{
          font-size: 24px;
        }}

        .card-top {{
          flex-direction: column;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <span class="eyebrow">Archive</span>
        <h1>AI Daily Digest Archive</h1>
        <p class="lede">
          Browse saved AI daily digests by date. Each card links to the full HTML report and its source Markdown file.
        </p>
        <div class="hero-meta">
          <span class="meta-pill">{len(entries)} report(s)</span>
          <span class="meta-pill">Sorted by date descending</span>
          <span class="meta-pill">Generated at {html.escape(generated_at)}</span>
        </div>
      </section>

      <section class="archive">
{cards_html}
      </section>

      <footer class="footer">
        Rebuild this page after adding new reports by running
        <code>python3 ai-news-digest/scripts/build_report_index.py --reports-dir reports --output reports/index.html</code>.
      </footer>
    </main>
  </body>
</html>
"""


def write_index(reports_dir: pathlib.Path, output_path: pathlib.Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    entries = collect_reports(reports_dir)
    generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    html_text = render_page(entries, generated_at)
    output_path.write_text(html_text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    reports_dir = pathlib.Path(args.reports_dir).resolve()
    output_path = pathlib.Path(args.output).resolve()
    write_index(reports_dir, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
