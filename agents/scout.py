"""Scout agent: scours the web for what's worth writing about today.

Two steps, because Gemini's search grounding can't be combined with enforced
JSON output mode: (1) a grounded research call that returns prose notes, then
(2) a strict JSON-mode call that structures those notes into pitches. Step 2's
constrained decoding guarantees syntactically valid JSON, which a grounded
response does not.
"""

from __future__ import annotations

from pydantic import BaseModel

from .common import CONFIG, ask, ask_json, recent_topics


class Fact(BaseModel):
    fact: str
    status: str
    source_title: str
    source_url: str


class Pitch(BaseModel):
    topic: str
    section: str
    why_now: str
    sensitive: bool
    facts: list[Fact]
    competing_coverage: str

RESEARCH_SYSTEM = """You are the research scout for QUICKSAVE, an autonomous
video game news and reviews site. Use web search to find what is genuinely
worth covering RIGHT NOW.

Rules:
- Search broadly: gaming news today, new releases this week, big reviews,
  industry developments, hardware, indie breakouts, esports.
- Prefer stories with momentum (announced/updated in the last 72 hours) and
  evergreen angles tied to current events.
- For each story, write detailed notes: every fact, whether it is CONFIRMED
  (official announcement) vs REPORTED/RUMORED (journalist sourcing, leaks),
  the source title and URL for each fact, and what other outlets' take is.
- Sensitive stories (layoffs, closures, controversies) are in scope, but
  flag them as sensitive so the writer uses extra care.
- Skip anything that substantially overlaps the recently-covered list.

Write thorough prose notes - a later step structures them, and the writer may
only use facts you record here. Dates, platforms, prices, names, URLs:
capture everything."""

PITCH_SYSTEM = """You are the assignments desk for QUICKSAVE. Turn the
scout's research notes into story pitches. Use ONLY facts that appear in the
notes - never invent, embellish, or upgrade a rumor to confirmed. Copy source
titles and URLs exactly as written in the notes."""

PITCH_FORMAT = """Return a JSON array of {n} story candidates, each:
{{
  "topic": "short internal label",
  "section": "news|reviews|opinion|features",
  "why_now": "one sentence",
  "sensitive": false,
  "facts": [
    {{"fact": "...", "status": "confirmed|reported|rumor", "source_title": "...", "source_url": "..."}}
  ],
  "competing_coverage": "what everyone else's take is, so we can differ"
}}"""


def scout(n_candidates: int = 5) -> list[dict]:
    recent = recent_topics(CONFIG["duplicate_horizon_days"])
    recent_block = "\n".join(f"- {t}" for t in recent) or "(nothing yet)"

    # Step 1: grounded research, prose output - no JSON constraints.
    notes = ask(
        "scout", RESEARCH_SYSTEM,
        f"Find today's best story candidates for QUICKSAVE.\n\n"
        f"Recently covered (do NOT re-research these):\n{recent_block}",
        web_search=True, max_tokens=12000)

    # Step 2: structure the notes in strict JSON mode (valid JSON guaranteed).
    pitches = ask_json(
        "scout", PITCH_SYSTEM,
        "Research notes:\n" + notes + "\n\n" + PITCH_FORMAT.format(n=n_candidates),
        max_tokens=16000, schema=list[Pitch])
    return [p for p in pitches if p.get("facts")]
