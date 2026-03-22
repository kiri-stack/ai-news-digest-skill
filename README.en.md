# AI News Digest Skill

[中文](./README.md)

A Codex Skill built for **tracking the latest AI developments**.

This is not just another news scraper. It is a complete workflow for **high-trust source selection**, **structured Chinese digest generation**, and **HTML archive publishing**.

## Why This Skill Matters

There is no shortage of AI news. What is scarce is signal.

The goal of this Skill is not to dump the entire AI internet into a report. It is designed to surface **high-signal updates** from primary and trusted sources as quickly as possible, then turn them into a readable, structured, archive-friendly format.

It works especially well for:

- Daily AI intelligence tracking
- AI industry daily or weekly briefings
- Internal company intelligence updates
- Monitoring models, platforms, safety, policy, and industry moves
- Publishing AI summaries for Chinese-speaking audiences

## Core Capabilities

- Pull the latest AI updates from public, high-trust sources
- Resolve time expressions like "today", "latest", "recent", and "this week" into exact dates
- Deduplicate, rank, and filter for high-signal developments only
- Generate structured Chinese Markdown digests by default
- Render each report into a clean single-page HTML view
- Maintain an `index.html` archive for browsing reports by date
- Support both fast draft generation and a stronger Chinese review mode

## The Part I Care About Most: Sources

The real value of this Skill starts with **source quality**.

It prioritizes:

- Official company blogs
- Corporate newsrooms
- Public research updates
- Public RSS feeds
- A small number of trusted tech media feeds for discovery

The default one-command generator currently pulls from:

- Google Blog
- Microsoft Blog
- NVIDIA Blog
- Meta Newsroom
- TechCrunch AI

That means the Skill is naturally biased toward:

- Official announcements
- Platform updates
- Product launches
- Safety and governance developments
- Research and real-world deployment signals

Instead of:

- generic reposts
- SEO content farms
- social posts without traceable sourcing

## What the Output Looks Like

By default, the Skill produces a **fully Chinese, structured daily digest** with sections such as:

- Top line
- Key developments
- Industry watch
- Why watch next

It can also render the same report into:

- a single-page HTML digest
- a multi-day archive page via `index.html`

So the output is not just useful for reading once. It can become part of a long-term content archive.

## How to Use It

### 1. Generate a daily digest draft

```bash
python3 scripts/generate_report.py --date YYYY-MM-DD --reports-dir reports
```

### 2. Generate a more polished Chinese draft

```bash
python3 scripts/generate_report.py --date YYYY-MM-DD --reports-dir reports --review
```

### 3. Publish HTML and refresh the archive from an existing Markdown report

```bash
python3 scripts/publish_report.py --date YYYY-MM-DD --reports-dir reports
```

## What Is Inside This Repository

- `SKILL.md`: main Skill instructions and trigger logic
- `references/`: source strategy and report template
- `scripts/generate_report.py`: fetches public feeds and generates a Chinese daily digest draft
- `scripts/publish_report.py`: publishes Markdown to HTML and refreshes the archive
- `scripts/build_report_index.py`: rebuilds the report index page

## Current Boundaries

This Skill is already practical for day-to-day use, but it is not pretending to be a fully autonomous editorial team.

Its real role today is:

- a high-quality Chinese AI digest generator
- a workflow built around trusted sourcing and structured output
- a reusable framework for extending feeds and publishing pipelines

It already handles:

- draft generation
- HTML publishing
- archive maintenance

But if you are publishing externally, it is still worth doing a quick human review for:

- headline naturalness
- ranking decisions
- whether a second confirming source is needed

## Repository Goal

The goal of this project is not to build the loudest AI news crawler.

It is to build a more disciplined and more trustworthy **AI information production tool**:

- source-aware
- structured
- consistent
- archivable
- continuously improvable
