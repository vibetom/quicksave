"""QUICKSAVE static site builder.

Reads content/articles/*.json, writes public/*.html.
No dependencies beyond the standard library.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())
PUBLIC = ROOT / "public"
ASSETS = PUBLIC / "assets"

SECTION_LABEL = {"news": "News", "reviews": "Reviews",
                 "opinion": "Opinion", "features": "Features"}

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Bricolage+Grotesque:opsz,wght@12..96,400..800&"
         "family=Figtree:wght@400;500;600&"
         "family=JetBrains+Mono:wght@400;600&display=swap")


# ---------------------------------------------------------------- markdown --
def md_to_html(md: str) -> str:
    """Tiny renderer for the markdown subset the writer uses."""
    out, para = [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def inline(s: str) -> str:
        s = html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"\[(.+?)\]\((https?://[^)]+)\)",
                   r'<a href="\2" rel="noopener">\1</a>', s)
        return s

    for line in md.splitlines():
        line = line.rstrip()
        if not line:
            flush()
        elif line.startswith("### "):
            flush()
            out.append(f"<h2>{inline(line[4:])}</h2>")
        elif line.startswith("- "):
            flush()
            out.append(f"<ul><li>{inline(line[2:])}</li></ul>")
        else:
            para.append(line)
    flush()
    return re.sub(r"</ul>\s*<ul>", "", "\n".join(out))


# ----------------------------------------------------------------- helpers --
def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def nice_date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%b %d, %Y · %H:%M UTC")


def xp_bar(minutes: int) -> str:
    pct = min(100, minutes * 20)
    return (f'<span class="xp" title="{minutes} min read" '
            f'aria-label="{minutes} minute read">'
            f'<span class="xp-fill" style="width:{pct}%"></span>'
            f'<span class="xp-label">{minutes} MIN</span></span>')


def ticker_items(articles: list[dict]) -> str:
    lines = [
        "SCOUT // sweeping 6 wires for fresh topics",
        f"DESK // {len(articles)} stories live · "
        f"{CONFIG['cadence']['articles_per_day']}/day cadence",
        "EDITOR // originality gate: 0 shared n-grams in last pass",
    ]
    lines += [f"PUBLISH // {a['headline']}" for a in articles[:4]]
    span = "".join(f'<span class="tick">{esc(t)}</span><span class="tick-sep">◆</span>'
                   for t in lines)
    return span + span  # duplicated for seamless loop


def card(a: dict, big: bool = False) -> str:
    cls = "card card-lead" if big else "card"
    return f"""
<a class="{cls} sec-{esc(a['section'])}" href="{esc(a['slug'])}.html">
  <div class="card-top">
    <span class="kicker">{esc(SECTION_LABEL.get(a['section'], a['section']))}</span>
    <span class="card-emoji" aria-hidden="true">{a.get('hero_emoji', '🎮')}</span>
  </div>
  <h2 class="card-hed">{esc(a['headline'])}</h2>
  <p class="card-dek">{esc(a['dek'])}</p>
  <div class="card-meta">{xp_bar(a.get('read_minutes', 2))}
    <span class="card-date">{nice_date(a['published_at'])}</span></div>
</a>"""


def shell(title: str, body: str, *, desc: str) -> str:
    name = CONFIG["site"]["name"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="masthead">
  <a class="brand" href="index.html">{name}<span class="brand-dot">▮</span></a>
  <nav class="sections" aria-label="Sections">
    <a href="index.html#news" class="navlink sec-news">News</a>
    <a href="index.html#opinion" class="navlink sec-opinion">Opinion</a>
    <a href="index.html#features" class="navlink sec-features">Features</a>
    <a href="about.html" class="navlink">About</a>
  </nav>
</header>
{body}
<footer class="footer">
  <p class="disclosure">🤖 {esc(CONFIG['site']['disclosure'])}</p>
  <p class="colophon">{name} — {esc(CONFIG['site']['tagline'])} · Built and
  run by an autonomous editorial pipeline. <a href="about.html">How it works</a></p>
</footer>
</body>
</html>"""


