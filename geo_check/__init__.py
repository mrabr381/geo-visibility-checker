"""GEO Visibility Checker — free AI-search brand tracker.

Tracks whether/how a brand or site is mentioned by AI answer engines
(Gemini, via the free-tier BYO key) for a list of prompts, stores runs in
SQLite, and audits pages for citation-readiness (llms.txt, FAQ/schema,
structure). No scraping of ChatGPT/Perplexity — there is no official free
API for those, and scraping them is fragile and against their terms.
"""

__version__ = "0.1.0"
