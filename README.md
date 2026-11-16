# Fight Night Analyzer

CPSC 362 term project. A Flask web app that takes two active UFC fighters and
produces an AI-generated matchup analysis through a multi-stage LLM pipeline.

The app is the vehicle; the graded substance is the V1 - V4 pipeline iteration
study and the evaluation harness that measures whether each version actually
improved (epic FNA-4).

> Provisional README. The full version is FNA-33.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then fill in a key, or leave LLM_PROVIDER=demo
python main.py
```

Open http://127.0.0.1:5000

## Endpoints

| Route | Status |
|---|---|
| `GET /` | Working - the web page (FNA-3) |
| `GET /api/fighters?q=&limit=` | Working - autocomplete (FNA-7) |
| `GET /api/health` | Working - config and data-verification status |
| `POST /api/matchup` | Working - runs a matchup through the pipeline (FNA-15) |

`POST /api/matchup` takes `{"fighter_a": "<id>", "fighter_b": "<id>"}`, plus an
optional `"version"` (`v1`-`v4`, default `PIPELINE_VERSION`) and an optional
`"api_key"` (a user's own Groq key, used for that request only and never stored).
It returns both Stage 1 profiles, the Stage 2 analysis, and a `cross_division`
flag. Errors come back as `{"error": "<one plain sentence>"}`.

## Pipeline versions (FNA-14)

Each version adds one change to the one before it, so the eval (FNA-4) can tie
a score change to a single cause. Pick one with `PIPELINE_VERSION` in `.env`.

| Version | Change |
|---|---|
| v1 | Plain prompts (baseline) |
| v2 | + explains what each stat means, + gives Stage 2 both divisions |
| v3 | + Groq strict schema mode, + temperature 0 |
| v4 | + every key factor must cite the stats it rests on |

## Managing fighters

```bash
python manage.py list                                  # one line per fighter
python manage.py show islam-makhachev                  # full record
python manage.py add                                   # new fighter (asks for each field)
python manage.py result islam-makhachev win submission # after an event
python manage.py set islam-makhachev striking.slpm 2.41
python manage.py validate                              # check the whole file
```

Every change is validated before it is saved.

## Layout

```
app/
  __init__.py          application factory (FNA-6)
  routes.py            HTTP layer (FNA-7, FNA-15)
  data/
    fighters.json      fighter database (FNA-8)
    load_fighters.py   data-access layer (FNA-9)
  pipeline/
    schemas.py         output contracts for both stages (FNA-10, FNA-11)
    llm.py             provider client: Groq / demo (FNA-12)
    stage1.py          stats -> FighterProfile (FNA-12)
    stage2.py          two profiles -> MatchupAnalysis (FNA-13)
    guard.py           re-ask on bad output, user-facing errors (FNA-16)
    versions.py        v1 - v4 settings (FNA-14)
    dispatcher.py      run_matchup(): one call runs any version (FNA-14)
  templates/           index.html: page layout (FNA-17)
  static/              app.js: autocomplete, results, loading, errors (FNA-18 - 21)
                       style.css (FNA-22)
eval/                  harness and test cases (FNA-29, FNA-30)
manage.py              fighter database CLI
```

Nothing outside `data/load_fighters.py` reads or writes the JSON directly, so the storage
layer can move to SQLite without touching the rest of the app.

## Known gap

`fighters.json` currently holds **unverified placeholder statistics**. They
exercise the schema and autocomplete but are not accurate. They must be
re-sourced from ufcstats.com and flipped to `verified: true` before any scored
eval run, or fact-coverage and forbidden-claim scoring are meaningless.
`GET /api/health` reports this state.
