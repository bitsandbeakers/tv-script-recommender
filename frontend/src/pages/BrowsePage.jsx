// Catalog browser: all indexed shows with client-side title filtering.

import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ShowCard from '../components/ShowCard'

export default function BrowsePage() {
  const [shows, setShows] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listShows()
      .then(setShows)
      .catch((err) => setError(err.message))
  }, [])

  const filtered = useMemo(() => {
    if (!shows) return []
    const f = filter.trim().toLowerCase()
    if (!f) return shows
    return shows.filter(
      (s) =>
        s.title.toLowerCase().includes(f) ||
        (s.genres || []).some((g) => g.toLowerCase().includes(f)) ||
        (s.network || '').toLowerCase().includes(f)
    )
  }, [shows, filter])

  return (
    <div>
      <div className="browse-header">
        <h1>Catalog</h1>
        <input
          className="search-input browse-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by title, genre, or network…"
        />
        {shows && (
          <span className="catalog-count">
            {filtered.length} of {shows.length} shows
          </span>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {!shows && !error && <p className="empty">Loading catalog…</p>}
      {shows && shows.length === 0 && (
        <p className="empty">
          The catalog is empty. Ingest shows with <code>python scripts/ingest_from_hf.py</code>.
        </p>
      )}

      <div className="grid">
        {filtered.map((s) => (
          <ShowCard key={s.id} show={s} />
        ))}
      </div>
    </div>
  )
}
