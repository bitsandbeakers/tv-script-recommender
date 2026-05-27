# TV Script Recommender — System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INGESTION LAYER                                │
│                                                                         │
│   ┌─────────────────┐      ┌──────────────────┐                        │
│   │  Path A:         │      │  Path B:          │                        │
│   │  OpenSubtitles   │      │  HuggingFace      │                        │
│   │  API             │      │  Dataset           │                        │
│   │                  │      │                    │                        │
│   │  ingest_show.py  │      │  ingest_from_hf.py │                        │
│   │  ingest_batch.py │      │                    │                        │
│   └────────┬─────────┘      └─────────┬──────────┘                       │
│            │                          │                                  │
│            ▼                          ▼                                  │
│   ┌────────────────┐       ┌────────────────────┐                        │
│   │ OpenSubtitles  │       │ IMDB episode.tsv.gz│                        │
│   │ /subtitles     │       │ (bulk download)    │                        │
│   │ /download      │       │         │          │                        │
│   └───────┬────────┘       │         ▼          │                        │
│           │                │ HuggingFace Hub    │                        │
│           ▼                │ bigscience/        │                        │
│   ┌──────────────┐         │ open_subtitles_    │                        │
│   │  SRT files   │         │ monolingual (en)   │                        │
│   │  on disk     │         └─────────┬──────────┘                        │
│   └──────┬───────┘                   │                                  │
│          │                           │                                  │
│          ▼                           │                                  │
│   ┌──────────────┐                   │                                  │
│   │  srt_parser  │                   │                                  │
│   │  (strip tags,│                   │                                  │
│   │   clean up)  │                   │                                  │
│   └──────┬───────┘                   │                                  │
│          │                           │                                  │
│          └──────────┬────────────────┘                                  │
│                     │                                                    │
│                     ▼                                                    │
│          ┌─────────────────────┐                                        │
│          │   Clean dialogue    │                                        │
│          │   text (combined    │                                        │
│          │   across episodes)  │                                        │
│          └──────────┬──────────┘                                        │
└─────────────────────┼───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PROCESSING PIPELINE                              │
│                                                                         │
│   ┌──────────────────┐                                                  │
│   │  chunk_script()  │  4000-char sliding window, 200-char overlap      │
│   └────────┬─────────┘                                                  │
│            │                                                            │
│            ▼                                                            │
│   ┌──────────────────────────────────────┐                              │
│   │  extract_and_merge_features()        │                              │
│   │                                      │                              │
│   │  1. Sample up to 5 chunks evenly     │                              │
│   │  2. Per chunk → EXTRACTION_PROMPT    │──── Anthropic API ──────┐    │
│   │     → Claude → JSON → ScriptFeatures │                         │    │
│   │  3. MERGE_PROMPT → Claude            │◄────────────────────────┘    │
│   │     → merged ScriptFeatures          │                              │
│   └────────┬─────────────────────────────┘                              │
│            │                                                            │
│            ▼                                                            │
│   ┌──────────────────────────────────────────┐                          │
│   │  ScriptFeatures                          │                          │
│   │  ├── themes       ["power", "family"]    │                          │
│   │  ├── tone         ["dark", "satirical"]  │                          │
│   │  ├── humor_type   ["dry wit"]            │                          │
│   │  ├── dialogue_style ["rapid-fire"]       │                          │
│   │  ├── emotional_register ["restrained"]   │                          │
│   │  ├── pacing       "fast"                 │                          │
│   │  ├── genre_blend  ["drama"]              │                          │
│   │  ├── narrative_structure "serialized"    │                          │
│   │  ├── vocabulary_complexity "dense"       │                          │
│   │  └── style_summary "Sharp prestige..."   │                          │
│   └────────┬─────────────────────────────────┘                          │
│            │                                                            │
│            ▼                                                            │
│   ┌──────────────────────────────┐                                      │
│   │  features_to_text()         │                                       │
│   │  → natural language string  │                                       │
│   │                             │                                       │
│   │  embed_text()               │  SentenceTransformer                  │
│   │  → 384-dim float vector     │  (all-MiniLM-L6-v2, local)           │
│   └────────┬─────────────────────┘                                      │
│            │                                                            │
└────────────┼────────────────────────────────────────────────────────────┘
             │
             │        ┌──────────────────────────────────────────────────┐
             │        │            METADATA ENRICHMENT                   │
             │        │                                                  │
             │        │   enrich_show(query, year, imdb_id)              │
             │        │        │                                         │
             │        │        ├──► TMDB API v3 (primary)                │
             │        │        │    /search/tv → /tv/{id}                │
             │        │        │    ?append_to_response=external_ids     │
             │        │        │                                         │
             │        │        └──► TVDB API v4 (fallback)               │
             │        │             /login → /search                     │
             │        │                                                  │
             │        │   Returns: title, year, network, genres,         │
             │        │   overview, poster_url, imdb_id, tmdb_id,        │
             │        │   tvdb_id, status, num_seasons, num_episodes     │
             │        └──────────────────────┬───────────────────────────┘
             │                               │
             ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                  │
