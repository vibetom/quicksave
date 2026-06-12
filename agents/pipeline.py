"""Pipeline orchestrator.

  python -m agents.pipeline once       # research + publish one article
  python -m agents.pipeline batch 3    # publish three now
  python -m agents.pipeline daemon     # run forever, 10/day on a spread-out
                                       # schedule inside the publish window
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from datetime import datetime

from .angle import develop_angle
from .common import CONFIG, ROOT, now_iso, save_article, slugify
from .editor import edit_gate
from .scout import scout
from .writer import write_article


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def produce_one() -> dict | None:
    log("SCOUT: searching the wire...")
    try:
        pitches = scout(n_candidates=5)
    except Exception as e:
        # A scout hiccup (search timeout, truncated structuring) is a quiet
        # no-op for this slot, not a failed run — try again next slot.
        log(f"SCOUT: research failed ({e!r}); nothing published this run.")
        return None
    if not pitches:
        log("SCOUT: nothing publishable found.")
        return None

    for pitch in pitches:  # try candidates in order until one clears the desk
        try:
            article = _try_pitch(pitch)
            if article:
                return article
        except Exception as e:
            # One bad pitch (a garbled model response, a transient API error)
            # shouldn't sink the whole run — log it and move to the next.
            log(f"DESK: '{pitch.get('topic', '?')}' errored ({e!r}); next pitch.")
    return None


def _try_pitch(pitch: dict) -> dict | None:
    log(f"ANGLE: developing take on '{pitch['topic']}'")
    angle = develop_angle(pitch)
    draft = write_article(pitch, angle)

    # Newsroom revision loop: the editor sends the draft back with notes and
    # the writer revises (keeping the angle) until it's approved or we hit the
    # revision cap. A fatal verdict — the premise itself is unpublishable —
    # spikes the story immediately, no point revising.
    max_rev = CONFIG["cadence"]["max_revisions"]
    for rev in range(max_rev + 1):
        verdict = edit_gate(draft, pitch)
        if verdict["pass"]:
            article = {
                **{k: v for k, v in draft.items() if not k.startswith("_")},
                "slug": slugify(draft["headline"]),
                "published_at": now_iso(),
                "byline": "QUICKSAVE editorial agents",
            }
            path = save_article(article)
            log(f"PUBLISH: {article['headline']}  -> {path.name}")
            rebuild_site()
            return article
        if verdict.get("fatal"):
            reason = (verdict["issues"] or ["premise rejected"])[0]
            log(f"DESK: '{pitch['topic']}' spiked on premise — {reason}")
            return None
        if rev == max_rev:
            log(f"DESK: '{pitch['topic']}' spiked after {max_rev} revisions.")
            return None
        log(f"EDITOR: {len(verdict['issues'])} issue(s); back to the writer "
            f"(revision {rev + 1}/{max_rev})")
        draft = write_article(pitch, angle, prior_draft=draft,
                              feedback=verdict["fix"], issues=verdict["issues"])
    return None


def rebuild_site() -> None:
    subprocess.run([sys.executable, str(ROOT / "site_builder" / "build.py")],
                   check=True)
    log("SITE: rebuilt.")


def daemon() -> None:
    per_day = CONFIG["cadence"]["articles_per_day"]
    start = CONFIG["cadence"]["publish_window_start_hour"]
    end = CONFIG["cadence"]["publish_window_end_hour"]
    window = (end - start) * 3600
    base_gap = window / per_day
    log(f"DAEMON: {per_day}/day between {start}:00 and {end}:00.")
    while True:
        now = datetime.now()
        if start <= now.hour < end:
            try:
                produce_one()
            except Exception as e:  # keep the desk alive through bad runs
                log(f"ERROR: {e!r} - sleeping it off.")
            jitter = random.uniform(0.7, 1.3)  # human-ish irregularity
            time.sleep(base_gap * jitter)
        else:
            time.sleep(600)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "once"
    if cmd == "once":
        produce_one()
    elif cmd == "batch":
        for _ in range(int(sys.argv[2])):
            produce_one()
    elif cmd == "daemon":
        daemon()
    else:
        print(__doc__)
