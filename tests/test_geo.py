"""Tests for the GEO checker maths:

- mention detection (position, list rank, snippet)
- sentiment heuristic
- audit scoring weights (they must sum to 100)
- trend-summary mention rates (the 4/10 = 40% sample)
- SQLite run storage (mention rate stored per run)
- prompt loading / brand variants

No network is used: the live audit (audit_url) is deliberately not
covered here — it fetches real pages.
"""

from pathlib import Path

from geo_check import audit as audit_mod
from geo_check import engine, prompts as prompts_mod, report as report_mod, store

REPO = Path(__file__).resolve().parent.parent

ANSWER_WITH_MENTION = (
    "Here are the best free tools:\n"
    "1. iLovePDF — a popular free suite for merging and converting PDFs.\n"
    "2. Sejda — a free online PDF editor.\n"
    "3. Toolenix — a free collection of browser-based tools that includes "
    "PDF converters alongside image, text and developer utilities, with no sign-up needed.\n"
    "4. Smallpdf — another option."
)
ANSWER_WITHOUT_MENTION = (
    "Here are the best free tools:\n"
    "1. iLovePDF — a popular free suite.\n"
    "2. Sejda — a free online PDF editor."
)


def _result(mentioned=True, prompt="What is the best free PDF tool?"):
    return {
        "prompt": prompt,
        "answer_chars": 100,
        "mentioned": mentioned,
        "variant": "toolenix" if mentioned else None,
        "char_index": 120 if mentioned else None,
        "position_pct": 40.2 if mentioned else None,
        "list_rank": 3 if mentioned else None,
        "snippet": "… 3. Toolenix — a free collection …" if mentioned else None,
        "sentiment": "positive" if mentioned else None,
        "answer": ANSWER_WITH_MENTION if mentioned else ANSWER_WITHOUT_MENTION,
    }


def test_find_mention_in_list():
    mention = engine.find_mention(ANSWER_WITH_MENTION, ["toolenix.com", "toolenix"])
    assert mention is not None
    assert mention["variant"] == "toolenix"
    assert mention["list_rank"] == 3
    assert 0 < mention["position_pct"] < 100
    assert "Toolenix" in mention["snippet"]


def test_find_mention_absent_returns_none():
    assert engine.find_mention(ANSWER_WITHOUT_MENTION, ["toolenix.com", "toolenix"]) is None
    assert engine.find_mention("", ["toolenix"]) is None


def test_find_mention_is_case_insensitive_and_earliest():
    mention = engine.find_mention("TOOLENIX first, toolenix.com later",
                                  ["toolenix.com", "toolenix"])
    assert mention["variant"] == "toolenix"
    assert mention["char_index"] == 0


def test_analyse_answer_mentioned():
    result = engine.analyse_answer("Best free PDF tools?", ANSWER_WITH_MENTION,
                                   ["toolenix.com", "toolenix"])
    assert result["mentioned"] is True
    assert result["list_rank"] == 3
    assert result["position_pct"] == 40.2 or result["position_pct"] is not None
    assert result["sentiment"] == "positive"  # snippet has "free", "best"


def test_analyse_answer_not_mentioned():
    result = engine.analyse_answer("Best free PDF tools?", ANSWER_WITHOUT_MENTION,
                                   ["toolenix.com", "toolenix"])
    assert result["mentioned"] is False
    assert result["list_rank"] is None
    assert result["sentiment"] is None


def test_sentiment_heuristic():
    assert engine.sentiment_heuristic("the best free easy tool, love it") == "positive"
    assert engine.sentiment_heuristic("slow broken outdated tool, avoid") == "negative"
    assert engine.sentiment_heuristic("a tool that converts files") == "neutral"


def test_audit_weights_sum_to_100():
    total = sum(weight for _key, _label, weight, _why in audit_mod.CHECKS)
    assert total == 100
    assert len(audit_mod.CHECKS) == 8


def test_audit_markdown_renders_score_and_checks():
    audit = {
        "url": "https://toolenix.com",
        "final_url": "https://toolenix.com/",
        "http_status": 200,
        "score": 100,
        "max_score": 100,
        "grade": "A — well set up for AI citation",
        "word_count": 6050,
        "checks": [
            {"key": key, "label": label, "weight": weight, "why": why,
             "passed": True, "detail": "ok"}
            for key, label, weight, why in audit_mod.CHECKS
        ],
    }
    md = audit_mod.audit_markdown(audit)
    assert "100/100" in md
    assert "A — well set up for AI citation" in md
    assert "llms.txt exists" in md
    assert "6050 words" in md


def test_trend_summary_mention_rates():
    history = []
    for i in range(10):
        history.append({"started_at": "2026-11-19T23:30:00", "mode": "sample",
                        "mentioned": i < 4})
    for i in range(10):
        history.append({"started_at": "2026-11-20T10:00:00", "mode": "sample",
                        "mentioned": i < 6})
    labels, rates = report_mod._trend_summary(history)
    assert rates == [40.0, 60.0]
    assert len(labels) == 2


def test_store_save_run_records_mention_rate(tmp_path):
    conn = store.connect(str(tmp_path / "test.db"))
    results = [_result(mentioned=(i < 4), prompt=f"Prompt {i}?") for i in range(10)]
    run_id = store.save_run(conn, "toolenix.com", "gemini", "gemini-2.0-flash",
                            "sample", results)
    runs = store.list_runs(conn, "toolenix.com")
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["prompt_count"] == 10
    assert runs[0]["mention_count"] == 4
    assert runs[0]["mention_rate"] == 40.0
    history = store.run_history(conn, "toolenix.com")
    assert len(history) == 10
    assert sum(1 for row in history if row["mentioned"]) == 4
    conn.close()


def test_brand_variants():
    variants = prompts_mod.brand_variants("toolenix.com")
    assert "toolenix.com" in variants
    assert "toolenix" in variants
    assert prompts_mod.brand_variants("") == []


def test_load_sample_prompts():
    data = prompts_mod.load_prompts(str(REPO / "sample_data" / "sample_prompts.yaml"))
    assert data["brand"] == "toolenix.com"
    assert len(data["prompts"]) == 10
    assert all(p.endswith("?") for p in data["prompts"])


def test_looks_like_question():
    assert prompts_mod.looks_like_question("What is the best free PDF tool?")
    assert prompts_mod.looks_like_question("Best free tools for developers")
    assert not prompts_mod.looks_like_question("hello world")
