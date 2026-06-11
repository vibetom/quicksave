"""Shared plumbing for the QUICKSAVE agent pipeline."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())
ARTICLE_DIR = ROOT / "content" / "articles"
ARTICLE_DIR.mkdir(parents=True, exist_ok=True)

_client = None


def client() -> anthropic.Anthropic:
    """Singleton Anthropic client. Requires ANTHROPIC_API_KEY in the env."""
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Set ANTHROPIC_API_KEY before running the pipeline, e.g.\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _client = anthropic.Anthropic()
    return _client


def ask(model_key: str, system: str, user: str, *, web_search: bool = False,
        max_tokens: int = 4000) -> str:
    """One-shot call to Claude. Returns concatenated text blocks."""
    kwargs = dict(
        model=CONFIG["models"][model_key],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": 6}]
    resp = client().messages.create(**kwargs)
    return "".join(b.text for b in resp.content if b.type == "text")


def ask_json(model_key: str, system: str, user: str, **kw) -> dict | list:
    """Call Claude expecting a JSON-only reply; strips code fences defensively."""
    text = ask(model_key, system + "\nRespond with valid JSON only. "
               "No prose, no markdown fences.", user, **kw)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=0)
    return json.loads(text[start:])


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
