// Show detail: full metadata, script-feature breakdown, and similar shows.

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import ShowCard from '../components/ShowCard'
import { useUser } from '../user'

const FEATURE_ROWS = [
  { key: 'themes', label: 'Themes' },
  { key: 'tone', label: 'Tone' },
  { key: 'humor_type', label: 'Humor' },
  { key: 'dialogue_style', label: 'Dialogue' },
  { key: 'emotional_register', label: 'Emotional register' },
  { key: 'genre_blend', label: 'Genre blend' },
]

export default function ShowDetailPage() {
  const { showId } = useParams()
  const { user, feedback, rate } = useUser()
  const [show, setShow] = useState(null)
  const [similar, setSimilar] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setShow(null)
    setSimilar(null)
    setError('')
    api
      .getShow(showId)
      .then(setShow)
      .catch((err) => setError(err.message))
    api
      .similarShows(showId, 6)
      .then((resp) => setSimilar(resp.results))
      .catch(() => setSimilar([]))
  }, [showId])

  if (error) return <p className="error">{error}</p>
  if (!show) return <p className="empty">Loading…</p>

  const f = show.features
  const rating = feedback[show.id]

  return (
    <div>
      <div className="detail-header">
        {show.poster_url ? (
          <img className="detail-poster" src={show.poster_url} alt={show.title} />
        ) : (
          <div className="detail-poster placeholder">
            <span>{show.title}</span>
          </div>
        )}
        <div className="detail-info">
          <h1>
            {show.title} {show.year ? <span className="card-year">({show.year})</span> : null}
          </h1>
          <p className="detail-meta">
            {[show.network, show.status, show.num_seasons ? `${show.num_seasons} seasons` : '', (show.genres || []).join(', ')]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {show.overview && <p className="detail-overview">{show.overview}</p>}
          {f?.style_summary && (
            <blockquote className="style-summary">
              <strong>Writing style:</strong> {f.style_summary}
            </blockquote>
          )}
          {user && (
            <div className="rate-row detail-rate">
              <button className={`rate-btn ${rating === 1 ? 'active-like' : ''}`} onClick={() => rate(show.id, 1)}>
                👍 Like
              </button>
              <button className={`rate-btn ${rating === -1 ? 'active-dislike' : ''}`} onClick={() => rate(show.id, -1)}>
                👎 Dislike
              </button>
            </div>
          )}
        </div>
      </div>

      {f && (
        <section>
          <h2 className="section-title">Script analysis</h2>
          <table className="feature-table">
            <tbody>
              {FEATURE_ROWS.filter((row) => (f[row.key] || []).length > 0).map((row) => (
                <tr key={row.key}>
                  <th>{row.label}</th>
                  <td>{f[row.key].join(', ')}</td>
                </tr>
              ))}
              {f.pacing && (
                <tr>
                  <th>Pacing</th>
                  <td>{f.pacing}</td>
                </tr>
              )}
              {f.narrative_structure && (
                <tr>
                  <th>Structure</th>
                  <td>{f.narrative_structure}</td>
                </tr>
              )}
              {f.vocabulary_complexity && (
                <tr>
                  <th>Vocabulary</th>
                  <td>{f.vocabulary_complexity}</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h2 className="section-title">Similar writing style</h2>
        {similar === null && <p className="empty">Finding similar shows…</p>}
        {similar && similar.length === 0 && <p className="empty">No similar shows found yet.</p>}
        {similar && similar.length > 0 && (
          <div className="grid">
            {similar.map((r) => (
              <ShowCard key={r.show.id} show={r.show} score={r.similarity_score} explanation={r.explanation} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
