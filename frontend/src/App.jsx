import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import BrowsePage from './pages/BrowsePage'
import ProfilePage from './pages/ProfilePage'
import SearchPage from './pages/SearchPage'
import ShowDetailPage from './pages/ShowDetailPage'
import { UserProvider, useUser } from './user'

function Nav() {
  const { user } = useUser()
  return (
    <nav className="nav">
      <NavLink to="/" className="nav-brand">
        📺 Script Recommender
      </NavLink>
      <div className="nav-links">
        <NavLink to="/" end>
          Search
        </NavLink>
        <NavLink to="/browse">Browse</NavLink>
        <NavLink to="/profile">{user ? `Profile (${user.name})` : 'Profile'}</NavLink>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <UserProvider>
      <BrowserRouter>
        <Nav />
        <main className="container">
          <Routes>
            <Route path="/" element={<SearchPage />} />
            <Route path="/browse" element={<BrowsePage />} />
            <Route path="/shows/:showId" element={<ShowDetailPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </main>
        <footer className="footer">
          Recommendations powered by script analysis — themes, tone, and dialogue style extracted from
          real transcripts.
        </footer>
      </BrowserRouter>
    </UserProvider>
  )
}
