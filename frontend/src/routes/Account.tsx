import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Me } from '../api/types'
import { ErrorNote, Panel } from '../components/ui'
import { Upgrade } from '../components/Upgrade'

const LABELS: Record<string, string> = {
  match: 'Match scores', roadmap: 'Roadmaps', advisor: 'Advisor messages',
  scam_check: 'Employer checks', jd_extract: 'Posting reads',
  interview_prep: 'Interview preps',
}

export function Account() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [confirm, setConfirm] = useState('')
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: () => api.get<Me>('/api/me') })

  const signOut = useMutation({
    mutationFn: () => api.post('/api/auth/logout'),
    onSuccess: () => {
      // Clear, not invalidate. The cached /api/me still says "signed in", and
      // the router reads that cache to decide whether to show the app. Leaving
      // it in place meant a signed-out user was redirected off /login and back
      // into their own data until the entry went stale.
      qc.clear()
      nav('/login', { replace: true })
    },
  })

  /** Export runs in the browser rather than as a download endpoint, so the
   *  file never exists on a server and the session cookie does the auth. */
  const exportData = useMutation({
    mutationFn: async () => {
      const data = await api.get<unknown>('/api/export')
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a')
      a.href = url; a.download = 'telos-export.json'; a.click()
      URL.revokeObjectURL(url)
    },
  })

  const destroy = useMutation({
    mutationFn: () => api.del('/api/account'),
    onSuccess: () => { qc.clear(); nav('/login', { replace: true }) },
  })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Account</h1>
          <p>{me?.email}</p>
        </div>
        <div className="right">
          <button className="btn ghost" onClick={() => signOut.mutate()}>Sign out</button>
        </div>
      </div>

      <ErrorNote error={signOut.error ?? exportData.error ?? destroy.error} />

      <div style={{ display: 'grid', gap: 20 }}>
        <Upgrade />

        <Panel title={`Plan: ${me?.plan_label ?? '—'}`}>
          <table className="data">
            <thead><tr><th>Feature</th><th>Used this month</th></tr></thead>
            <tbody>
              {Object.entries(me?.quotas ?? {}).map(([action, q]) => (
                <tr key={action}>
                  <td>{LABELS[action] ?? action}</td>
                  <td className="mono">
                    {q.used} / {q.limit < 0 ? '∞' : q.limit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Your data">
          <p style={{ fontSize: 13.5, marginBottom: 12 }}>
            Download everything Telos holds about you as JSON.
          </p>
          <button className="btn ghost" disabled={exportData.isPending}
                  onClick={() => exportData.mutate()}>
            {exportData.isPending ? 'Preparing…' : 'Export my data'}
          </button>
        </Panel>

        <Panel title="Delete this account">
          <p style={{ fontSize: 13.5, marginBottom: 12 }}>
            This removes your profile, resumes, pipeline, scores and roadmaps. It
            cannot be undone. Type <b>DELETE</b> to confirm.
          </p>
          <label className="field" style={{ maxWidth: 240 }}>
            <span>Confirm</span>
            <input value={confirm} onChange={e => setConfirm(e.target.value)} />
          </label>
          <button className="btn" disabled={confirm !== 'DELETE' || destroy.isPending}
                  style={{ background: 'var(--red)', color: '#2A0D0D' }}
                  onClick={() => destroy.mutate()}>
            {destroy.isPending ? 'Deleting…' : 'Delete my account'}
          </button>
        </Panel>
      </div>
    </>
  )
}
