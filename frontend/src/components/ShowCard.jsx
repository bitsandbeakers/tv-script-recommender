// A show result card: poster (or generated placeholder), metadata, feature
// chips, optional similarity score, and like/dislike buttons when a user
// profile is active.

import { Link } from 'react-router-dom'
import { useUser } from '../user'
import FeatureChips from './FeatureChips'

function posterFallbackHue(title) {
  let hash = 0
  for (const ch of title) hash = (hash * 31 + ch.charCodeAt(0)) % 360
  return hash
}

export default function ShowCard({ show, score, explanation }) {
  const { user, feedback, rate } = useUser()
  const rating = feedback[show.id]

  return (
    <div className="card">
      <Link to={`/shows/${show.id}`} className="card-poster-link">
        {show.poster_url ? (
          <img className="card-poster" src={show.poster_url} alt={show.title} loading="lazy" />
        ) : (
          <div
            className="card-poster placeholder"
            style={{ background: `linear-gradient(160deg, hsl(${posterFallbackHue(show.title)}, 45%, 28%), hsl(${(posterFallbackHue(show.title) + 40) % 360}, 40%, 16%))` }}
          >
            <span>{show.title}</span>
          </div>
        )}
      </Link>
      <div className="card-body">
        <div className="card-title-row">
          <Link to={`/shows/${show.id}`} className="card-title">
            {show.title}
          </Link>
          {show.year ? <span className="card-year">{show.year}</span> : null}
        </div>
        {typeof score === 'number' && (
          <div className="score-row" title={`Similarity ${(score * 100).toFixed(1)}%`}>
            <div className="score-bar">
              <div className="score-fill" style={{ width: `${Math.round(score * 100)}%` }} />
            </div>
            <span className="score-label">{(score * 100).toFixed(0)}%</span>
          </div>
        )}
        <FeatureChips features={show.features} />
        {explanation ? <p className="card-explanation">{explanation}</p> : null}
        {user && (
          <div className="rate-row">
            <button
              className={`rate-btn ${rating === 1 ? 'active-like' : ''}`}
              onClick={() => rate(show.id, 1)}
              title="Like — improves your personalized recommendations"
            >
              👍
            </button>
            <button
              className={`rate-btn ${rating === -1 ? 'active-dislike' : ''}`}
              onClick={() => rate(show.id, -1)}
              title="Dislike — steers recommendations away from this"
            >
              👎
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
