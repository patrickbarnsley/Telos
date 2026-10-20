import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ErrorNote } from '../components/ui'

type Mode = 'login' | 'signup' | 'forgot'

/** One screen, three modes.
 *
 *  The reset flow deliberately says the same thing whether or not the address
 *  has an account. The API is enumeration-safe and the UI must not undo that by
 *  reporting "no such user" back to the caller.
 */
export function Auth({ initial = 'login' }: { initial?: Mode }) {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const [mode, setMode] = useState<Mode>(initial)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [sent, setSent] = useState(false)

  const next = params.get('next') || '/'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null); setBusy(true)
    try {
      if (mode === 'forgot') {
        await api.post('/api/auth/reset', { email })
        setSent(true)
      } else {
        await api.post(`/api/auth/${mode}`, { email, password })
        await qc.invalidateQueries()
        nav(next, { replace: true })
      }
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand" style={{ marginBottom: 6 }}>
          <span className="mark" aria-hidden="true" />Telos
        </div>
        <p className="sub" style={{ marginBottom: 22, color: 'var(--muted)', fontSize: 13.5 }}>
          {mode === 'login' && 'Know what to do next.'}
          {mode === 'signup' && 'Start free. No card.'}
          {mode === 'forgot' && 'We will send a link to set a new password.'}
        </p>

        <ErrorNote error={error} />

        {sent ? (
          <p style={{ fontSize: 14 }}>
            If that address has an account, a reset link is on its way. Check your inbox.
          </p>
        ) : (
          <>
            <label className="field">
              <span>Email</span>
              <input type="email" required autoComplete="email" value={email}
                     onChange={e => setEmail(e.target.value)} />
            </label>

            {mode !== 'forgot' && (
              <label className="field">
                <span>Password</span>
                <input type="password" required
                       autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                       value={password} onChange={e => setPassword(e.target.value)} />
              </label>
            )}

            <button className="btn" style={{ width: '100%' }} disabled={busy}>
              {busy ? 'One moment…'
                : mode === 'login' ? 'Sign in'
                : mode === 'signup' ? 'Create account'
                : 'Send reset link'}
            </button>
          </>
        )}

        <div className="auth-alt">
          {mode !== 'login' && (
            <button type="button" onClick={() => { setMode('login'); setSent(false); setError(null) }}>
              Sign in
            </button>
          )}
          {mode !== 'signup' && (
            <button type="button" onClick={() => { setMode('signup'); setSent(false); setError(null) }}>
              Create an account
            </button>
          )}
          {mode !== 'forgot' && (
            <button type="button" onClick={() => { setMode('forgot'); setSent(false); setError(null) }}>
              Forgot password
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
