#!/usr/bin/env python3
"""Generate an AI daily digest draft from public RSS feeds, then publish it."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import publish_report


USER_AGENT = "ai-news-digest/1.0"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
RSS_TIMEOUT_SECONDS = 20
DEFAULT_DAYS_BACK = 10
DEFAULT_MAX_ITEMS = 7
SOURCE_NAMES_CN = {
    "Google Blog": "谷歌博客",
    "Microsoft Blog": "微软博客",
    "NVIDIA Blog": "英伟达博客",
    "Meta Newsroom": "Meta 新闻室",
    "TechCrunch AI": "TechCrunch AI",
}


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    priority: int
    ai_only: bool = False


@dataclass
class FeedEntry:
    source: FeedSource
    title: str
    link: str
    published_at: dt.datetime
    summary: str
    categories: list[str]


DEFAULT_FEEDS = [
    FeedSource("Google Blog", "https://blog.google/rss/", 90),
    FeedSource("Microsoft Blog", "https://blogs.microsoft.com/feed/", 88),
    FeedSource("NVIDIA Blog", "https://blogs.nvidia.com/feed/", 86),
    FeedSource("Meta Newsroom", "https://about.fb.com/news/feed/", 82),
    FeedSource("TechCrunch AI", "https://techcrunch.com/tag/artificial-intelligence/feed/", 68, ai_only=True),
]

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "agent",
    "agents",
    "agentic",
    "copilot",
    "gemini",
    "gpt",
    "llm",
    "model",
    "models",
    "robot",
    "robotics",
    "physical ai",
    "omniverse",
    "machine learning",
    "deepmind",
    "openai",
    "anthropic",
    "safety",
    "security",
]

THEME_KEYWORDS = {
    "workflow": ["copilot", "workspace", "docs", "sheets", "slides", "drive", "office", "productivity", "workflow"],
    "safety": ["safety", "security", "secure", "scam", "trust", "prompt injection", "risk"],
    "governance": ["policy", "government", "pentagon", "institute", "regulation", "public"],
    "physical": ["robot", "robotics", "physical ai", "omniverse", "factory", "industrial", "autonomous"],
    "research": ["research", "study", "framework", "benchmark", "scientist", "paper"],
    "health": ["health", "medical", "clinician", "fitbit", "hospital", "drug"],
}

THEME_DESCRIPTIONS = {
    "workflow": "企业工作流入口",
    "safety": "安全与风控",
    "governance": "治理与政策",
    "physical": "具身智能与机器人",
    "research": "研究与评测",
    "health": "AI 医疗与健康",
}

WHY_MATTERS = {
    "workflow": "这说明 AI 竞争正在从模型能力转向工作流入口和实际部署，谁能占住日常生产工具，谁就更容易形成长期使用习惯。",
    "safety": "这说明安全与风控正在从附加项变成部署门槛，企业和平台会越来越关注可审计性、风险控制和默认防护。",
    "governance": "这说明治理和用途边界已经进入主线，模型厂商不只要证明能力，还要证明它们能在真实世界被安全使用。",
    "physical": "这说明 AI 正从数字工作流扩展到真实世界系统，仿真、机器人和工业自动化会成为下一阶段的重要落地方向。",
    "research": "这说明研究与评测框架仍在塑造下一轮能力叙事，新的评测标准和研究结果会很快反馈到产品路线图上。",
    "health": "这说明 AI 正继续进入高价值垂类场景，医疗与健康会是最容易形成长期数据闭环和专业壁垒的领域之一。",
    "general": "这是一条值得跟踪的高信号更新，说明头部公司仍在把 AI 更深地推入产品、平台或行业基础设施。",
}

WATCH_LINES = {
    "workflow": "Microsoft、Google 和 OpenAI 之间的竞争，会继续向“谁控制企业真实工作流”演变。",
    "safety": "Prompt injection、平台风控和默认安全防护，会继续从研究议题变成企业采购门槛。",
    "governance": "政府、监管和大型企业客户会继续推动模型供应商把用途边界写进产品和合同。",
    "physical": "GTC 这类大会释放的信号表明具身智能与机器人正在从概念验证走向更具体的工业部署。",
    "research": "新的评测框架和研究结论，会继续影响市场如何理解“谁在逼近下一代能力边界”。",
    "health": "AI 医疗和健康产品会继续沿着专业助手、训练数据和合规能力三个方向加速。",
}

DETAIL_HINTS = [
    ("scam", "反诈骗防护"),
    ("tax season", "税季安全防护"),
    ("contrail", "航空减排研究"),
    ("air travel", "航空减排研究"),
    ("adoption at work", "职场 AI 采用"),
    ("adopt ai at work", "职场 AI 采用"),
    ("kaggle", "AI 挑战赛平台"),
    ("shopping", "AI 购物"),
    ("commerce", "AI 商业流程"),
    ("health", "医疗健康"),
    ("drug discovery", "药物研发"),
    ("diagnostic", "诊断能力"),
    ("robot", "机器人训练与部署"),
    ("robotics", "机器人训练与部署"),
    ("simulation", "仿真训练"),
    ("support and safety", "平台支持与安全"),
    ("safety", "安全风控"),
    ("vision pro", "空间计算与 XR"),
    ("cloudxr", "空间计算与 XR"),
    ("copilot", "Copilot 更新"),
    ("policy", "政策治理"),
    ("lawmakers", "政策治理"),
]

REWRITE_RULES = [
    (
        "contrail",
        "谷歌发布利用 AI 降低航空气候影响的新研究",
        "谷歌发布新研究，展示如何把 AI 能力嵌入航空工具，以减少飞行造成的气候影响。",
    ),
    (
        "tax season",
        "谷歌发布税季反诈骗 AI 防护更新",
        "谷歌公布了税季反诈骗更新，重点是利用 AI 提升风险识别和用户保护能力。",
    ),
    (
        "adoption at work",
        "谷歌总结提升职场 AI 使用率的五个策略",
        "谷歌结合与研究者的合作结果，总结了推动员工更深度使用 AI 的五个策略。",
    ),
    (
        "kaggle",
        "谷歌扩展 Kaggle AI 挑战赛能力",
        "谷歌发布新的 Kaggle 社区挑战赛能力，进一步扩大 AI 竞赛和开发者生态的参与范围。",
    ),
    (
        "support and safety",
        "Meta 用 AI 强化应用内支持与安全",
        "Meta 发布新的 AI 工具，用于提升应用内支持效率、内容治理和安全保护能力。",
    ),
    (
        "gtc 2026",
        "英伟达 GTC 2026 持续释放 AI 新进展",
        "英伟达在 GTC 2026 期间持续发布 AI 相关产品、演示和基础设施更新。",
    ),
    (
        "roche",
        "罗氏与英伟达扩大 AI 工厂部署，加速药物研发与诊断",
        "罗氏宣布扩大与英伟达相关的 AI 基础设施部署，以加速药物研发、诊断和制造流程。",
    ),
    (
        "build robots",
        "英伟达推进机器人训练与部署工具链",
        "英伟达展示了从仿真到生产的机器人 AI 工具链，强调如何加速机器人训练与落地部署。",
    ),
    (
        "vision pro",
        "英伟达与苹果扩展 Vision Pro 的 XR 与仿真能力",
        "英伟达与苹果推进 Vision Pro 相关能力集成，把图形、仿真和空间计算能力进一步打通。",
    ),
    (
        "shopping",
        "谷歌发布 AI 购物流程更新",
        "谷歌更新了与 AI 购物和商业流程相关的产品能力，继续推动消费场景中的智能化体验。",
    ),
]


class HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format.")
    parser.add_argument("--reports-dir", default="reports", help="Directory that stores report files.")
    parser.add_argument("--days-back", type=int, default=DEFAULT_DAYS_BACK, help="How many recent days to scan.")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, help="Maximum number of digest items.")
    parser.add_argument("--review", action="store_true", help="Apply a stronger Chinese refinement and diversity pass.")
    parser.add_argument("--overwrite-markdown", action="store_true", help="Overwrite an existing markdown report.")
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def keyword_matches(haystack: str, keyword: str) -> bool:
    pattern = re.escape(keyword.lower())
    if keyword[:1].isalnum():
        pattern = r"\b" + pattern
    if keyword[-1:].isalnum():
        pattern = pattern + r"\b"
    return re.search(pattern, haystack) is not None


def strip_html(raw_html: str) -> str:
    stripper = HTMLStripper()
    stripper.feed(raw_html)
    return normalize_whitespace(html.unescape(stripper.get_text()))


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def child_text(element: ET.Element, names: set[str]) -> str:
    for child in element:
        if local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def direct_child_text_exact(element: ET.Element, tag_name: str) -> str:
    for child in element:
        if child.tag == tag_name and child.text:
            return child.text.strip()
    return ""


def child_elements(element: ET.Element, names: set[str]) -> list[ET.Element]:
    return [child for child in element if local_name(child.tag) in names]


def parse_datetime(text: str) -> dt.datetime | None:
    text = text.strip()
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        return parsed.astimezone(LOCAL_TZ)
    except (TypeError, ValueError):
        pass

    iso_candidate = text.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(LOCAL_TZ)
    except ValueError:
        return None


def entry_link(element: ET.Element) -> str:
    direct = child_text(element, {"link"})
    if direct.startswith("http"):
        return direct
    for child in element:
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        if child.text and child.text.strip().startswith("http"):
            return child.text.strip()
    return ""


def parse_feed(xml_bytes: bytes, source: FeedSource) -> list[FeedEntry]:
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []

    candidates: list[ET.Element] = []
    for element in root.iter():
        name = local_name(element.tag)
        if name in {"item", "entry"}:
            candidates.append(element)

    for element in candidates:
        title = child_text(element, {"title"})
        link = entry_link(element)
        summary = direct_child_text_exact(element, "description")
        if not summary:
            summary = direct_child_text_exact(element, "summary")
        if not summary:
            summary = child_text(element, {"description", "summary"})
        if not summary:
            summary = child_text(element, {"encoded"})
        published_text = child_text(element, {"pubDate", "published", "updated"})
        published_at = parse_datetime(published_text) if published_text else None
        categories = []
        for category in child_elements(element, {"category"}):
            term = category.attrib.get("term")
            if term:
                categories.append(term.strip())
            elif category.text:
                categories.append(category.text.strip())

        if not title or not link or published_at is None:
            continue

        entries.append(
            FeedEntry(
                source=source,
                title=normalize_whitespace(html.unescape(title)),
                link=link.strip(),
                published_at=published_at,
                summary=strip_html(summary),
                categories=[normalize_whitespace(cat) for cat in categories if cat.strip()],
            )
        )

    return entries


def fetch_feed(source: FeedSource) -> list[FeedEntry]:
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=RSS_TIMEOUT_SECONDS) as response:
        payload = response.read()
    return parse_feed(payload, source)


def is_ai_relevant(entry: FeedEntry) -> bool:
    if entry.source.ai_only:
        return True
    haystack = " ".join([entry.title, entry.summary, " ".join(entry.categories)]).lower()
    return any(keyword_matches(haystack, keyword) for keyword in AI_KEYWORDS)


def detect_themes(text: str) -> list[str]:
    haystack = text.lower()
    hits: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword_matches(haystack, keyword) for keyword in keywords):
            hits.append(theme)
    return hits or ["general"]


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def score_entry(entry: FeedEntry, report_date: dt.date) -> int:
    days_old = max((report_date - entry.published_at.date()).days, 0)
    themes = detect_themes(f"{entry.title} {entry.summary} {' '.join(entry.categories)}")
    score = entry.source.priority
    score += max(0, 20 - days_old * 3)
    score += 3 if entry.published_at.date() == report_date else 0
    score += min(6, len(themes) * 2)
    return score


def choose_entries(entries: list[FeedEntry], report_date: dt.date, days_back: int, max_items: int) -> list[FeedEntry]:
    window_start = report_date - dt.timedelta(days=days_back - 1)
    candidates = [
        entry
        for entry in entries
        if window_start <= entry.published_at.date() <= report_date and is_ai_relevant(entry)
    ]
    candidates.sort(key=lambda item: (score_entry(item, report_date), item.published_at), reverse=True)

    chosen: list[FeedEntry] = []
    seen_titles: set[str] = set()
    seen_links: set[str] = set()
    per_source_counts: dict[str, int] = {}
    for entry in candidates:
        title_key = normalize_title(entry.title)
        if title_key in seen_titles or entry.link in seen_links:
            continue
        if per_source_counts.get(entry.source.name, 0) >= 3:
            continue
        chosen.append(entry)
        seen_titles.add(title_key)
        seen_links.add(entry.link)
        per_source_counts[entry.source.name] = per_source_counts.get(entry.source.name, 0) + 1
        if len(chosen) >= max_items:
            break
    return chosen


def choose_entries_review(entries: list[FeedEntry], report_date: dt.date, days_back: int, max_items: int) -> list[FeedEntry]:
    window_start = report_date - dt.timedelta(days=days_back - 1)
    remaining = [
        entry
        for entry in entries
        if window_start <= entry.published_at.date() <= report_date and is_ai_relevant(entry)
    ]

    seen_titles: set[str] = set()
    deduped: list[FeedEntry] = []
    for entry in sorted(remaining, key=lambda item: (score_entry(item, report_date), item.published_at), reverse=True):
        title_key = normalize_title(entry.title)
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        deduped.append(entry)

    selected: list[FeedEntry] = []
    source_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}

    while deduped and len(selected) < max_items:
        best_entry: FeedEntry | None = None
        best_value = -10**9
        for entry in deduped:
            theme = choose_primary_theme(entry)
            source_count = source_counts.get(entry.source.name, 0)
            theme_count = theme_counts.get(theme, 0)
            if source_count >= 2:
                continue
            if theme_count >= 3:
                continue
            value = score_entry(entry, report_date)
            value += 10 if source_count == 0 else -6 * source_count
            value += 8 if theme_count == 0 else -4 * theme_count
            if entry.published_at.date() == report_date:
                value += 4
            if best_entry is None or value > best_value:
                best_entry = entry
                best_value = value

        if best_entry is None:
            break

        selected.append(best_entry)
        deduped.remove(best_entry)
        theme = choose_primary_theme(best_entry)
        source_counts[best_entry.source.name] = source_counts.get(best_entry.source.name, 0) + 1
        theme_counts[theme] = theme_counts.get(theme, 0) + 1

    return selected


def summarize_summary(text: str, limit: int = 180) -> str:
    text = normalize_whitespace(text)
    if not text:
        return "官方摘要未提供更多细节，请查看原文。"
    if len(text) <= limit:
        return text
    truncated = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{truncated}..."


def choose_primary_theme(entry: FeedEntry) -> str:
    themes = detect_themes(f"{entry.title} {entry.summary} {' '.join(entry.categories)}")
    return themes[0]


def source_name_cn(source_name: str) -> str:
    return SOURCE_NAMES_CN.get(source_name, source_name)


def detect_detail(text: str) -> str:
    haystack = text.lower()
    for keyword, phrase in DETAIL_HINTS:
        if keyword_matches(haystack, keyword):
            return phrase
    return ""


def rewrite_rule(text: str) -> tuple[str, str] | None:
    haystack = text.lower()
    for keyword, headline, what in REWRITE_RULES:
        if keyword_matches(haystack, keyword):
            return headline, what
    return None


def chinese_headline(entry: FeedEntry) -> str:
    rewritten = rewrite_rule(f"{entry.title} {entry.summary}")
    if rewritten:
        return rewritten[0]

    source_cn = source_name_cn(entry.source.name)
    theme = choose_primary_theme(entry)
    detail = detect_detail(f"{entry.title} {entry.summary}")
    if detail:
        if theme == "research":
            return f"{source_cn}发布{detail}相关研究更新"
        if theme == "safety":
            return f"{source_cn}发布{detail}相关 AI 安全更新"
        if theme == "physical":
            return f"{source_cn}发布{detail}相关 AI 更新"
        if theme == "workflow":
            return f"{source_cn}发布{detail}相关产品更新"
        if theme == "health":
            return f"{source_cn}发布{detail}相关 AI 更新"
        return f"{source_cn}发布{detail}相关 AI 更新"

    if theme == "research":
        return f"{source_cn}发布 AI 研究更新"
    if theme == "safety":
        return f"{source_cn}发布 AI 安全与风控更新"
    if theme == "physical":
        return f"{source_cn}发布具身智能与机器人更新"
    if theme == "workflow":
        return f"{source_cn}发布 AI 工作流更新"
    if theme == "health":
        return f"{source_cn}发布 AI 医疗与健康更新"
    if theme == "governance":
        return f"{source_cn}发布 AI 治理与政策更新"
    return f"{source_cn}发布 AI 相关更新"


def chinese_what_happened(entry: FeedEntry) -> str:
    rewritten = rewrite_rule(f"{entry.title} {entry.summary}")
    if rewritten:
        return rewritten[1]

    source_cn = source_name_cn(entry.source.name)
    theme = choose_primary_theme(entry)
    detail = detect_detail(f"{entry.title} {entry.summary}")
    if detail and theme == "research":
        return f"{source_cn}发布了一项与{detail}相关的 AI 研究更新，重点是展示最新研究结果与潜在应用方向。"
    if detail and theme == "safety":
        return f"{source_cn}发布了一项与{detail}相关的 AI 更新，重点放在安全防护、风险识别或平台治理能力。"
    if detail and theme == "workflow":
        return f"{source_cn}发布了一项与{detail}相关的 AI 更新，重点是提升真实工作流中的使用效率与落地能力。"
    if detail and theme == "physical":
        return f"{source_cn}发布了一项与{detail}相关的更新，重点是把 AI 能力推进到仿真、机器人或工业部署场景。"
    if detail and theme == "health":
        return f"{source_cn}发布了一项与{detail}相关的 AI 更新，重点围绕医疗、健康或生命科学应用。"
    return f"{source_cn}发布了一项新的 AI 相关更新，详情可查看原始来源。"


def build_top_line(entries: list[FeedEntry], report_date: dt.date) -> str:
    same_day = [entry for entry in entries if entry.published_at.date() == report_date]
    min_date = min(entry.published_at.date() for entry in entries)
    max_date = max(entry.published_at.date() for entry in entries)

    theme_counts: dict[str, int] = {}
    for entry in entries:
        for theme in detect_themes(f"{entry.title} {entry.summary} {' '.join(entry.categories)}"):
            if theme == "general":
                continue
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    top_themes = sorted(theme_counts, key=theme_counts.get, reverse=True)[:3]
    theme_text = "、".join(THEME_DESCRIPTIONS[theme] for theme in top_themes) if top_themes else "产品发布与行业落地"

    if not same_day:
        return (
            f"截至 {report_date.isoformat()} 北京时间，头部 AI 公司没有出现很多“今天刚发”的重磅新公告；"
            f"最近一波高信号更新主要集中在 {min_date.isoformat()} 到 {max_date.isoformat()}，"
            f"主线集中在{theme_text}。"
        )

    return (
        f"截至 {report_date.isoformat()} 北京时间，今天能核实到 {len(same_day)} 条较高信号的 AI 更新；"
        f"本轮主线集中在 {theme_text}。"
    )


def build_market_watch(entries: list[FeedEntry]) -> list[str]:
    themes = [choose_primary_theme(entry) for entry in entries]
    bullets: list[str] = []
    if "workflow" in themes:
        bullets.append("模型与产品：近期高信号更新继续集中在办公协作、企业助手和默认工作流入口。")
    else:
        bullets.append("模型与产品：最近的增量更多来自产品化和落地，而不是新的超大模型重磅发布。")

    if "safety" in themes or "governance" in themes:
        bullets.append("政策与安全：安全、治理和用途边界持续升温，已经从附加议题进入主线。")
    else:
        bullets.append("政策与安全：本轮信号更偏产品与平台整合，政策面增量相对有限。")

    if "physical" in themes:
        bullets.append("具身智能：机器人、仿真和工业系统相关动作明显增多，具身智能继续升温。")
    else:
        bullets.append("平台与接口：头部公司仍在争夺平台入口，重点是把 AI 深嵌进现有软件和基础设施。")

    bullets.append("来源结构：本日报草稿基于公开 RSS 和官方博客，适合快速初筛，重大结论仍建议二次核验。")
    return bullets


def build_watch_next(entries: list[FeedEntry]) -> list[str]:
    seen: list[str] = []
    for entry in entries:
        theme = choose_primary_theme(entry)
        line = WATCH_LINES.get(theme)
        if line and line not in seen:
            seen.append(line)
        if len(seen) >= 3:
            break
    if len(seen) < 3:
        seen.append("头部厂商会继续把 AI 叙事从模型能力转向产品整合、治理和真实部署。")
    return seen[:3]


def render_markdown(entries: list[FeedEntry], report_date: dt.date, days_back: int) -> str:
    generated_at = dt.datetime.now().astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z (UTC%z)")
    window_start = report_date - dt.timedelta(days=days_back - 1)
    lines = [
        f"# AI 日报 | {report_date.isoformat()}",
        "",
        f"> 覆盖范围：{window_start.isoformat()} 至 {report_date.isoformat()}",
        f"> 生成时间：{generated_at}",
        "",
        "## 今日要点",
        "",
        build_top_line(entries, report_date),
        "",
        "## 重点动态",
        "",
    ]

    for index, entry in enumerate(entries, start=1):
        theme = choose_primary_theme(entry)
        summary = chinese_what_happened(entry)
        why = WHY_MATTERS.get(theme, WHY_MATTERS["general"])
        source_cn = source_name_cn(entry.source.name)
        lines.extend(
            [
                f"### {index}. {chinese_headline(entry)}",
                "",
                f"- 日期：{entry.published_at.date().isoformat()}",
                f"- 发生了什么：{summary}",
                f"- 为什么重要：{why}",
                f"- 来源：[{source_cn}]({entry.link})",
                "",
            ]
        )

    lines.extend(["## 行业观察", ""])
    for bullet in build_market_watch(entries):
        lines.append(f"- {bullet}")

    lines.extend(["", "## 接下来值得关注", ""])
    for bullet in build_watch_next(entries):
        lines.append(f"- {bullet}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report_date = dt.date.fromisoformat(args.date)
    reports_dir = pathlib.Path(args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = publish_report.default_markdown(args.date, reports_dir)
    html_path = publish_report.default_html(args.date, reports_dir)
    index_path = publish_report.default_index(reports_dir)

    if markdown_path.exists() and not args.overwrite_markdown:
        raise SystemExit(f"Markdown report already exists: {markdown_path}")

    entries: list[FeedEntry] = []
    for source in DEFAULT_FEEDS:
        try:
            entries.extend(fetch_feed(source))
        except Exception as exc:  # pragma: no cover - network failures are non-deterministic
            print(f"warning: failed to fetch {source.name}: {exc}", file=sys.stderr)

    chooser = choose_entries_review if args.review else choose_entries
    chosen = chooser(entries, report_date, args.days_back, args.max_items)
    if not chosen:
        raise SystemExit("No AI-relevant entries found in the configured feeds.")

    markdown_path.write_text(render_markdown(chosen, report_date, args.days_back), encoding="utf-8")
    publish_report.publish(markdown_path, html_path, index_path, reports_dir)
    print(markdown_path)
    print(html_path)
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
