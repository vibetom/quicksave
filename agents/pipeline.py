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
    pitches = scout(n_candidates=5)
    if not pitches:
        log("SCOUT: nothing publishable found.")
        return None

    for pitch in pitches:  # try candidates in order until one clears the desk
        log(f"ANGLE: developing take on '{pitch['topic']}'")
        angle = develop_angle(pitch)
        draft = write_article(pitch, angle)

        for attempt in range(CONFIG["cadence"]["max_retries_per_article"] + 1):
            verdict = edit_gate(draft, pitch)
            if verdict["pass"]:
                article = {
                    **draft,
                    "slug": slugify(draft["headline"]),
                    "published_at": now_iso(),
                    "byline": "QUICKSAVE editorial agents",
                }
                path = save_article(article)
                log(f"PUBLISH: {article['headline']}  -> {path.name}")
                rebuild_site()
                return article
            log(f"EDITOR: rejected ({len(verdict['issues'])} issues), "
                f"retry {attempt + 1}")
            pitch["_editor_feedback"] = verdict
            draft = write_article(pitch, develop_angle(pitch))
        log(f"DESK: '{pitch['topic']}' spiked after retries; trying next pitch.")
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
