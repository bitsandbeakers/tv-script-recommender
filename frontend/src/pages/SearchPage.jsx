// Main search page: natural-language query plus optional "more like these
// shows" anchors, with results rendered as a card grid.

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import ShowCard from '../components/ShowCard'

const EXAMPLE_QUERIES = [
  'dark comedy with razor-sharp dialogue',
  'slow-burn crime drama about moral descent',
  'mockumentary workplace comedy',
  'cerebral sci-fi with bleak twist endings',
]

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [anchors, setAnchors] = useState([]) // shows the results should be "more like"
  const [pickerText, setPickerText] = useState('')
  const [pickerResults, setPickerResults] = useState([])
  const [results, setResults] = useState(null)
  const [interpretation, setInterpretation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const pickerTimer = useRef(null)

  // Debounced title search for the anchor picker
  useEffect(() => {
    clearTimeout(pickerTimer.current)
    if (pickerText.trim().length < 2) {
      setPickerResults([])
      return
    }
    pickerTimer.current = setTimeout(() => {
      api
        .searchShows(pickerText.trim())
        .then((shows) => setPickerResults(shows.filter((s) => !anchors.some((a) => a.id === s.id)).slice(0, 6)))
        .catch(() => setPickerResults([]))
    }, 200)
    return () => clearTimeout(pickerTimer.current)
  }, [pickerText, anchors])

  const runSearch = useCallback(
    async (overrideQuery) => {
      const q = overrideQuery ?? query
      if (!q.trim() && anchors.length === 0) return
      setLoading(true)
      setError('')
      try {
        const resp = await api.recommend({
          query: q.trim(),
          liked_shows: anchors.map((a) => a.id),
          top_k: 12,
        })
        setResults(resp.results)
        setInterpretation(resp.query_interpretation)
      } catch (err) {
        setError(err.message)
        setResults(null)
      } finally {
        setLoading(false)
      }
    },
    [query, anchors]
  )

  return (
    <div>
      <section className="hero">
        <h1>Find shows by how they're written</h1>
        <p className="hero-sub">
          Search by tone, dialogue style, and themes extracted from actual scripts — not just genre tags.
        </p>
        <form
          className="search-form"
          onSubmit={(e) => {
            e.preventDefault()
            runSearch()
          }}
        >
          <input
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Describe what you want — "political satire with rapid-fire insults"'
          />
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>

        <div className="examples">
          {EXAMPLE_QUERIES.map((ex) => (
            <button
              key={ex}
              className="example-pill"
              onClick={() => {
                setQuery(ex)
                runSearch(ex)
              }}
            >
              {ex}
            </button>
          ))}
        </div>

        <div className="anchor-picker">
          <label className="anchor-label">More like:</label>
          {anchors.map((a) => (
            <span key={a.id} className="anchor-tag">
              {a.title}
              <button onClick={() => setAnchors(anchors.filter((x) => x.id !== a.id))}>×</button>
            </span>
          ))}
          <div className="anchor-input-wrap">
            <input
              className="anchor-input"
              value={pickerText}
              onChange={(e) => setPickerText(e.target.value)}
              placeholder="add a show you like…"
            />
            {pickerResults.length > 0 && (
              <ul className="anchor-dropdown">
                {pickerResults.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => {
                        setAnchors([...anchors, s])
                        setPickerText('')
                        setPickerResults([])
                      }}
                    >
                      {s.title} {s.year ? `(${s.year})` : ''}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      {results && (
        <section>
          <h2 className="section-title">
            Results <span className="interpretation">{interpretation}</span>
          </h2>
          {results.length === 0 ? (
            <p className="empty">No matches — the catalog may still be small. Try ingesting more shows.</p>
          ) : (
            <div className="grid">
              {results.map((r) => (
                <ShowCard
                  key={r.show.id}
                  show={r.show}
                  score={r.similarity_score}
                  explanation={r.explanation}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
