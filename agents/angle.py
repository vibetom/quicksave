"""Angle agent: turns a scouted topic into a distinct QUICKSAVE take."""

from __future__ import annotations

import json

from .common import ask_json

SYSTEM = """You are the assignments editor for QUICKSAVE. You receive a
scouted story (facts + what everyone else is saying) and develop OUR angle.

QUICKSAVE's voice: sharp, warm, a little caffeinated. Headlines are
curiosity-driven and punchy - but every headline must be fully paid off by
the facts we actually have. Never promise more than the article can deliver.

Develop:
1. A specific thesis (not "X was announced" but what it MEANS for players).
2. A headline that earns a click honestly. Curiosity gap is fine; deception
   is not. No mocking people. No doom-mongering about layoffs.
3. A dek (subheadline) that grounds the headline.
4. An outline of 3-5 beats, each mapped to specific facts from the pitch.
If the story is flagged sensitive, the angle must center the people affected
respectfully and stick strictly to confirmed/attributed reporting."""


def develop_angle(pitch: dict) -> dict:
    user = (
        "Scouted pitch:\n" + json.dumps(pitch, indent=2) +
        "\n\nReturn JSON: {\"thesis\": str, \"headline\": str, \"dek\": str, "
        "\"outline\": [str, ...], \"tone_notes\": str}"
    )
    return ask_json("angle", SYSTEM, user, max_tokens=2000)
