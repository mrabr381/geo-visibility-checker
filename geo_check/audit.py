"""Citation-readiness audit for a single page.

Checks whether an AI answer engine can easily find, trust and cite the
page: llms.txt, robots.txt, FAQ / FAQPage schema, other structured data,
heading structure, dates/facts, and basic readability signals. Every
check is a real fetch/parse — nothing is guessed. Scores are weighted
and the weighting is printed in the report.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import requests

HEADERS = {"User-Agent": "GEO-Visibility-Checker/0.1 (+free open-source audit)"}
TIMEOUT_S = 20

# (key, label, weight, what good looks like)
CHECKS = [
    ("llms_txt", "llms.txt exists", 20,
     "A /llms.txt file tells AI crawlers what the site offers."),
    ("robots_ok", "robots.txt allows AI crawlers", 10,
     "robots.txt must not block GPTBot / CCBot / Google-Extended."),
    ("faq", "FAQ content or FAQPage schema", 20,
     "Questions + answers in the page help AI engines quote it."),
    ("schema", "Structured data (JSON-LD) present", 15,
     "Schema.org markup (WebSite, FAQPage, HowTo, Article...) helps citation."),
    ("headings", "Clear heading structure (H1 + H2s)", 10,
     "One H1 and descriptive H2s make the page easy to summarise."),
    ("dates", "Dates / freshness signals", 10,
     "A published/updated date tells engines the facts are current."),
    ("length", "Substantive content (>= 300 words)", 10,
     "Thin pages rarely get cited; 300+ words is the floor here."),
    ("links", "Descriptive internal links", 5,
     "Named links (not 'click here') help engines follow the site."),
]


def _fetch(url: str) -> tuple[int | None, str, str]:
    """Returns (status, final_url, text). Status None on network error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
        return resp.status_code, resp.url, resp.text
    except requests.RequestException as exc:
        return None, url, f"ERROR: {exc}"


