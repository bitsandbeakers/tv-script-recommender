// Profile page: create/select a user, review feedback history, and get
// personalized recommendations built from that history.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import ShowCard from '../components/ShowCard'
import { useUser } from '../user'

export default function ProfilePage() {
  const { user, feedback, selectUser } = useUser()
  const [users, setUsers] = useState([])
  const [newName, setNewName] = useState('')
  const [recs, setRecs] = useState(null)
  const [recQuery, setRecQuery] = useState('')
  const [loadingRecs, setLoadingRecs] = useState(false)
  const [error, setError] = useState('')
  const [ratedShows, setRatedShows] = useState({}) // show_id -> ShowInfo

  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => {})
  }, [user])

  // Resolve titles for the feedback list
  useEffect(() => {
    const ids = Object.keys(feedback).filter((id) => !ratedShows[id])
    if (!ids.length) return
    Promise.all(ids.map((id) => api.getShow(id).catch(() => null))).then((shows) => {
      setRatedShows((prev) => {
        const next = { ...prev }
        for (const s of shows) if (s) next[s.id] = s
        return next
      })
    })
  }, [feedback, ratedShows])

  const createProfile = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    try {
      const u = await api.createUser(newName.trim())
      setNewName('')
      selectUser(u)
    } catch (err) {
      setError(err.message)
    }
  }

  const loadRecommendations = async () => {
    if (!user) return
    setLoadingRecs(true)
    setError('')
    try {
      const resp = await api.personalizedRecommendations(user.id, recQuery)
      setRecs(resp.results)
    } catch (err) {
      setError(err.message)
      setRecs(null)
    } finally {
      setLoadingRecs(false)
    }
  }

  const likedIds = Object.keys(feedback).filter((id) => feedback[id] === 1)
  const dislikedIds = Object.keys(feedback).filter((id) => feedback[id] === -1)

  return (
    <div>
      <h1>Profile</h1>

      <section className="profile-select">
        {users.length > 0 && (
          <div className="profile-row">
            <label>Active profile:</label>
            <select
              value={user?.id || ''}
              onChange={(e) => {
                const u = users.find((x) => x.id === e.target.value)
                selectUser(u || null)
                setRecs(null)
              }}
            >
              <option value="">— none —</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.num_liked} 👍 / {u.num_disliked} 👎)
                </option>
              ))}
            </select>
          </div>
        )}
        <form className="profile-row" onSubmit={createProfile}>
          <input
            className="anchor-input"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New profile name…"
          />
          <button className="btn-secondary" type="submit">
            Create profile
          </button>
        </form>
      </section>

      {error && <p className="error">{error}</p>}

      {!user ? (
        <p className="empty">
          Create or select a profile, then 👍/👎 shows anywhere in the app to build your taste profile.
        </p>
      ) : (
        <>
          <section>
            <h2 className="section-title">Your ratings</h2>
            {likedIds.length === 0 && dislikedIds.length === 0 ? (
              <p className="empty">
                No ratings yet — <Link to="/browse">browse the catalog</Link> and rate some shows.
              </p>
            ) : (
              <div className="ratings-columns">
                <div>
                  <h3>👍 Liked</h3>
                  <ul className="rating-list">
                    {likedIds.map((id) => (
                      <li key={id}>
                        <Link to={`/shows/${id}`}>{ratedShows[id]?.title || id}</Link>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3>👎 Disliked</h3>
                  <ul className="rating-list">
                    {dislikedIds.map((id) => (
                      <li key={id}>
                        <Link to={`/shows/${id}`}>{ratedShows[id]?.title || id}</Link>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </section>

          <section>
            <h2 className="section-title">Personalized recommendations</h2>
            <div className="profile-row">
              <input
                className="search-input"
                value={recQuery}
                onChange={(e) => setRecQuery(e.target.value)}
                placeholder="Optional: steer with a query, e.g. 'but funnier'"
              />
              <button className="btn-primary" onClick={loadRecommendations} disabled={loadingRecs}>
                {loadingRecs ? 'Thinking…' : 'Recommend for me'}
              </button>
            </div>
            {recs && recs.length === 0 && <p className="empty">Nothing to recommend yet — rate more shows.</p>}
            {recs && recs.length > 0 && (
              <div className="grid">
                {recs.map((r) => (
                  <ShowCard key={r.show.id} show={r.show} score={r.similarity_score} explanation={r.explanation} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
