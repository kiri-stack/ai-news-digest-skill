---
name: ai-news-digest
description: Gather, verify, and summarize the latest AI news with source links and exact dates. Use when the user asks for today's, latest, recent, or weekly AI updates; AI daily digests; model launches; product announcements; funding; regulation; safety developments; or company-specific AI news where freshness and citations matter.
---

# AI News Digest

## Overview

Use this skill to produce a fast, source-backed AI news briefing. Treat freshness as mandatory: verify exact dates, cite every item, and prefer primary sources over commentary.
Unless the user explicitly asks otherwise, output everything in Chinese, including headings, summaries, analysis, and generated headlines.

Read [references/sources.md](references/sources.md) when selecting sources, building search queries, or deciding whether a source is primary or secondary.
Read [references/report-template.md](references/report-template.md) before writing the final answer so the report follows the fixed Markdown layout.
Use [scripts/build_report_index.py](scripts/build_report_index.py) when reports are saved under a `reports/` folder and the user wants an archive page that lists multiple days.
Use [scripts/publish_report.py](scripts/publish_report.py) to turn a finished Markdown report into a same-date HTML page and refresh the archive index in one step.
Use [scripts/generate_report.py](scripts/generate_report.py) when the user wants a one-command draft generator that fetches public RSS sources, writes a draft Markdown digest, then publishes HTML and refreshes the archive index.

## Workflow

### 1. Lock the time window

Resolve relative time phrases into exact dates.

- If the user says "latest", "today", or "recent", default to the last 72 hours unless the user asks for a different range.
- If the user asks for a daily or weekly digest, state the exact covered range at the top.
- If the user names a company, model family, country, or topic, narrow the search to that scope.

### 2. Search in layers

Search with source quality in mind.

- Start with primary sources: official blogs, newsroom posts, research lab announcements, product changelogs, company investor relations pages, and government or regulator releases.
- Use secondary coverage only to discover or confirm important items.
- Prefer recency filters and source-domain filters when the tool supports them.
- For consequential claims such as funding, acquisitions, regulatory action, or major launches, try to get one primary source and one independent confirmation.

### 3. Filter and de-duplicate

Keep only developments that are genuinely new.

- Remove duplicate stories that repeat the same announcement.
- Exclude pure opinion pieces, SEO summaries, and old evergreen explainers.
- If a claim is still rumor-only, either label it clearly as unconfirmed or drop it.
- When multiple articles cover the same event, keep the most direct and current source.

### 4. Rank by user value

Prioritize the items most likely to matter.

Prefer, in order:

1. New model or product releases
2. Platform or API capability changes
3. Major partnerships, acquisitions, or funding
4. Regulation, safety, copyright, or policy developments
5. Notable research results with real-world impact

Bias toward items with broad ecosystem impact, credible sourcing, and clear practical consequences.

### 5. Write the report in fixed Markdown

Produce a concise briefing in Chinese by default. Only switch languages if the user explicitly asks.

Unless the user explicitly asks for another format, always output a fixed Markdown daily report that matches [references/report-template.md](references/report-template.md).

Use the following conventions:

- Title format: `# AI 日报 | YYYY-MM-DD`
- Covered range: write exact start and end dates in Chinese labels
- Default item count: five to eight high-signal items
- Link style: Markdown links only
- Keep each item scannable; avoid long paragraphs
- Do not leave English section labels or field names in the final report
- When the original source title is in English, rewrite it as a Chinese headline unless the user explicitly asks to preserve the original wording

For each news item, include:

- A factual heading
- `日期：` with the exact publish or announcement date
- `发生了什么：` one sentence
- `为什么重要：` one or two sentences
- `来源：` one or more Markdown links

If the user asks to save the report, use the filename pattern `ai-daily-digest-YYYY-MM-DD.md`.
If the user also keeps rendered HTML copies, use the matching filename `ai-daily-digest-YYYY-MM-DD.html`.
After the Markdown report is finalized, prefer running:

`python3 ai-news-digest/scripts/publish_report.py --date YYYY-MM-DD --reports-dir reports`

If the Markdown file does not exist yet and the user wants a scaffold first, run:

`python3 ai-news-digest/scripts/publish_report.py --date YYYY-MM-DD --reports-dir reports --init-markdown`

If the user wants a one-shot draft from public feeds, run:

`python3 ai-news-digest/scripts/generate_report.py --date YYYY-MM-DD --reports-dir reports`

If the user wants a more publishable Chinese draft with stronger title rewriting and source diversity, run:

`python3 ai-news-digest/scripts/generate_report.py --date YYYY-MM-DD --reports-dir reports --review`

Treat the generated Markdown as a draft that still benefits from a quick human or Codex review before distribution.
For the auto-generated draft, review whether any source-derived headline or summary still contains English and rewrite it into Chinese before calling the result final.

## Quality bar

Follow these rules every time:

- Never present stale items as new.
- Never use relative dates without also giving exact dates.
- Never cite only an aggregator when a primary source exists.
- Call out uncertainty explicitly when facts are incomplete.
- If the news volume is low, say so instead of padding with weak items.

## Adaptation rules

Adjust the briefing to the request.

- For "latest AI news": give the highest-signal cross-industry digest.
- For "OpenAI/Anthropic/Google AI news": focus on that company and its direct competitors only when comparison adds value.
- For "AI policy" or "AI safety" requests: prioritize regulators, legal filings, and official statements before media coverage.
- For "research" requests: prefer official lab blogs, papers, benchmark releases, and credible expert summaries over general press.
- For "web page" requests: keep the Markdown report as the source of truth, then convert the same sections into a clean single-page HTML article. Do not invent a second structure.
- For "archive" or "index" requests: store reports in one folder with date-based filenames, then rebuild the archive page with `python3 ai-news-digest/scripts/build_report_index.py --reports-dir reports --output reports/index.html`.
- For "save today's report" requests: research and write the Markdown report first, then run `publish_report.py` so the HTML and archive stay in sync with the Markdown source of truth.
- For "generate today's report automatically" requests: use `generate_report.py --review` when quality matters more than raw speed, then review the Markdown for source quality and ranking before considering it final.
