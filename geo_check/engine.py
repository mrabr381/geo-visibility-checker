"""Answer-engine calls (Gemini free tier, BYO key) and mention parsing.

SAFE SCOPE — read this before extending:
There is no official free API for ChatGPT or Perplexity answers, so this
tool does NOT scrape them. It queries Google's Gemini API (free tier, the
user's own key) and analyses the returned answer text. A prompt run against
Gemini measures visibility in *Gemini's* answers; it is not a claim about
any other engine. The report and README say so plainly.
"""

from __future__ import annotations

import json
import re
import time

import requests

DEFAULT_MODEL = "gemini-2.0-flash"
FALLBACK_MODEL = "gemini-1.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_S = 60

# System instruction: we want a normal assistant answer, the way a real
# user would see it — not a "list every tool" prompt that would inflate
# mentions. The brand name is never mentioned in the request.
SYSTEM_PROMPT = (
    "Answer the user's question helpfully and concisely, as you would for "
    "a normal user. If a list fits, give a short list with a one-line reason "
    "for each item. Do not mention that you are being tested."
)

POSITIVE_WORDS = {
    "best", "excellent", "great", "free", "easy", "fast", "useful",
    "popular", "recommended", "top", "powerful", "simple", "reliable",
    "love", "favourite", "favorite", "impressive", "handy",
}
NEGATIVE_WORDS = {
    "worst", "bad", "slow", "broken", "unreliable", "outdated",
    "limited", "expensive", "avoid", "poor", "buggy", "cluttered",
}


class EngineError(RuntimeError):
    """Raised when the answer engine cannot be reached or rejects a call."""


def _post_answer(prompt: str, api_key: str, model: str) -> str:
    url = f"{API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        raise EngineError(f"network error calling Gemini: {exc}") from exc
    if resp.status_code == 404:
        raise EngineError(f"model {model!r} not available (HTTP 404) — "
                          "the model name may have been retired; "
                          "set GEMINI_MODEL to a current free-tier model")
    if resp.status_code in (400, 403):
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = resp.text[:200]
        raise EngineError(f"Gemini rejected the request (HTTP {resp.status_code}): "
                          f"{detail or 'check that GEMINI_API_KEY is a valid free-tier key'}")
    if resp.status_code == 429:
        raise EngineError("Gemini rate limit hit (HTTP 429) — free-tier quota "
                          "exceeded; wait a while and re-run")
    if resp.status_code != 200:
        raise EngineError(f"Gemini returned HTTP {resp.status_code}: "
                          f"{resp.text[:200]}")
    try:
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise EngineError(f"unexpected Gemini response shape: {exc}") from exc


def ask(prompt: str, api_key: str, model: str = DEFAULT_MODEL,
        sleep_s: float = 0.5) -> str:
    """Ask the answer engine one prompt. Returns the raw answer text."""
    if sleep_s:
        time.sleep(sleep_s)  # stay polite to the free tier
    try:
        return _post_answer(prompt, api_key, model)
    except EngineError as exc:
        if "not available" in str(exc) and model != FALLBACK_MODEL:
            return _post_answer(prompt, api_key, FALLBACK_MODEL)
        raise


def find_mention(answer: str, variants: list[str]) -> dict | None:
    """Find the first mention of the brand in an answer.

    Returns None when not mentioned, else a dict with the matched variant,
    character position, position in the answer as a percentage, and the
    rank among list items (1-based) when the answer contains a list.
    """
    text = answer or ""
    lowered = text.lower()
    best: dict | None = None
    for variant in variants:
        if not variant:
            continue
        idx = lowered.find(variant.lower())
        if idx == -1:
            continue
        if best is None or idx < best["char_index"]:
            best = {"variant": variant, "char_index": idx}
    if best is None:
        return None
    total = max(len(text), 1)
    best["position_pct"] = round(100.0 * best["char_index"] / total, 1)
    # Rank: count list items (lines starting with -, *, digit., or a
    # heading-like entry) that appear before the mention.
    items_before = 0
    for line in text[: best["char_index"]].splitlines():
        if re.match(r"^\s*([-*•]|\d+[.)])\s+\S", line):
            items_before += 1
    best["list_rank"] = items_before + 1 if items_before or re.search(
        r"^\s*([-*•]|\d+[.)])\s", text, re.M) else None
    start = max(0, best["char_index"] - 120)
    end = min(len(text), best["char_index"] + 160)
    snippet = text[start:end].replace("\n", " ").strip()
    best["snippet"] = ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
    return best


def sentiment_heuristic(snippet: str) -> str:
    """Keyword-based sentiment label for a mention snippet.

    This is a transparent word-list heuristic, NOT a model judgement —
    the report labels it as such. Returns positive / negative / neutral.
    """
    words = set(re.findall(r"[a-z]+", (snippet or "").lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def analyse_answer(prompt: str, answer: str, variants: list[str]) -> dict:
    """Full per-prompt analysis: mention, position, snippet, sentiment."""
    mention = find_mention(answer, variants)
    result = {
        "prompt": prompt,
        "answer_chars": len(answer or ""),
        "mentioned": mention is not None,
        "variant": mention["variant"] if mention else None,
        "char_index": mention["char_index"] if mention else None,
        "position_pct": mention["position_pct"] if mention else None,
        "list_rank": mention["list_rank"] if mention else None,
        "snippet": mention["snippet"] if mention else None,
        "sentiment": sentiment_heuristic(mention["snippet"]) if mention else None,
        "answer": answer or "",
    }
    return result