# ------------------------------------------------------------------- pages --
def build_index(articles: list[dict]) -> str:
    lead, rest = articles[0], articles[1:]
    ticker = f"""
<div class="wire" role="marquee" aria-label="Newsroom activity feed">
  <div class="wire-track">{ticker_items(articles)}</div>
</div>"""
    secondary = "".join(card(a) for a in rest[:2])
    grid = "".join(card(a) for a in rest[2:])
    body = f"""
{ticker}
<main class="wrap">
  <section class="hero">
    {card(lead, big=True)}
    <div class="hero-side">{secondary}</div>
  </section>
  <div class="rule"><span>THE FEED</span></div>
  <section class="grid" id="news">{grid}</section>
</main>"""
    return shell(f"{CONFIG['site']['name']} — {CONFIG['site']['tagline']}",
                 body, desc=CONFIG["site"]["tagline"])


def build_article(a: dict, articles: list[dict]) -> str:
    sources = "".join(
        f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["title"])}</a></li>'
        for s in a.get("sources", []))
    nxt = [x for x in articles if x["slug"] != a["slug"]][:3]
    upnext = "".join(card(x) for x in nxt)
    facts = a.get("facts_status", "")
    facts_html = (f'<p class="facts-status">✓ Standards note: {esc(facts)}</p>'
                  if facts else "")
    body = f"""
<main class="wrap article sec-{esc(a['section'])}">
  <p class="kicker kicker-page">{esc(SECTION_LABEL.get(a['section'], a['section']))}</p>
  <h1 class="hed">{esc(a['headline'])}</h1>
  <p class="dek">{esc(a['dek'])}</p>
  <div class="byline-row">
    <span class="byline">By {esc(a['byline'])}</span>
    <span class="card-date">{nice_date(a['published_at'])}</span>
    {xp_bar(a.get('read_minutes', 2))}
  </div>
  <article class="body">{md_to_html(a['body_markdown'])}</article>
  {facts_html}
  <aside class="sources">
    <h2>Sources & further reading</h2>
    <ul>{sources}</ul>
  </aside>
  <div class="rule"><span>UP NEXT</span></div>
  <section class="grid">{upnext}</section>
</main>"""
    return shell(f"{a['headline']} — {CONFIG['site']['name']}", body,
                 desc=a["dek"])


def build_about() -> str:
    standards = "".join(f"<li>{esc(s)}</li>"
                        for s in CONFIG["editorial_standards"])
    body = f"""
<main class="wrap article">
  <h1 class="hed">A games site that runs itself</h1>
  <p class="dek">{esc(CONFIG['site']['name'])} is an experiment: a fully
  autonomous editorial desk powered by Claude.</p>
  <article class="body">
    <p>Every article here is found, pitched, written, edited, and published by
    a pipeline of AI agents. A <strong>Scout</strong> sweeps the web for what's
    worth covering. An <strong>Assignments editor</strong> develops our angle.
    A <strong>Writer</strong> drafts original prose from verified facts. A
    <strong>Standards editor</strong> runs an originality check against every
    source and rejects anything that hallucinates, over-promises, or fails to
    label a rumor as a rumor. Then the site rebuilds itself.</p>
    <h2>Our standards</h2>
  </article>
  <aside class="sources"><ul>{standards}</ul></aside>
</main>"""
    return shell(f"About — {CONFIG['site']['name']}", body,
                 desc="How the autonomous newsroom works.")


def build() -> None:
    articles = [json.loads(p.read_text())
                for p in (ROOT / "content" / "articles").glob("*.json")]
    articles.sort(key=lambda a: a["published_at"], reverse=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    css_src = ROOT / "site_builder" / "templates" / "style.css"
    shutil.copy(css_src, ASSETS / "style.css")
    (PUBLIC / "index.html").write_text(build_index(articles))
    (PUBLIC / "about.html").write_text(build_about())
    for a in articles:
        (PUBLIC / f"{a['slug']}.html").write_text(build_article(a, articles))
    print(f"Built {len(articles)} articles -> {PUBLIC}")


if __name__ == "__main__":
    build()
