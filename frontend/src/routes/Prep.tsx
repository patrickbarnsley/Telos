import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { InterviewPrep, MatchResult, PrepQuestion } from '../api/types'
import { Empty, ErrorNote, Panel } from '../components/ui'

/** Strength is the ordering signal, so it has to read at a glance.
 *  Weak first is deliberate: the questions you are least ready for are the ones
 *  worth the rehearsal time. */
const STRENGTH: Record<string, { cls: string; glyph: string; label: string }> = {
  weak:    { cls: 'bad',     glyph: '✕', label: 'Weak spot' },
  partial: { cls: 'live',    glyph: '◑', label: 'Partly covered' },
  strong:  { cls: 'good',    glyph: '●', label: 'Well covered' },
}

function Question({ q, n }: { q: PrepQuestion; n: number }) {
  const s = STRENGTH[q.strength ?? ''] ?? { cls: 'neutral', glyph: '○', label: q.strength ?? '' }
  return (
    <li style={{ paddingBottom: 18, marginBottom: 18, borderBottom: '1px solid var(--hairline)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 7, flexWrap: 'wrap' }}>
        <span className="mono" style={{ color: 'var(--muted)', fontSize: 12 }}>
          {String(n).padStart(2, '0')}
        </span>
        <b style={{ fontSize: 15, fontWeight: 600, flex: '1 1 260px' }}>{q.question}</b>
        {q.strength && (
          <span className={`chip chip-${s.cls}`}>
            <span className="glyph" aria-hidden="true">{s.glyph}</span>{s.label}
          </span>
        )}
      </div>

      {q.how_your_resume_answers && (
        <p style={{ fontSize: 13.5, marginBottom: 8 }}>{q.how_your_resume_answers}</p>
      )}

      {q.from_requirement && (
        <p style={{ fontSize: 12.5, color: 'var(--muted)', borderLeft: '2px solid var(--hairline)',
                    paddingLeft: 11 }}>
          From the posting: &ldquo;{q.from_requirement}&rdquo;
        </p>
      )}
    </li>
  )
}

export function Prep() {
  const { data } = useQuery({
    queryKey: ['match'],
    queryFn: () => api.get<{ results: MatchResult[] }>('/api/match'),
  })
  const results = data?.results ?? []
  const [chosen, setChosen] = useState<number | null>(null)

  const qc = useQueryClient()

  // Read before write. Prep already generated for this match is fetched rather
  // than regenerated: generating costs a quota credit, and charging someone a
  // second time to look at something they already own is indefensible.
  const existing = useQuery({
    queryKey: ['prep', chosen],
    queryFn: () => api.get<InterviewPrep>(`/api/match/${chosen}/interview-prep`),
    enabled: chosen !== null,
    retry: false,
  })

  const make = useMutation({
    mutationFn: (id: number) => api.post<InterviewPrep>(`/api/match/${id}/interview-prep`),
    onSuccess: data => qc.setQueryData(['prep', chosen], data),
  })

  const prep = make.data ?? existing.data
  const questions = prep?.questions ?? []
  const alreadyHave = !!existing.data?.questions?.length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Interview prep</h1>
          <p>The questions this posting is likely to ask, each traced to the line that
             produced it and answered from your own resume. Weakest first, because
             those are the ones worth rehearsing.</p>
        </div>
      </div>

      <ErrorNote error={make.error} />

      <Panel title="Pick a scored role">
        {results.length === 0 && <Empty>Score a role on Match first.</Empty>}
        {results.length > 0 && (
          <>
            <label className="field">
              <span>Scored roles</span>
              <select value={chosen ?? ''} onChange={e => setChosen(Number(e.target.value))}>
                <option value="" disabled>Choose one</option>
                {results.map(r => (
                  <option key={r.id} value={r.id}>
                    {(r.role || 'Untitled')}{r.company ? ` — ${r.company}` : ''} ({r.overall_score ?? '?'}%)
                  </option>
                ))}
              </select>
            </label>
            <button className="btn" disabled={!chosen || make.isPending}
                    onClick={() => chosen && make.mutate(chosen)}>
              {make.isPending ? 'Preparing…'
                : alreadyHave ? 'Prepare again' : 'Prepare questions'}
            </button>
            {alreadyHave && !make.isPending && (
              <p style={{ color: 'var(--muted)', fontSize: 12.5, marginTop: 9 }}>
                Showing the prep you already have for this role. Preparing again
                uses another credit.
              </p>
            )}
          </>
        )}
      </Panel>

      {prep?.injection_attempt && (
        <p className="err" role="alert" style={{ marginTop: 20 }}>
          This posting contained text aimed at steering the analysis: {prep.injection_attempt}
        </p>
      )}

      {questions.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Panel title={`${questions.length} likely questions`}>
            {prep?.note && (
              <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 16 }}>{prep.note}</p>
            )}
            <ol style={{ listStyle: 'none' }}>
              {questions.map((q, i) => <Question key={i} q={q} n={i + 1} />)}
            </ol>
          </Panel>
        </div>
      )}
    </>
  )
}
