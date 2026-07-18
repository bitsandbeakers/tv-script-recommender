# TV Script Recommender

TV show recommender powered by script/transcript analysis — themes, tone, and writing style matching.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   React UI  │────▶│  FastAPI API  │────▶│  ChromaDB   │
│  (Vite)     │◀────│              │◀────│  (vectors)  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │   Pipeline   │
                    │ ingest →     │
                    │ extract →    │
                    │ embed        │
                    └──────────────┘
```

**Data flow:** Scripts are ingested, chunked, analyzed by an LLM (Claude) to extract structured features (tone, themes, dialogue style, pacing, humor type, etc.), then embedded into vectors via sentence-transformers and stored in ChromaDB for cosine similarity search.

**Recommendation modes:**
- Natural language queries ("dark comedy with sharp dialogue like Succession")
- Similar-show lookup (find shows with matching writing style)
- Blended (query + liked/disliked show anchors)
- Personalized: per-user taste vector from 👍/👎 feedback, blended with an
  item-item collaborative signal (0.7 semantic / 0.3 collaborative), with
  candidates near disliked shows penalized

## Project Structure

```
backend/
  app.py              — FastAPI entry point
  api/routes.py       — API endpoints (shows, users, feedback, recommend)
  core/config.py      — Settings via pydantic-settings + .env
  models/schemas.py   — Pydantic models (features, users, requests, responses)
  pipeline/
    ingest.py         — Script loading and chunking
    extract.py        — LLM-based feature extraction
    embed.py          — Sentence-transformer embeddings
  recommender/
    engine.py         — Similarity search + ranking
    personalize.py    — Taste vectors + collaborative blending
  db/
    vector_store.py   — ChromaDB client
    show_store.py     — SQLite show catalog
    user_store.py     — SQLite users + feedback
  eval/
    metrics.py        — precision@k, recall@k, MRR, nDCG
    harness.py        — Runs evals against the live catalog
    data/ground_truth.json — Curated similar-show groups + query cases
frontend/             — React + Vite web app
scripts/              — CLI tools: ingestion, demo seed, evaluation
tests/                — pytest suite
```

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your Anthropic API key

# Run tests
pytest

# Seed a demo catalog (18 shows, no API keys needed)
python scripts/seed_demo.py

# Start the API server
uvicorn backend.app:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to the backend on :8000
```

Create a profile on the Profile page, then 👍/👎 shows anywhere in the app —
personalized recommendations are built from that feedback history.

## Evaluating Recommendation Quality

The eval harness scores the recommender against curated ground truth
(`backend/eval/data/ground_truth.json`): stylistically similar show groups
(each show should retrieve the others) and natural-language query cases.

```bash
python scripts/run_eval.py                 # per-case + mean metrics
python scripts/run_eval.py --k 5 10 20 --json report.json
```

Metrics: precision@k, recall@k, hit rate@k, MRR, and nDCG@k. Cases whose
shows aren't in the catalog yet are skipped and reported, so the harness is
useful even with a partial catalog. On the demo seed catalog the engine
scores ~1.0 MRR on text queries and ~0.78 MRR on similar-show retrieval.

## Feature Extraction Schema

Each show is analyzed across these dimensions:

| Dimension | Example Values |
|-----------|---------------|
| Themes | power, family dysfunction, class, identity |
| Tone | dark, satirical, warm, melancholic |
| Humor type | dry wit, slapstick, absurdist, observational |
| Dialogue style | rapid-fire, naturalistic, monologue-heavy, poetic |
| Emotional register | restrained, explosive, vulnerable, manic |
| Pacing | fast, slow-burn, variable |
| Genre blend | drama, comedy, thriller, sci-fi |
| Narrative structure | serialized, episodic, anthology |
| Vocabulary complexity | simple, moderate, dense |

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Vector store:** ChromaDB (local, persistent)
- **Metadata/users:** SQLite
- **Feature extraction:** Claude API (Anthropic)
- **Frontend:** React 18 + Vite + React Router
