"""Editor agent: mechanical originality check + LLM standards review.

Two gates before anything publishes:
1. Originality gate (pure code): compares the draft against every source
   snippet the scout collected. Long shared word n-grams or a high overlap
   ratio = rejection with the offending passages, so the writer can rewrite.
2. Standards gate (LLM): checks facts-vs-pitch, attribution, rumor labeling,
   headline payoff, and tone. Returns pass/fail with required fixes.
"""

from __future__ import annotations

import json
import re

from .common import CONFIG, ask_json

_WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def originality_report(draft_text: str, source_texts: list[str]) -> dict:
    """Flag long verbatim runs shared with any source snippet."""
    n = CONFIG["originality"]["max_shared_ngram"]
    max_ratio = CONFIG["originality"]["max_overlap_ratio"]
    draft_words = _words(draft_text)
    draft_grams = _ngrams(draft_words, n)
    if not draft_grams:
        return {"ok": True, "shared": [], "ratio": 0.0}

    shared: set[tuple[str, ...]] = set()
    for src in source_texts:
        shared |= draft_grams & _ngrams(_words(src), n)

    ratio = len(shared) / len(draft_grams)
    return {
        "ok": not shared or ratio <= max_ratio and len(shared) <= 2,
        "shared": [" ".join(g) for g in sorted(shared)][:10],
        "ratio": round(ratio, 4),
    }


REVIEW_SYSTEM = """You are the standards editor for QUICKSAVE. Review the
draft against the pitch. Fail the draft if ANY of these hold:
- A factual claim does not appear in the pitch facts (hallucination).
- Reported/rumored info is presented as confirmed, or attribution is missing.
- The headline over-promises relative to the body.
- Anyone is mocked or treated disrespectfully; layoffs/closures handled
  without care.
- It reads like a press release or like another outlet's copy.
Return JSON: {"pass": bool, "issues": [str], "fix_instructions": str}"""


def review(draft: dict, pitch: dict) -> dict:
    user = ("Pitch:\n" + json.dumps(pitch, indent=2) +
            "\n\nDraft:\n" + json.dumps(draft, indent=2))
    return ask_json("editor", REVIEW_SYSTEM, user, max_tokens=1500)


def edit_gate(draft: dict, pitch: dict) -> dict:
    """Run both gates. Returns {'pass': bool, 'issues': [...], 'fix': str}."""
    source_texts = [f["fact"] for f in pitch.get("facts", [])]
    orig = originality_report(draft.get("body_markdown", ""), source_texts)
    issues, fix = [], ""
    if not orig["ok"]:
        issues.append(f"Originality: shared phrases with sources: {orig['shared']}")
        fix += "Rewrite the flagged passages entirely in your own words. "
    llm = review(draft, pitch)
    if not llm.get("pass", False):
        issues += llm.get("issues", [])
        fix += llm.get("fix_instructions", "")
    return {"pass": not issues, "issues": issues, "fix": fix}
