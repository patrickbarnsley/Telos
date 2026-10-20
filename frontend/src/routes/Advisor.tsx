import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { Empty, ErrorNote, Panel } from '../components/ui'

export function Advisor() {
  const [msg, setMsg] = useState('')
  const [log, setLog] = useState<{ role: string; content: string }[]>([])
  const ask = useMutation({
    mutationFn: (m: string) => api.post<{ reply: string }>('/api/advisor', { message: m, history: log }),
    onSuccess: (r, m) => {
      setLog(l => [...l, { role: 'user', content: m }, { role: 'assistant', content: r.reply }])
      setMsg('')
    },
  })
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Advisor</h1>
          <p>Ask about your search. It answers from your resume, your pipeline and
             your roadmap, and it stays on that subject.</p>
        </div>
      </div>
      <ErrorNote error={ask.error} />
      <Panel>
        {log.length === 0 && <Empty>Nothing asked yet.</Empty>}
        {log.map((m, i) => (
          <div key={i} style={{
            marginBottom: 14, paddingLeft: m.role === 'user' ? 0 : 12,
            borderLeft: m.role === 'user' ? 'none' : '2px solid var(--gold)',
          }}>
            <div className="sub mono" style={{ fontSize: 10, letterSpacing: '.1em',
                 textTransform: 'uppercase', marginBottom: 3 }}>
              {m.role === 'user' ? 'You' : 'Advisor'}
            </div>
            <div style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>{m.content}</div>
          </div>
        ))}
        <label className="field" style={{ marginTop: 16 }}>
          <span>Your question</span>
          <textarea value={msg} onChange={e => setMsg(e.target.value)} style={{ minHeight: 80 }} />
        </label>
        <button className="btn" disabled={!msg.trim() || ask.isPending}
                onClick={() => ask.mutate(msg)}>
          {ask.isPending ? 'Thinking…' : 'Ask'}
        </button>
      </Panel>
    </>
  )
}