def audit_url(url: str) -> dict:
    """Audit one URL. Returns a dict with score, checks and details."""
    if not urlparse(url).scheme:
        url = "https://" + url
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    status, final_url, html = _fetch(url)
    if status is None:
        # Site unreachable: do not let the error message masquerade as
        # page content (it would inflate the word count and pass checks).
        html = ""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    results: dict[str, dict] = {}

    # llms.txt
    llms_status, _, llms_body = _fetch(urljoin(base, "/llms.txt"))
    results["llms_txt"] = {
        "passed": llms_status == 200 and len(llms_body or "") > 20,
        "detail": f"GET {base}/llms.txt -> HTTP {llms_status}"
                  + (" (empty)" if llms_status == 200 and len(llms_body or "") <= 20 else ""),
    }

    # robots.txt — fail only if it explicitly disallows known AI bots
    rob_status, _, rob_body = _fetch(urljoin(base, "/robots.txt"))
    blocked = []
    if rob_status == 200:
        for bot in ("GPTBot", "CCBot", "Google-Extended", "anthropic-ai",
                    "ClaudeBot", "PerplexityBot"):
            if re.search(rf"(?im)^User-agent:\s*\*?{re.escape(bot)}.*?^Disallow:\s*/\s*$",
                         rob_body or "", re.M | re.S):
                blocked.append(bot)
        # also catch a blanket "User-agent: * / Disallow: /"
        if re.search(r"(?im)^User-agent:\s*\*\s*$\nDisallow:\s*/\s*$", rob_body or ""):
            blocked.append("* (all bots)")
    if blocked:
        robots_passed, robots_detail = False, (
            f"robots.txt HTTP {rob_status}; blocks: {', '.join(blocked)}")
    elif rob_status == 200:
        robots_passed, robots_detail = True, (
            "robots.txt HTTP 200; no AI-bot blocks found")
    elif rob_status == 404:
        robots_passed, robots_detail = True, (
            "no robots.txt (HTTP 404) — nothing is blocked")
    elif rob_status is None:
        robots_passed, robots_detail = False, (
            "could not fetch robots.txt — site unreachable")
    else:
        robots_passed, robots_detail = False, (
            f"robots.txt HTTP {rob_status} — could not verify")
    results["robots_ok"] = {"passed": robots_passed, "detail": robots_detail}

    # FAQ: visible FAQ text or FAQPage schema
    has_faq_text = bool(re.search(r"\bfaq\b|frequently asked", text, re.I))
    has_faq_schema = bool(re.search(r'"@type"\s*:\s*"FAQPage"', html or ""))
    results["faq"] = {
        "passed": has_faq_text or has_faq_schema,
        "detail": ("FAQPage schema present" if has_faq_schema else
                   "FAQ text present" if has_faq_text else "no FAQ content found"),
    }

    # JSON-LD schema types
    types = sorted(set(re.findall(
        r'"@type"\s*:\s*"([A-Za-z]+)"', html or "")))
    results["schema"] = {
        "passed": bool(types),
        "detail": ("types: " + ", ".join(types)) if types else "no JSON-LD found",
    }

    # Headings
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html or "", re.I | re.S)
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.I | re.S)
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
    results["headings"] = {
        "passed": len(h1s) == 1 and len(h2s) >= 2,
        "detail": f"H1: {len(h1s)} ({clean(h1s[0])[:60] if h1s else 'none'}); "
                  f"H2: {len(h2s)}",
    }

    # Dates
    dates = set(re.findall(
        r"\b(20\d\d[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d\d)\b",
        text))
    has_date_meta = bool(re.search(
        r"(datePublished|dateModified|article:published_time)", html or ""))
    results["dates"] = {
        "passed": bool(dates) or has_date_meta,
        "detail": ("dates found: " + ", ".join(sorted(dates)[:3]))
                  if dates else ("date meta present" if has_date_meta else "no dates found"),
    }

    # Length
    results["length"] = {
        "passed": len(words) >= 300,
        "detail": f"{len(words)} words of visible text",
    }

    # Descriptive links
    anchors = re.findall(r'<a[^>]*>(.*?)</a>', html or "", re.I | re.S)
    named = [clean(a) for a in anchors if clean(a) and clean(a).lower() not in
             ("click here", "here", "read more", "more", "link")]
    results["links"] = {
        "passed": len(named) >= 5,
        "detail": f"{len(anchors)} links, {len(named)} with descriptive text",
    }

    score = sum(w for key, _label, w, _why in CHECKS if results[key]["passed"])
    max_score = sum(w for _k, _l, w, _w in CHECKS)
    grade = ("A — well set up for AI citation" if score >= 80 else
             "B — mostly ready, fix the gaps below" if score >= 60 else
             "C — partly ready" if score >= 40 else
             "D — AI engines will struggle to cite this page")
    return {
        "url": url,
        "final_url": final_url,
        "http_status": status,
        "score": score,
        "max_score": max_score,
        "grade": grade,
        "word_count": len(words),
        "checks": [
            {"key": key, "label": label, "weight": weight, "why": why,
             "passed": results[key]["passed"], "detail": results[key]["detail"]}
            for key, label, weight, why in CHECKS
        ],
    }


def audit_markdown(audit: dict) -> str:
    """Render an audit dict as Markdown."""
    lines = [
        f"# Citation-readiness audit: {audit['url']}",
        "",
        f"**Score: {audit['score']}/{audit['max_score']} — {audit['grade']}**",
        f"HTTP {audit['http_status']} · final URL: {audit['final_url']} · "
        f"{audit['word_count']} words",
        "",
        "| Check | Weight | Result | Detail |",
        "|---|---|---|---|",
    ]
    for c in audit["checks"]:
        mark = "✅ Pass" if c["passed"] else "❌ Fail"
        lines.append(f"| {c['label']} | {c['weight']} | {mark} | {c['detail']} |")
    lines += ["", "## Why each check matters", ""]
    for c in audit["checks"]:
        lines.append(f"- **{c['label']}** ({c['weight']} pts): {c['why']}")
    return "\n".join(lines) + "\n"
