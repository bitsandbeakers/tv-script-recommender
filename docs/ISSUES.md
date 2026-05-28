# Planned Issues

Tracking future work items for GitHub issue creation.

---

## 1. Neo4j integration for decoupled feature storage

**Labels:** enhancement, architecture

Replace the monolithic feature blob (SQLite JSON + single ChromaDB vector) with a
graph model where each feature dimension is its own set of nodes and relationships.
This makes adding new dimensions incremental — new edges, no re-extraction of
existing ones.

- Show/Season/Episode as nodes preserving the hierarchical extraction structure
- Per-dimension relationships: `(Show)-[:HAS_TONE]->(dark)`, `(Show)-[:HAS_THEME]->(power)`
- Similarity via graph traversal alongside existing vector search (hybrid)
- Per-dimension weighting as edge weights, updated from feedback signals
- Must conform to nox shared services infrastructure (Neo4j already running there)

**Depends on:** Migration to nox infrastructure

---

## 2. Migrate to nox shared services (Neo4j, Postgres, Plex)

**Labels:** enhancement, infrastructure

This project currently runs standalone with embedded storage (SQLite, ChromaDB).
It needs to migrate to the nox infrastructure where Neo4j, Postgres, and Plex
are already running as shared services.

- Replace SQLite show catalog with Postgres
- Add Neo4j for graph-based feature storage (see issue #1)
- ChromaDB may stay or be replaced depending on nox conventions
- Connect to Plex for library sync (see issue #6)
- Follow nox project conventions for service configuration, networking, and env vars
- Review nox repo for its service agreement/conventions before starting

**Blocked until:** Project lands on the nox machine

---

## 3. Re-extraction from saved dialogue

**Labels:** enhancement

Add `scripts/reextract.py --show-id <id>` that reads saved `dialogue.txt`,
rebuilds the `EpisodeDialogue` list from the `--- S01E02 ---` headers, re-runs
`extract_show_features`, and upserts both stores. No subtitle re-download needed.

- Parse the existing dialogue file format back into structured episodes
- Also expose as `POST /api/shows/{id}/reextract` endpoint
- Support `--all` flag for batch re-extraction across the catalog
- Use case: prompts changed, model upgraded, or full feature refresh needed

---

## 4. Targeted single-dimension extraction

**Labels:** enhancement

When a new field is added to `ScriptFeatures`, run a focused prompt against saved
dialogue for just that dimension and patch it into the existing record + re-embed.

- Decouple extraction prompts so each dimension can run independently
- Merge result into existing `features.json` without touching other dimensions
- Re-embed after patching
- Much lighter than full hierarchical re-extraction
- CLI: `scripts/reextract.py --show-id <id> --dimension tone`

**Depends on:** Issue #3 (re-extraction infrastructure)

---

## 5. Per-dimension weighted embedding

**Labels:** enhancement

Replace the flat `features_to_text` string (all dimensions equal) with a weighted
approach where each dimension's contribution to the final embedding is controllable.

- Store a weight vector (global or per-user)
- Apply weights when constructing the text representation before embedding
- Alternatively: embed dimensions separately and combine with weighted average
- Query-time parameter, not pre-computation — no re-indexing needed
- Default weights = equal; adjusted via feedback (see issue #6)

---

## 6. Weight update from feedback signals

**Labels:** enhancement

Use accumulated feedback from the feedback store to adjust per-dimension weights.

- Dimension-scoped feedback already captured: `POST /api/feedback` with `dimension` field
- Simple approach: bandit-style update — dimensions on liked shows get weight boost,
  dimensions on disliked shows get penalty
- More sophisticated: gradient-based update from like/dislike pairs
- Expose current weights via `GET /api/weights`
- Allow manual override via `PUT /api/weights`

**Depends on:** Issue #5 (per-dimension weighted embedding), feedback store (done)

---

## 7. Implicit feedback signals

**Labels:** enhancement

Track which recommendations are clicked/viewed vs skipped as a weaker signal
alongside explicit thumbs up/down.

- Log recommendation impressions (what was shown)
- Log click-throughs (what was selected)
- Skip = shown but not clicked within session
- Feed into weight update (issue #6) with lower confidence than explicit feedback

**Depends on:** Frontend (not yet built)

---

## 8. Plex library integration

**Labels:** enhancement, infrastructure

Periodic sync from Plex: auto-ingest shows present in the user's library but not
yet in the catalog. Plex is running as a shared service on the nox machine.

- Connect to Plex API to enumerate library
- Diff against show catalog
- Auto-queue ingestion for missing shows
- Periodic refresh (cron or manual trigger)
- Plex metadata can supplement TMDB/TVDB enrichment

**Depends on:** Issue #2 (migration to nox infrastructure)
