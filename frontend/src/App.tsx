import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from './api/client'
import type { Me } from './api/types'
import { Rail } from './components/Rail'
import { Auth } from './routes/Auth'
import { Account } from './routes/Account'
import { Pipeline } from './routes/Pipeline'
import { Match } from './routes/Match'
import { Prep } from './routes/Prep'
import { Roadmap } from './routes/Roadmap'
import { Advisor } from './routes/Advisor'
import { ProfilePage } from './routes/Profile'

export default function App() {
  const loc = useLocation()
  const { data: me, isLoading, error } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get<Me>('/api/me'),
    // A 401 is the expected answer for a signed-out visitor, not a fault worth
    // retrying. Anything else gets one retry.
    retry: (count, err) => !(err instanceof ApiError && err.status === 401) && count < 1,
  })

  const signedOut = error instanceof ApiError && error.status === 401
  const onAuthPage = ['/login', '/signup'].includes(loc.pathname)

  if (isLoading) return <div className="empty" style={{ paddingTop: 80 }}>Loading.</div>

  if (signedOut) {
    return (
      <Routes>
        <Route path="/signup" element={<Auth initial="signup" />} />
        <Route path="*" element={<Auth initial="login" />} />
      </Routes>
    )
  }

  // Signed in but sitting on an auth page: go where they were headed.
  if (onAuthPage) return <Navigate to="/" replace />

  return (
    <div className="app">
      <Rail me={me} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Pipeline />} />
          <Route path="/match" element={<Match />} />
          <Route path="/prep" element={<Prep />} />
          <Route path="/roadmap" element={<Roadmap />} />
          <Route path="/advisor" element={<Advisor />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/account" element={<Account />} />
          <Route path="*" element={<p className="empty">That page does not exist.</p>} />
        </Routes>
      </main>
    </div>
  )
}
