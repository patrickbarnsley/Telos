import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { MatchResult, ScamVerdict } from '../api/types'
import { Empty, ErrorNote, FitBar, Panel } from '../components/ui'
import { Verdict } from '../components/Verdict'

export function Match() {
  const qc = useQueryClient()
  const [jd, setJd] = useState('')
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')

  const { data } = useQuery({
    queryKey: ['match'],
    queryFn: () => api.get<{ results: MatchResult[] }>('/api/match'),
  })
  const results = data?.results ?? []

  // The scam check is separate from scoring on purpose. Someone who suspects a
  // posting wants to check the employer before spending a match credit on it.
  const scam = useMutation({
    mutationFn: () => api.post<ScamVerdict>('/api/match/scam-check', {
      company, jd_text: jd,
    }),
  })

  const score = useMutation({
    mutationFn: () => api.post<MatchResult>('/api/match', {
      jd_text: jd, company: company || null, role: role || null,
    }),
    onSuccess: () => { setJd(''); qc.invalidateQueries({ queryKey: ['match'] }) },
  })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Match</h1>
          <p>Paste a posting. Telos scores it against your resume, names what you
             already have, and names what is missing.</p>
        </div>
      </div>

      <ErrorNote error={scam.error ?? score.error} />

      <div style={{ display: 'grid', gap: 20, gridTemplateColumns: 'minmax(0,1fr)' }}>
        <Panel title="Score a posting">
          <label className="field">
            <span>Job description</span>
            <textarea value={jd} onChange={e => setJd(e.target.value)}
                      placeholder="Paste the full posting here." />
          </label>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <label className="field" style={{ flex: '1 1 180px' }}>
              <span>Company (optional)</span>
              <input value={company} onChange={e => setCompany(e.target.value)} />
            </label>
            <label className="field" style={{ flex: '1 1 180px' }}>
              <span>Role (optional)</span>
              <input value={role} onChange={e => setRole(e.target.value)} />
            </label>
          </div>
          <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
            <button className="btn" disabled={!jd.trim() || score.isPending}
                      onClick={() => score.mutate()}>
                {score.isPending ? 'Scoring…' : 'Score this role'}
              </button>
            <button className="btn ghost"
                    disabled={!jd.trim() || !company.trim() || scam.isPending}
                    onClick={() => scam.mutate()}
                    title={!company.trim() ? 'Add the company name to check the employer' : undefined}>
              {scam.isPending ? 'Checking\u2026' : 'Check this employer'}
            </button>
          </div>
        </Panel>

        {scam.data && (
          <Panel title="Employer check">
            <Verdict v={scam.data} />
          </Panel>
        )}

        {score.data && (
          <Panel title={`Result: ${score.data.overall_score ?? '—'}% fit`}>
            <div style={{ maxWidth: 420, marginBottom: 14 }}>
              <FitBar score={score.data.overall_score} />
            </div>
            <p style={{ marginBottom: 16 }}>{score.data.summary}</p>
            <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))' }}>
              <div>
                <h3 style={{ fontSize: 13, color: 'var(--green)', marginBottom: 7 }}>What you have</h3>
                <ul style={{ paddingLeft: 18, fontSize: 13.5 }}>
                  {(score.data.matched_requirements ?? []).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
              <div>
                <h3 style={{ fontSize: 13, color: 'var(--red)', marginBottom: 7 }}>What is missing</h3>
                <ul style={{ paddingLeft: 18, fontSize: 13.5 }}>
                  {(score.data.missing_requirements ?? []).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            </div>
          </Panel>
        )}

        <Panel title="Previous scores">
          {results.length === 0 && <Empty>Nothing scored yet.</Empty>}
          {results.length > 0 && (
            <table className="data">
              <thead><tr><th>Role</th><th>Fit</th><th>When</th></tr></thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.id}>
                    <td><b>{r.role || 'Untitled role'}</b><div className="sub">{r.company || ''}</div></td>
                    <td style={{ minWidth: 140 }}><FitBar score={r.overall_score} /></td>
                    <td className="sub mono">{(r.created_at || '').slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  )
}
