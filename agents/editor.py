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

from pydantic import BaseModel

from .common import CONFIG, ask_json


class Verdict(BaseModel):
    approved: bool
    issues: list[str]
    fix_instructions: str


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
draft against the pitch and decide if it is fit to publish.

Reject (approved=false) only for MATERIAL problems:
- A concrete factual claim (a date, number, price, name, quote) that does not
  trace to the pitch facts — i.e. invented or speculative detail.
- Reported/rumored info presented as confirmed fact, or a clear attribution
  missing where another outlet broke the story.
- A headline the body does not pay off.
- Anyone mocked or treated with disrespect; layoffs/closures handled without
  care for the people involved.
- Prose that copies a source's phrasing rather than being original.

Do NOT reject for matters of taste, structure, length, or reasonable framing
of facts that ARE in the pitch. If the draft is accurate, fairly attributed,
original, and respectful, approve it. Be specific: each issue must name the
exact offending text so it can be fixed.

Return JSON: {"approved": bool, "issues": [str], "fix_instructions": str}"""


def review(draft: dict, pitch: dict) -> dict:
    # Judge the draft fresh: drop internal keys (e.g. _editor_feedback from a
    # prior retry) so the editor doesn't re-flag stale issues and inflate its
    # own output past the token budget.
    clean_pitch = {k: v for k, v in pitch.items() if not k.startswith("_")}
    user = ("Pitch:\n" + json.dumps(clean_pitch, indent=2) +
            "\n\nDraft:\n" + json.dumps(draft, indent=2))
    return ask_json("editor", REVIEW_SYSTEM, user, max_tokens=4000, schema=Verdict)


def edit_gate(draft: dict, pitch: dict) -> dict:
    """Run both gates. Returns {'pass': bool, 'issues': [...], 'fix': str}."""
    source_texts = [f["fact"] for f in pitch.get("facts", [])]
    orig = originality_report(draft.get("body_markdown", ""), source_texts)
    issues, fix = [], ""
    if not orig["ok"]:
        issues.append(f"Originality: shared phrases with sources: {orig['shared']}")
        fix += "Rewrite the flagged passages entirely in your own words. "
    llm = review(draft, pitch)
    if not llm.get("approved", False):
        issues += llm.get("issues", [])
        fix += llm.get("fix_instructions", "")
    return {"pass": not issues, "issues": issues, "fix": fix}
