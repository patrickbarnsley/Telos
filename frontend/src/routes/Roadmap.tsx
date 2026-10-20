import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Roadmap as R } from '../api/types'
import { Empty, ErrorNote, Panel } from '../components/ui'

export function Roadmap() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['roadmap'], queryFn: () => api.get<R>('/api/roadmap'),
  })
  const { data: prog } = useQuery({
    queryKey: ['roadmap-progress'],
    queryFn: () => api.get<{ progress: Record<string, boolean> }>('/api/roadmap/progress'),
  })
  const done = prog?.progress ?? {}

  const build = useMutation({
    mutationFn: () => api.post<R>('/api/roadmap'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roadmap'] }),
  })

  // Optimistic, because a checkbox that waits on a round trip before moving
  // feels broken even when it is working.
  const tick = useMutation({
    mutationFn: (v: { order: number; title: string; completed: boolean }) =>
      api.put('/api/roadmap/progress', {
        milestone_order: v.order, milestone_title: v.title, completed: v.completed,
      }),
    onMutate: async v => {
      await qc.cancelQueries({ queryKey: ['roadmap-progress'] })
      const prev = qc.getQueryData<{ progress: Record<string, boolean> }>(['roadmap-progress'])
      qc.setQueryData<{ progress: Record<string, boolean> }>(['roadmap-progress'], old => ({
        progress: { ...(old?.progress ?? {}), [String(v.order)]: v.completed },
      }))
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(['roadmap-progress'], ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['roadmap-progress'] }),
  })

  const ms = data?.milestones ?? []
  const completed = ms.filter((_, i) => done[String(i + 1)]).length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Roadmap</h1>
          <p>The shortest defensible path from where you are to the role you want.</p>
        </div>
        <div className="right">
          {ms.length > 0 && (
            <span className="mono" style={{ fontSize: 12.5, color: 'var(--muted)' }}>
              {completed} of {ms.length} done
            </span>
          )}
          <button className="btn" disabled={build.isPending} onClick={() => build.mutate()}>
            {build.isPending ? 'Building…' : ms.length ? 'Rebuild' : 'Build my roadmap'}
          </button>
        </div>
      </div>

      <ErrorNote error={build.error ?? tick.error} />

      {isLoading && <Empty>Loading.</Empty>}
      {!isLoading && ms.length === 0 && <Empty>No roadmap yet. Build one above.</Empty>}

      {ms.length > 0 && (
        <Panel title={data?.target_role || 'Your path'}>
          {data?.summary && <p style={{ marginBottom: 18 }}>{data.summary}</p>}
          <ul style={{ listStyle: 'none', display: 'grid', gap: 12 }}>
            {ms.map((m, i) => {
              const order = i + 1
              const isDone = !!done[String(order)]
              return (
                <li key={order}>
                  <label style={{
                    display: 'grid', gridTemplateColumns: '20px 1fr', gap: 12,
                    alignItems: 'start', cursor: 'pointer',
                    opacity: isDone ? .6 : 1,
                  }}>
                    <input type="checkbox" checked={isDone} style={{ marginTop: 4 }}
                           onChange={e => tick.mutate({
                             order, title: m.title, completed: e.target.checked })} />
                    <span>
                      <b style={{ fontSize: 14.5, fontWeight: 600,
                                  textDecoration: isDone ? 'line-through' : 'none' }}>
                        {m.title}
                      </b>
                      {m.detail && <span style={{ display: 'block', color: 'var(--muted)',
                                                  fontSize: 13.5, marginTop: 3 }}>{m.detail}</span>}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        </Panel>
      )}
    </>
  )
}
