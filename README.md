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

## Project Structure

```
backend/
  app.py              — FastAPI entry point
  api/routes.py       — API endpoints (/health, /recommend)
  core/config.py      — Settings via pydantic-settings + .env
  models/schemas.py   — Pydantic models (features, requests, responses)
  pipeline/
    ingest.py         — Script loading and chunking
    extract.py        — LLM-based feature extraction
    embed.py          — Sentence-transformer embeddings
  recommender/
    engine.py         — Similarity search + ranking
  db/
    vector_store.py   — ChromaDB client
frontend/             — React + Vite (to be built)
scripts/              — CLI tools for batch ingestion
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

# Start the API server
uvicorn backend.app:app --reload
```

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
- **Feature extraction:** Claude API (Anthropic)
- **Frontend:** React + Vite (planned)
