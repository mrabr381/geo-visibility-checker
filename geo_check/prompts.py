"""Loading and validating prompt lists (prompts.yaml)."""

from __future__ import annotations

import re

import yaml

MIN_PROMPTS = 1
MAX_PROMPTS = 50

# A prompt should look like a question a real user would ask an AI
# assistant, not a bare keyword.
QUESTION_WORDS = ("what", "which", "how", "why", "where", "when", "who",
                  "best", "top", "recommend", "compare", "is there", "can you")


class PromptError(ValueError):
    """Raised when a prompts file is missing or invalid."""


def load_prompts(path: str) -> dict:
    """Load a prompts file. Returns {"brand": str, "prompts": [str, ...]}.

    Accepted formats:
      - YAML mapping: {brand: "toolenix.com", prompts: ["...", "..."]}
      - YAML list of strings (brand must then be passed separately)
      - Plain text, one prompt per line (lines starting with # ignored)
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise PromptError(f"cannot read prompts file {path!r}: {exc}") from exc

    if not raw.strip():
        raise PromptError(f"prompts file {path!r} is empty")

    if path.endswith((".yaml", ".yml")):
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise PromptError(f"invalid YAML in {path!r}: {exc}") from exc
    else:
        data = None

    prompts: list[str] = []
    brand = ""
    if isinstance(data, dict):
        brand = str(data.get("brand") or "").strip()
        items = data.get("prompts") or []
        if not isinstance(items, list):
            raise PromptError(f"{path!r}: 'prompts' must be a list")
        prompts = [str(p).strip() for p in items]
    elif isinstance(data, list):
        prompts = [str(p).strip() for p in data]
    else:
        prompts = [ln.strip() for ln in raw.splitlines()
                   if ln.strip() and not ln.strip().startswith("#")]

    prompts = [p for p in prompts if p]
    if len(prompts) < MIN_PROMPTS:
        raise PromptError(f"{path!r}: need at least {MIN_PROMPTS} prompt")
    if len(prompts) > MAX_PROMPTS:
        raise PromptError(
            f"{path!r}: {len(prompts)} prompts exceeds the {MAX_PROMPTS} limit "
            "(split the list into two runs)")
    seen: set[str] = set()
    for p in prompts:
        key = p.lower()
        if key in seen:
            raise PromptError(f"{path!r}: duplicate prompt: {p!r}")
        seen.add(key)
    return {"brand": brand, "prompts": prompts}


def brand_variants(brand: str) -> list[str]:
    """Strings that count as a mention of the brand in an AI answer.

    The bare brand, its domain without TLD dots, and its name with spaces.
    E.g. "toolenix.com" -> ["toolenix.com", "toolenix"].
    """
    brand = brand.strip().lower()
    if not brand:
        return []
    variants = {brand}
    host = re.sub(r"^https?://", "", brand).strip("/").split("/")[0]
    variants.add(host)
    name = host.split(".")[0]
    variants.add(name)
    variants.add(name.replace("-", " "))
    return sorted(v for v in variants if v)


def looks_like_question(prompt: str) -> bool:
    """Heuristic: does the prompt read like a real user question?"""
    text = prompt.strip().lower()
    if text.endswith("?"):
        return True
    return any(text.startswith(w) for w in QUESTION_WORDS)
