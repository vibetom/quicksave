"""Shared plumbing for the QUICKSAVE agent pipeline.

All model calls go through Google's Gemini API (google-genai SDK). The scout
uses Google Search grounding instead of a separate search tool; the other
agents run in plain JSON mode.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())
ARTICLE_DIR = ROOT / "content" / "articles"
ARTICLE_DIR.mkdir(parents=True, exist_ok=True)

_client = None


def client() -> genai.Client:
    """Singleton Gemini client. Requires GEMINI_API_KEY in the env."""
    global _client
    if _client is None:
        if not (os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")):
            raise RuntimeError(
                "Set GEMINI_API_KEY before running the pipeline, e.g.\n"
                "  export GEMINI_API_KEY=AIza..."
            )
        _client = genai.Client()
    return _client


def ask(model_key: str, system: str, user: str, *, web_search: bool = False,
        max_tokens: int = 4000, json_only: bool = False, schema=None) -> str:
    """One-shot call to Gemini. Returns the response text."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        # Structured editorial tasks don't need a thinking budget, and the
        # whole point of running on Flash is cost.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    if web_search:
        # Grounded generation: Gemini plans and runs the searches itself.
        config.tools = [types.Tool(google_search=types.GoogleSearch())]
    elif json_only:
        # JSON response mode can't be combined with search grounding,
        # so grounded calls rely on prompt + defensive parsing instead.
        config.response_mime_type = "application/json"
        if schema is not None:
            # Constrained decoding against a Pydantic schema — guarantees
            # syntactically valid JSON even when a field (e.g. body_markdown)
            # is full of quotes, newlines, and markdown.
            config.response_schema = schema
    resp = client().models.generate_content(
        model=CONFIG["models"][model_key], contents=user, config=config)
    # Detect truncation up front so a too-small budget surfaces as a clear
    # error instead of a cryptic "Expecting ',' delimiter" downstream.
    cand = (resp.candidates or [None])[0]
    finish = str(getattr(cand, "finish_reason", "") or "")
    if finish.rsplit(".", 1)[-1] == "MAX_TOKENS":
        raise RuntimeError(
            f"{model_key} hit the {max_tokens}-token output cap before "
            f"finishing — raise max_tokens for this call.")
    return resp.text or ""


def ask_json(model_key: str, system: str, user: str, **kw) -> dict | list:
    """Call Gemini expecting a JSON reply.

    Pass schema=<PydanticModel> for constrained decoding (guaranteed-valid
    JSON). Even so, parsing stays defensive — tolerant of markdown fences,
    leading/trailing prose, and unescaped control characters — and the call is
    retried once before giving up, since a stray malformed response shouldn't
    sink the run.
    """
    last_err = None
    for attempt in range(2):
        text = ask(model_key, system + "\nRespond with valid JSON only. "
                   "No prose, no markdown fences.", user, json_only=True, **kw)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0),
                    default=0)
        try:
            # raw_decode parses one value at `start` and ignores anything after
            # it; strict=False allows raw newlines/tabs inside string values.
            obj, _ = json.JSONDecoder(strict=False).raw_decode(text, start)
            return obj
        except json.JSONDecodeError as e:
            last_err = (e, text[max(0, e.pos - 200):e.pos + 200])
    e, ctx = last_err
    raise RuntimeError(
        f"{model_key} returned unparseable JSON ({e.msg} at char {e.pos}). "
        f"Context around the error:\n...{ctx}...") from e


def slugify(title: str) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:72] or "untitled"


def load_articles() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in sorted(ARTICLE_DIR.glob("*.json"))]
    arts.sort(key=lambda a: a["published_at"], reverse=True)
    return arts


def recent_topics(days: int) -> list[str]:
    """Headlines + topics published within the dedupe horizon."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    out = []
    for a in load_articles():
        ts = datetime.fromisoformat(a["published_at"]).timestamp()
        if ts >= cutoff:
            out.append(f"{a['topic']} :: {a['headline']}")
    return out


def save_article(article: dict) -> Path:
    path = ARTICLE_DIR / f"{article['slug']}.json"
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False))
    return path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
