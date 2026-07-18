// Thin client for the FastAPI backend. All paths go through the Vite /api proxy in dev.

async function request(path, options = {}) {
  const resp = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail || detail
    } catch {
      // non-JSON error body
    }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  health: () => request('/health'),

  // Shows
  listShows: () => request('/shows'),
  searchShows: (q) => request(`/shows/search?q=${encodeURIComponent(q)}`),
  getShow: (id) => request(`/shows/${encodeURIComponent(id)}`),

  // Recommendations
  recommend: (body) =>
    request('/recommend', { method: 'POST', body: JSON.stringify(body) }),
  similarShows: (id, topK = 6) =>
    request(`/recommend/${encodeURIComponent(id)}?top_k=${topK}`),

  // Users & feedback
  createUser: (name) =>
    request('/users', { method: 'POST', body: JSON.stringify({ name }) }),
  listUsers: () => request('/users'),
  getUser: (id) => request(`/users/${encodeURIComponent(id)}`),
  getFeedback: (userId) => request(`/users/${encodeURIComponent(userId)}/feedback`),
  setFeedback: (userId, showId, rating) =>
    request(`/users/${encodeURIComponent(userId)}/feedback`, {
      method: 'PUT',
      body: JSON.stringify({ show_id: showId, rating }),
    }),
  removeFeedback: (userId, showId) =>
    request(`/users/${encodeURIComponent(userId)}/feedback/${encodeURIComponent(showId)}`, {
      method: 'DELETE',
    }),
  personalizedRecommendations: (userId, query = '', topK = 12) =>
    request(
      `/users/${encodeURIComponent(userId)}/recommendations?query=${encodeURIComponent(query)}&top_k=${topK}`
    ),
}
