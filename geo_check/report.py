"""Report generation: CSV, Markdown, and trend charts (matplotlib)."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV_FIELDS = ["prompt", "mentioned", "variant", "char_index",
              "position_pct", "list_rank", "sentiment", "snippet",
              "answer_chars"]


def write_csv(results: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})


def _trend_summary(history: list[dict]) -> tuple[list[str], list[float]]:
    """Mention rate per run (oldest first) from run_history rows."""
    runs: dict[str, list[int]] = {}
    order: list[str] = []
    for row in history:
        key = f"{row['started_at'][:16]} ({row['mode']})"
        if key not in runs:
            runs[key] = []
            order.append(key)
        runs[key].append(1 if row["mentioned"] else 0)
    labels = order
    rates = [round(100.0 * sum(v) / len(v), 1) for v in (runs[k] for k in order)]
    return labels, rates


def write_chart(results: list[dict], history: list[dict], path: str) -> None:
    """Two-panel chart: mention rate over runs + per-prompt mentions."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    labels, rates = _trend_summary(history)
    if len(labels) >= 1:
        x = range(len(labels))
        ax1.bar(x, rates, color="#6d28d9")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([l[:16] for l in labels], rotation=25, ha="right",
                            fontsize=8)
        ax1.set_ylim(0, 100)
        ax1.set_ylabel("Mention rate (%)")
        ax1.set_title("Mention rate over runs")
        for xi, v in zip(x, rates):
            ax1.text(xi, v + 2, f"{v}%", ha="center", fontsize=9)
    else:
        ax1.text(0.5, 0.5, "No history yet", ha="center", va="center")
        ax1.set_title("Mention rate over runs")
    mentioned = [1 if r["mentioned"] else 0 for r in results]
    ax2.bar(["Mentioned", "Not mentioned"],
            [sum(mentioned), len(mentioned) - sum(mentioned)],
            color=["#16a34a", "#dc2626"])
    ax2.set_ylabel("Prompts")
    ax2.set_title(f"This run: {sum(mentioned)}/{len(mentioned)} mentioned")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_markdown(brand: str, engine: str, model: str, mode: str,
                   results: list[dict], history: list[dict],
                   audit: dict | None, path: str) -> str:
    """Write the full Markdown report. Returns the report text."""
    mentioned = sum(1 for r in results if r["mentioned"])
    rate = round(100.0 * mentioned / len(results), 1) if results else 0.0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    lines = [
        f"# GEO Visibility Report — {brand}",
        "",
        f"Generated {now} · Engine: **{engine}** ({model}) · Mode: **{mode}**",
        "",
    ]
    if mode == "sample":
        lines += [
            "> ⚠️ **Sample mode:** no API key was used. The answers below come "
            "from the bundled sample dataset so the report format can be "
            "previewed — they are NOT live measurements. Run with "
            "`GEMINI_API_KEY` set for a real measurement.",
            "",
        ]
    lines += [
        f"## Summary",
        "",
        f"- Prompts tested: **{len(results)}**",
        f"- Brand mentioned: **{mentioned} ({rate}%)**",
        f"- Runs in history for this brand: **{len({r['started_at'] for r in history})}**",
        "",
        "## Per-prompt results",
        "",
        "| Prompt | Mentioned | Position | Rank | Sentiment | Snippet |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        snippet = (r["snippet"] or "—").replace("|", "/").replace("\n", " ")
        pos = f"{r['position_pct']}%" if r["position_pct"] is not None else "—"
        rank = f"#{r['list_rank']}" if r["list_rank"] else "—"
        sent = r["sentiment"] or "—"
        mark = "✅ Yes" if r["mentioned"] else "❌ No"
        lines.append(f"| {r['prompt']} | {mark} | {pos} | {rank} | {sent} | {snippet} |")
    lines += [
        "",
        "## How to read this",
        "",
        "- **Mentioned** — did the AI answer name the brand at all?",
        "- **Position** — how far into the answer the first mention appears "
        "(0% = first word). Earlier is better.",
        "- **Rank** — which list item the brand was, when the answer was a "
        "list (1 = first).",
        "- **Sentiment** — a keyword-based heuristic on the snippet only, "
        "not a model judgement.",
        "- This report measures **Gemini** answers only. There is no official "
        "free API for ChatGPT or Perplexity, so this tool does not claim "
        "to measure them.",
        "",
    ]
    if audit:
        lines += [
            "## Citation-readiness audit",
            "",
            f"**{audit['url']} — {audit['score']}/{audit['max_score']} "
            f"({audit['grade']})**",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
        ]
        for c in audit["checks"]:
            mark = "✅ Pass" if c["passed"] else "❌ Fail"
            lines.append(f"| {c['label']} | {mark} | {c['detail']} |")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return "\n".join(lines)