│                                                                         │
│   ┌─────────────────────────┐    ┌──────────────────────────────────┐   │
│   │      ChromaDB           │    │          SQLite                  │   │
│   │   (chroma_data/)        │    │       (tvscripts.db)             │   │
│   │                         │    │                                  │   │
│   │  Collection: tv_scripts │    │  Table: shows                   │   │
│   │  Index: HNSW cosine     │    │  ├── id, title, year, network   │   │
│   │                         │    │  ├── genres, overview, poster    │   │
│   │  Per show:              │    │  ├── imdb_id, tmdb_id, tvdb_id  │   │
│   │  ├── 384-dim embedding  │    │  ├── status, num_seasons        │   │
│   │  └── metadata:          │    │  ├── num_episodes_analyzed      │   │
│   │      title, style_      │    │  └── features_json              │   │
│   │      summary, themes,   │    │      (serialized ScriptFeatures)│   │
│   │      tone, genre        │    │                                  │   │
│   └────────────┬────────────┘    └──────────────┬───────────────────┘   │
│                │                                │                      │
└────────────────┼────────────────────────────────┼──────────────────────┘
                 │                                │
                 ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       RECOMMENDATION ENGINE                             │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────┐           │
│   │                                                         │           │
│   │  recommend_by_text(query)                               │           │
│   │    embed query → cosine search ChromaDB                 │           │
│   │                                                         │           │
│   │  recommend_by_show(show_id)                             │           │
│   │    load features from SQLite → embed → cosine search    │           │
│   │                                                         │           │
│   │  recommend_blended(liked, disliked, query)              │           │
│   │    embed each liked show + query (weight 1.5x)          │           │
│   │    → weighted average embedding (L2 normalized)         │           │
│   │    → cosine search ChromaDB                             │           │
│   │    → penalize disliked (0.3 × max similarity penalty)   │           │
│   │    → re-rank                                            │           │
│   │                                                         │           │
│   └──────────────────────────┬──────────────────────────────┘           │
│                              │                                          │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI)                             │
│                          prefix: /api                                   │
│                                                                         │
│   Catalog                                                               │
│   ├── GET  /shows                  list all shows                       │
│   ├── GET  /shows/search?q=       title search                          │
│   ├── GET  /shows/{id}            show details + features               │
│   ├── DELETE /shows/{id}          remove show                           │
│   └── GET  /shows/{id}/enrich     pull TMDB/TVDB metadata               │
│                                                                         │
│   Recommendations                                                       │
│   ├── POST /recommend             text / similar / blended mode         │
│   └── GET  /recommend/{id}        similar shows shortcut                │
│                                                                         │
│   Metadata                                                              │
│   ├── GET  /lookup?q=             external metadata lookup              │
│   └── GET  /health                status + show count                   │
│                                                                         │
│   CORS: http://localhost:5173 (Vite dev server)                         │
└─────────────────────────────────────────────────────────────────────────┘


## External Services

┌──────────────────────┬────────────────────────────────────────────┐
│ Service              │ Purpose                                    │
├──────────────────────┼────────────────────────────────────────────┤
│ OpenSubtitles API    │ Search/download SRT subtitle files         │
│ HuggingFace Hub     │ Stream subtitle corpus (no API key needed) │
│ IMDB Datasets (TSV) │ Episode IMDB ID lookup for HF path         │
│ TMDB API v3         │ Show metadata enrichment (primary)         │
│ TVDB API v4         │ Show metadata enrichment (fallback)        │
│ Anthropic API       │ LLM feature extraction (Claude)            │
│ SentenceTransformer │ Local 384-dim embedding generation         │
└──────────────────────┴────────────────────────────────────────────┘


## Future: HuggingFace Enriched Dataset

data/subtitles/{show_id}/
├── S01E01.srt          (raw subtitles, Path A only)
├── dialogue.txt        (clean combined dialogue)
├── features.json       (extracted ScriptFeatures)
│
└── → Package into HF dataset with columns:
     show_id, title, year, network, genres, imdb_id,
     dialogue_text, features (JSON), embedding (384-dim)
