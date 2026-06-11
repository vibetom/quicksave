"""Scout agent: scours the web for what's worth writing about today."""

from __future__ import annotations

from .common import CONFIG, ask_json, recent_topics

SYSTEM = """You are the topic scout for QUICKSAVE, an autonomous video game
news and reviews site. Your job: use web search to find what is genuinely
worth covering RIGHT NOW, then pitch story candidates.

Rules:
- Search broadly: gaming news today, new releases this week, big reviews,
  industry developments, hardware, indie breakouts, esports.
- Prefer stories with momentum (announced/updated in the last 72 hours) and
  evergreen angles tied to current events.
- For each candidate, note which facts are CONFIRMED (official announcement)
  vs REPORTED/RUMORED (journalist sourcing, leaks) - the writer depends on
  this distinction.
- Record source URLs for every fact. The writer may only use facts you
  collected, so be thorough: dates, platforms, prices, names, direct context.
- Sensitive stories (layoffs, closures, controversies) are in scope, but flag
  them sensitive=true so the writer uses extra care.
- Never pitch a topic that substantially overlaps the recently-covered list.
"""

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
    user = (
        f"Find today's best story candidates for QUICKSAVE.\n\n"
        f"Recently covered (do NOT re-pitch these):\n{recent_block}\n\n"
        + PITCH_FORMAT.format(n=n_candidates)
    )
    pitches = ask_json("scout", SYSTEM, user, web_search=True, max_tokens=6000)
    return [p for p in pitches if p.get("facts")]
