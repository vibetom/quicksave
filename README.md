# QUICKSAVE — an autonomous video game news desk

A games site that runs itself. AI agents scout the web for what's worth
covering, develop a perspective, write original articles, edit them against
a standards checklist and a plagiarism gate, and rebuild the site — at least
10 articles a day, on their own.

```
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌───────────┐
│ SCOUT  │ → │ ANGLE  │ → │ WRITER │ → │ EDITOR │ → │ PUBLISHER │
│ web    │   │ thesis │   │ draft  │   │ gates  │   │ rebuild   │
│ search │   │ + hed  │   │ prose  │   │ ✓/✗    │   │ site      │
└────────┘   └────────┘   └────────┘   └────────┘   └───────────┘
```

## Quick start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python -m agents.pipeline once      # research + publish one article
python -m agents.pipeline batch 3   # publish three right now
python -m agents.pipeline daemon    # run forever: 10/day, spread 7:00–22:00

python site_builder/build.py        # rebuild site from existing content
python -m http.server -d public     # preview at http://localhost:8000
```

## How each agent works

| Agent | File | Job |
|---|---|---|
| Scout | `agents/scout.py` | Uses Claude's web search tool to find stories with momentum, collects facts **with sources** and a confirmed/reported/rumor status on each, and skips anything covered in the last 14 days. |
| Angle | `agents/angle.py` | Turns a pitch into a thesis, an honest-but-clicky headline, a dek, and an outline mapped to specific facts. |
| Writer | `agents/writer.py` | Drafts 450–700 words of original prose. Hard rules: facts from the pitch only, attribute reporting to the outlet that broke it, label rumors, never mock people. |
| Editor | `agents/editor.py` | **Two gates.** (1) A mechanical originality check: any 7-word run shared with a source, or >6% n-gram overlap, is a rejection with the offending passages quoted back. (2) An LLM standards review: hallucinated facts, rumor-as-fact, over-promising headlines, or disrespectful tone all fail the draft. Failed drafts are rewritten with the feedback, up to the retry limit, then spiked. |
| Publisher | `agents/pipeline.py` | Saves the article JSON, rebuilds the static site, and (in the daemon) sleeps a jittered interval so 10 articles spread naturally across the day. |

During development, the originality gate rejected one of this repo's own seed
articles for tracking Nintendo's announcement wording too closely. It was
rewritten. The gate is not decorative.

## Running it 24/7

**Option A — GitHub Actions (free, zero servers).** Push this repo to GitHub,
add `ANTHROPIC_API_KEY` as a repository secret, enable Pages (source: GitHub
Actions). `.github/workflows/newsroom.yml` fires 10 times a day, publishes one
article per run, commits the content, and deploys the site.

**Option B — any always-on box.**
```bash
nohup python -m agents.pipeline daemon >> newsroom.log 2>&1 &
```

**Option C — cron**, one article per slot:
```cron
30 7,9,10,12,13,15,16,18,19,21 * * * cd /path/to/quicksave && python -m agents.pipeline once
```

## Editorial standards (enforced in `config.json`)

- Original prose only — verified mechanically, not on the honor system.
- No invented quotes, dates, numbers, or details.
- Reporting is attributed to the outlet that did it; rumors are labeled rumors.
- Headlines can tease but must be fully paid off by the body.
- People are never mocked. Layoffs and closures are covered with care.
- Every page discloses AI authorship; every article lists its sources.

## Costs and dials

Each article costs roughly 4–8 Claude calls (scout search turns + angle +
draft + review, more on retries). Tune in `config.json`:

- `cadence.articles_per_day`, publish window hours
- `models.*` — defaults to `claude-sonnet-4-6`; drop the scout/editor to a
  smaller model to cut costs, or raise the writer for fancier prose
- `originality.*` — strictness of the plagiarism gate
- `duplicate_horizon_days` — how long a topic stays "covered"

For current model names and pricing, see https://docs.claude.com/en/api/overview

## Design notes

Dark indigo-charcoal base with a per-section hue system (news = cyan,
opinion = magenta, features = violet, reviews = gold) so the page color-codes
itself. Bricolage Grotesque display / Figtree body / JetBrains Mono utility.
Signature elements: the "wire" ticker streaming newsroom activity across the
top, and XP-bar read-time meters on every card. Reduced-motion preferences
are respected; the layout is responsive down to mobile.
