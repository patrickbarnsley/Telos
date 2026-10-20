import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  DndContext, DragOverlay, PointerSensor, useSensor, useSensors,
  useDraggable, useDroppable, type DragEndEvent, type DragStartEvent,
} from '@dnd-kit/core'
import { api } from '../api/client'
import type { CompanyStat, Job, MatchResult, Status } from '../api/types'
import { Chip, Empty, ErrorNote, FitBar, Panel, StatStrip, STATUSES, statusLabel } from '../components/ui'

type View = 'board' | 'list' | 'companies'

function Card({ job, dragging }: { job: Job; dragging?: boolean }) {
  return (
    <div className={`card${dragging ? ' dragging' : ''}`}>
      <b>{job.role}</b>
      <span className="co">{job.company}</span>
      {job.location && <span className="co">{job.location}</span>}
    </div>
  )
}

function DraggableCard({ job }: { job: Job }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: job.id })
  return (
    <div ref={setNodeRef} {...listeners} {...attributes}
         role="button" tabIndex={0}
         aria-label={`${job.role} at ${job.company}, ${statusLabel(job.status)}`}>
      <Card job={job} dragging={isDragging} />
    </div>
  )
}

function Column({ status, jobs }: { status: Status; jobs: Job[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <div ref={setNodeRef} className={`col${isOver ? ' over' : ''}`}>
      <div className="col-head">
        <Chip status={status} />
        <span className="count mono">{jobs.length}</span>
      </div>
      {jobs.map(j => <DraggableCard key={j.id} job={j} />)}
    </div>
  )
}

export function Pipeline() {
  const qc = useQueryClient()
  const [view, setView] = useState<View>('board')

  // Only asked for when the tab is open. The query joins jobs to match_results
  // across the whole account, which is not worth running to render a board.
  const stats = useQuery({
    queryKey: ['job-stats'],
    queryFn: () => api.get<{ companies: CompanyStat[] }>('/api/jobs/stats'),
    enabled: view === 'companies',
  })
  const [active, setActive] = useState<Job | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.get<{ jobs: Job[] }>('/api/jobs'),
  })
  const jobs = data?.jobs ?? []

  // The Fit column showed "Not scored" for every row regardless of whether a
  // score existed, which is worse than showing nothing: it told the user their
  // scored roles were unscored. Joined on job_id, best score wins.
  const { data: matchData } = useQuery({
    queryKey: ['match'],
    queryFn: () => api.get<{ results: MatchResult[] }>('/api/match'),
  })
  const scoreFor = new Map<number, number>()
  for (const m of matchData?.results ?? []) {
    if (m.job_id == null || m.overall_score == null) continue
    const best = scoreFor.get(m.job_id)
    if (best === undefined || m.overall_score > best) scoreFor.set(m.job_id, m.overall_score)
  }

  /** Optimistic, because a drag that visibly snaps back while the server thinks
   *  is the single most common way a board feels broken. On failure the previous
   *  list is restored and the error surfaces. */
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Status }) =>
      api.patch(`/api/jobs/${id}`, { status }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ['jobs'] })
      const prev = qc.getQueryData<{ jobs: Job[] }>(['jobs'])
      qc.setQueryData<{ jobs: Job[] }>(['jobs'], old => old
        ? { jobs: old.jobs.map(j => (j.id === id ? { ...j, status } : j)) }
        : old)
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(['jobs'], ctx.prev) },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['jobs'] }) },
  })

  // A small distance constraint so a click on a card is not read as a drag.
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const onStart = (e: DragStartEvent) =>
    setActive(jobs.find(j => j.id === e.active.id) ?? null)

  const onEnd = (e: DragEndEvent) => {
    setActive(null)
    const to = e.over?.id as Status | undefined
    const job = jobs.find(j => j.id === e.active.id)
    if (!to || !job || job.status === to) return
    move.mutate({ id: job.id, status: to })
  }

  const counts = STATUSES.map(s => ({ s, n: jobs.filter(j => j.status === s).length }))
  const live = jobs.filter(j => ['screening', 'interview'].includes(j.status)).length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Pipeline</h1>
          <p>Every role you are pursuing, and what stage each one is at.</p>
        </div>
        <div className="right">
          <div className="seg" role="group" aria-label="View">
            <button aria-pressed={view === 'board'} onClick={() => setView('board')}>Board</button>
            <button aria-pressed={view === 'list'} onClick={() => setView('list')}>List</button>
            <button aria-pressed={view === 'companies'} onClick={() => setView('companies')}>Companies</button>
          </div>
        </div>
      </div>

      <StatStrip stats={[
        { label: 'Tracked', value: jobs.length },
        { label: 'In flight', value: live },
        { label: 'Offers', value: counts.find(c => c.s === 'offer')?.n ?? 0 },
        { label: 'Closed', value: jobs.filter(j => ['rejected', 'withdrawn'].includes(j.status)).length },
      ]} />

      <ErrorNote error={move.error ?? error} />

      {isLoading && <Empty>Loading your pipeline.</Empty>}
      {!isLoading && jobs.length === 0 && (
        <Empty>Nothing tracked yet. Add a role and it appears here.</Empty>
      )}

      {!isLoading && jobs.length > 0 && view === 'board' && (
        <DndContext sensors={sensors} onDragStart={onStart} onDragEnd={onEnd}>
          <div className="board">
            {STATUSES.map(s => (
              <Column key={s} status={s} jobs={jobs.filter(j => j.status === s)} />
            ))}
          </div>
          <DragOverlay>{active ? <Card job={active} /> : null}</DragOverlay>
        </DndContext>
      )}

      {!isLoading && jobs.length > 0 && view === 'list' && (
        <div className="panel">
          <table className="data">
            <thead>
              <tr><th>Role</th><th>Status</th><th>Location</th><th>Fit</th></tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id}>
                  <td><b>{j.role}</b><div className="sub">{j.company}</div></td>
                  <td><Chip status={j.status} /></td>
                  <td className="sub">{j.location || '—'}</td>
                  <td style={{ minWidth: 130 }}><FitBar score={scoreFor.get(j.id) ?? null} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === 'companies' && (
        <Panel title="By company">
          {stats.isLoading && <Empty>Working out the totals…</Empty>}
          {stats.data && stats.data.companies.length === 0 && (
            <Empty>Nothing tracked yet. Add a role and this fills in.</Empty>
          )}
          {stats.data && stats.data.companies.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Roles</th>
                    <th>Scored</th>
                    <th>Best fit</th>
                    <th>Last activity</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.data.companies.map(c => (
                    <tr key={c.company}>
                      <td>{c.company}</td>
                      <td className="mono">{c.total_applications}</td>
                      <td className="mono">{c.total_match_runs}</td>
                      <td style={{ minWidth: 120 }}>
                        <FitBar score={c.best_score} />
                      </td>
                      <td className="mono" style={{ color: 'var(--muted)' }}>
                        {c.last_activity ? String(c.last_activity).slice(0, 10) : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </>
  )
}
