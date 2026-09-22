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
| `GET /` | Scaffold page (real UI: FNA-17) |
| `GET /api/fighters?q=&limit=` | Working - autocomplete (FNA-7) |
| `GET /api/health` | Working - config and data-verification status |
| `POST /api/matchup` | 501, pending FNA-15 |

## Layout

```
app/
  __init__.py          application factory (FNA-6)
  routes.py            HTTP layer (FNA-7, FNA-15)
  data/
    fighters.json      fighter database (FNA-8)
    load_fighters.py   data-access layer (FNA-9)
  templates/           index.html (FNA-17)
  static/              style.css, app.js (FNA-22)
eval/                  harness and test cases (FNA-29, FNA-30)
```

Nothing outside `data/load_fighters.py` reads the JSON directly, so the storage
layer can move to SQLite without touching the rest of the app.

## Known gap

`fighters.json` currently holds **unverified placeholder statistics**. They
exercise the schema and autocomplete but are not accurate. They must be
re-sourced from ufcstats.com and flipped to `verified: true` before any scored
eval run, or fact-coverage and forbidden-claim scoring are meaningless.
`GET /api/health` reports this state.
