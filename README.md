# GEO Visibility Checker 🔍

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![No API key required](https://img.shields.io/badge/API%20key-not%20required-brightgreen.svg)](#quickstart)
[![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B.svg)](#live-demo)
[![GitHub Pages demo](https://img.shields.io/badge/demo-live%20sample%20report-22c55e.svg)](#live-demo)

**Does ChatGPT / Gemini / Perplexity mention your site — or your competitors — when people ask "best X for Y"?**

This free, open-source tracker runs 10–50 prompts against an AI answer engine, records whether and how your brand is mentioned, charts the trend over time, and audits your pages for citation-readiness (llms.txt, FAQ/schema, structure). It uses your own free-tier Gemini key. No server, no subscription — results live in a local SQLite database.

> **Live demo:** see a real sample report for toolenix.com — [sample report page](sample_data/sample_output/index.html) (works on GitHub Pages, no server needed) — or run the web app on Streamlit Community Cloud (one-click deploy, see [Live demo](#live-demo)).

## Table of contents

- [Before / after](#before--after)
- [What it produces](#what-it-produces)
- [Live demo](#live-demo)
- [Quickstart](#quickstart)
- [Usage](#usage)
- [Web app](#web-app)
- [Comparison with paid tools](#comparison-with-paid-tools)
- [Quality promise — no invented content](#quality-promise--no-invented-content)
- [How it works](#how-it-works)
- [Honest limitations](#honest-limitations)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Before / after

**Before — guessing about AI search:**

```
❓ "Does Gemini ever mention my site?"
❓ "Are we gaining or losing visibility month to month?"
❓ "Is my page even citable by AI?"
😩 …and the tools that answer this cost $49–$499/month
```

**After — one command:**

```bash
python -m geo_check --prompts prompts.yaml --sample
```

```
report/
├── report.md       # mention rate, per-prompt table, audit summary
├── results.csv     # every prompt, position, rank, sentiment, snippet
└── trend.png       # mention rate over runs + mentioned vs not
geo_visibility.db  # every run, stored locally for trends
```

<details>
<summary><strong>Real sample output (toolenix.com, 10 prompts, sample mode)</strong></summary>

```
Done — toolenix.com: mentioned in 4/10 prompts (40.0%) [sample] · run #2

| Prompt | Mentioned | Position | Rank |
|---|---|---|---|
| Best free online tools for converting PDF files? | ✅ Yes | 40.2% | #3 |
| Best free word counter tool online? | ✅ Yes | 30.1% | — |
| Best free tools for developers in 2026? | ✅ Yes | 30.8% | #3 |
| Where can I find free online calculators? | ✅ Yes | 34.8% | — |
| (6 more prompts) | ❌ No | — | — |
```

And the citation audit on the live site, for real:
`https://toolenix.com: 100/100 — A, well set up for AI citation`
(all 8 checks passed — see [`sample_data/sample_output/audit.md`](sample_data/sample_output/audit.md))

</details>

## What it produces

- **Mention tracking** — for each prompt: mentioned yes/no, first-mention position in the answer, list rank when the answer is a list, and a snippet of the mention in context.
- **Trend history** — every run is stored in SQLite with a timestamp, so you can see whether visibility is rising or falling across runs.
- **Citation-readiness audit** — 8 weighted checks on any URL: llms.txt, robots.txt AI-bot blocks, FAQ/FAQPage schema, JSON-LD, heading structure, dates, content length, descriptive links. Score out of 100 with a grade.
- **Exports** — Markdown report, CSV of every result, and a PNG trend chart. No account, no upload, no server.

## Live demo

- **Sample report (GitHub Pages):** [`sample_data/sample_output/index.html`](sample_data/sample_output/index.html) — a static page showing the full sample pack. After cloning, enable Pages: repo Settings → Pages → Source: Deploy from a branch → `main`, folder `/ (root)` → Save. Live at `https://mrabr381.github.io/geo-visibility-checker/sample_data/sample_output/`.
- **Web app (Streamlit Community Cloud, one click):** [share.streamlit.io](https://share.streamlit.io) → Create app → repo `mrabr381/geo-visibility-checker`, branch `main`, file `app.py` → Deploy. No key needed for sample mode; optional `GEMINI_API_KEY` in Secrets for live runs.

## Quickstart

```bash
git clone https://github.com/mrabr381/geo-visibility-checker.git
cd geo-visibility-checker
pip install -r requirements.txt

# Preview with zero setup (bundled sample answers, clearly labelled):
python -m geo_check --prompts prompts.yaml --sample

# Live measurement with your free Gemini key:
export GEMINI_API_KEY="your-free-key"   # from https://aistudio.google.com/app/apikey
python -m geo_check --prompts prompts.yaml

# Audit one page for citation-readiness:
python -m geo_check --audit https://example.com
```

Write your own prompts in `prompts.yaml` — 1–50 real questions users ask
AI assistants, e.g. `"What is the best free invoicing tool for freelancers?"`.
Set `brand:` to your site or brand name.

## Usage

```
python -m geo_check --prompts prompts.yaml [--brand example.com]
                     [--out report] [--db geo_visibility.db]
                     [--sample] [--model gemini-2.0-flash]
                     [--api-key KEY] [--no-store]
python -m geo_check --audit https://example.com [--out report]
```

| Flag | Meaning |
|---|---|
| `--prompts` | YAML file with `brand:` + a `prompts:` list (1–50) |
| `--brand` | Overrides the brand in the prompts file |
| `--sample` | Use bundled sample answers — no key, no network calls to Gemini |
| `--audit URL` | Citation-readiness audit instead of a prompt run |
| `--out` | Output directory (default `report`) |
| `--db` | SQLite database (default `geo_visibility.db`, gitignored) |
| `--no-store` | Don't save this run to the database |

Exit codes: `0` success · `1` input or engine error (message printed, no traceback) · `2` usage error.

## Web app

```bash
streamlit run app.py
```

Three tabs: **Run prompts** (paste prompts or upload a prompts file, sample or live mode, results table + CSV download), **History** (past runs for a brand from the local database), **Citation audit** (audit any URL in the browser).

## Comparison with paid tools

Prices are from vendor pricing pages and comparisons read in November 2026 — re-check them before quoting elsewhere, they change.

| Tool | Price | What you get |
|---|---|---|
| **Dageno** | Starter $49–79/mo · Growth $199/mo · Scale $499/mo | AI visibility tracking across engines |
| **Profound** | Enterprise / custom (trial only) | AI visibility analytics |
| **Peec AI** | $95/mo | AI search monitoring |
| **Otterly** | $29/mo | AI visibility tracking |
| **Semrush AI Visibility** | $99/domain/mo | AI search add-on to Semrush |
| **OpenSEO** (open source, 25k stars) | Free code — but needs paid DataForSEO data ($50 minimum top-up) | Full SEO suite, not a lightweight GEO tracker |
| **GEO Visibility Checker (this repo)** | **$0** — Gemini free tier, BYO key | Prompt tracking, trends, citation audit |

The gap this fills: a lightweight, local, BYO-key tracker with no subscription and no paid data API. Dageno was #3 on Product Hunt's November 2026 board — GEO tracking is a new, fast-growing category, and the free options are almost all full SEO suites.

## Quality promise — no invented content

- Every mention, rank, position and snippet in a report comes from a real answer — a live Gemini response, or the bundled sample dataset (which every sample report labels as sample, in the file itself).
- If Gemini is unreachable or the key is invalid, the run **fails with a clear message** (exit 1) instead of inventing results.
- Sentiment is a transparent keyword-based heuristic on the snippet, labelled as such in every report — not a model judgement.
- The audit fetches the real page and reports real HTTP statuses. An unreachable site scores 0/100 with "site unreachable" on the checks it could not run — never a made-up score.

## How it works

```
prompts.yaml ──▶ Gemini API (free tier, BYO key) ──▶ analyse_answer()
                     │                                     │ mention? position?
                     │                                     │ rank? snippet? sentiment?
                     ▼                                     ▼
              sample mode (no key) ──▶ bundled answers ──▶ SQLite runs/results
                                                              │
                                        report.md + results.csv + trend.png
```

- **Mention matching** is case-insensitive on the brand, its domain, and its bare name (`toolenix.com` matches "Toolenix", "toolenix.com").
- **List rank** counts list items before the first mention (1 = the answer recommended you first).
- **Audit scoring** is weighted and printed: llms.txt 20, FAQ 20, schema 15, robots 10, headings 10, dates 10, length 10, links 5.

## Honest limitations

- **This tool measures Gemini answers only.** There is no official free API for ChatGPT or Perplexity answers, so it does not scrape them (scraping is fragile and against their terms) and does not claim to measure them. If you need other engines, the engine layer (`geo_check/engine.py`) is the one place to add an official API.
- **Gemini free-tier limits and model names change** — model names rotated in Oct–Nov 2026. The default is `gemini-2.0-flash` (override with `GEMINI_MODEL`); if a model is retired the tool falls back to `gemini-1.5-flash` and says so in the error.
- **A successful live Gemini call was not testable in the sandbox** (the sandbox proxy blocks `generativelanguage.googleapis.com` — a fake key is correctly rejected with HTTP 400, but a real generation call needs a normal network). First live run with a real free key is the remaining check.
- **Sample answers are illustrative, not measurements** — they exist so the report format can be previewed without a key, and every sample output says so.
- **Audit scores are a heuristic**, not a guarantee of citation — a high score means the page is easy to cite, not that engines will cite it.

## Project structure

```
geo-visibility-checker/
├── app.py                  # Streamlit web app (repo root, deploy-ready)
├── prompts.yaml            # example prompt list (Toolenix, 10 prompts)
├── geo_check/
│   ├── cli.py              # args, run/audit routing, exit codes
│   ├── engine.py           # Gemini REST calls + mention parsing
│   ├── prompts.py          # prompts.yaml loading + validation
│   ├── store.py            # SQLite runs/results
│   ├── audit.py            # citation-readiness audit (8 checks)
│   └── report.py           # CSV / Markdown / matplotlib charts
├── sample_data/
│   ├── sample_prompts.yaml
│   ├── sample_answers.json # bundled sample answers (4/10 mention Toolenix)
│   └── sample_output/      # real generated report + chart + index.html demo
├── requirements.txt
└── .env.example
```

## Contributing

Issues and pull requests are welcome. Please keep the safe scope: no scraping of answer engines, no invented data in outputs, and every price quoted in the README must come from a vendor page you link.

## License

MIT — see [LICENSE](LICENSE).
