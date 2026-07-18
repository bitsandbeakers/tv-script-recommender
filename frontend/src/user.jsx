// Current-user context: which profile is active, persisted in localStorage,
// plus that user's feedback map (show_id -> rating) for instant UI state.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api'

const UserContext = createContext(null)

const STORAGE_KEY = 'tvr_user_id'

export function UserProvider({ children }) {
  const [user, setUser] = useState(null)
  const [feedback, setFeedback] = useState({}) // show_id -> 1 | -1

  const loadFeedback = useCallback(async (userId) => {
    try {
      const items = await api.getFeedback(userId)
      const map = {}
      for (const item of items) map[item.show_id] = item.rating
      setFeedback(map)
    } catch {
      setFeedback({})
    }
  }, [])

  // Restore the active profile on first load
  useEffect(() => {
    const savedId = localStorage.getItem(STORAGE_KEY)
    if (!savedId) return
    api
      .getUser(savedId)
      .then((u) => {
        setUser(u)
        loadFeedback(u.id)
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY))
  }, [loadFeedback])

  const selectUser = useCallback(
    (u) => {
      setUser(u)
      if (u) {
        localStorage.setItem(STORAGE_KEY, u.id)
        loadFeedback(u.id)
      } else {
        localStorage.removeItem(STORAGE_KEY)
        setFeedback({})
      }
    },
    [loadFeedback]
  )

  const rate = useCallback(
    async (showId, rating) => {
      if (!user) return
      const current = feedback[showId]
      if (current === rating) {
        // Toggling the same rating off clears it
        setFeedback((f) => {
          const next = { ...f }
          delete next[showId]
          return next
        })
        await api.removeFeedback(user.id, showId).catch(() => {})
      } else {
        setFeedback((f) => ({ ...f, [showId]: rating }))
        await api.setFeedback(user.id, showId, rating).catch(() => {})
      }
      // Refresh aggregate like/dislike counts
      api.getUser(user.id).then(setUser).catch(() => {})
    },
    [user, feedback]
  )

  return (
    <UserContext.Provider value={{ user, feedback, selectUser, rate }}>
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  return useContext(UserContext)
}
