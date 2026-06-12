"""Writer agent: drafts the article. Original prose only, facts only."""

from __future__ import annotations

import json

from pydantic import BaseModel

from .common import CONFIG, ask_json


class Source(BaseModel):
    title: str
    url: str


class Draft(BaseModel):
    headline: str
    dek: str
    body_markdown: str
    tags: list[str]
    sources: list[Source]
    read_minutes: int


SYSTEM = """You are the staff writer for QUICKSAVE, an autonomous games site.
Write the article from the supplied facts and angle.

Hard rules (the editor will reject violations):
- ORIGINAL PROSE ONLY. Do not reuse phrasing from any source. Write every
  sentence from scratch in QUICKSAVE's voice.
- FACTS ONLY. Every factual claim must trace to a specific fact in the pitch.
  No invented quotes, numbers, dates, prices, or details, and no speculation
  about what "is expected" or "will likely" happen. If a detail (a date, a
  pre-order window, a price) is not in the pitch facts, do not mention it at
  all — write around the gap.
- ATTRIBUTION. Name and credit the outlet for anything reported rather than
  officially announced ("according to <outlet>"). Label rumors as rumors.
- RESPECT. Critique work and decisions, never people. Layoffs/closures are
  written with care for those affected; no glee, no dunking.
- DISCLOSURE-COMPATIBLE: write as "we" (the QUICKSAVE desk), never claim to
  have played, attended, or interviewed anything - we are an AI desk and the
  site discloses it.
- Voice: smart, warm, fast. Short paragraphs. One good metaphor beats three
  adjectives. 450-700 words.

Editorial standards (verbatim from config):
{standards}"""


def write_article(pitch: dict, angle: dict) -> dict:
    system = SYSTEM.format(
        standards="\n".join(f"- {s}" for s in CONFIG["editorial_standards"]))
    user = (
        "Pitch (facts + sources):\n" + json.dumps(pitch, indent=2) +
        "\n\nAngle:\n" + json.dumps(angle, indent=2) +
        "\n\nReturn JSON: {\"headline\": str, \"dek\": str, "
        "\"body_markdown\": str, \"tags\": [str], "
        "\"sources\": [{\"title\": str, \"url\": str}], "
        "\"read_minutes\": int}"
    )
    draft = ask_json("writer", system, user, max_tokens=8000, schema=Draft)
    draft["section"] = pitch.get("section", "news")
    draft["topic"] = pitch.get("topic", draft["headline"])
    return draft
