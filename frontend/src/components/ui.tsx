import type { Status } from '../api/types'

/** Status is a shape and a colour and a word, not just a colour.
 *
 *  The glyph is the point. The semantic pair is now separated by luminance, but
 *  colour alone still fails for a viewer who cannot see it at all, so each tone
 *  also carries a distinct mark. */
const TONE: Record<Status, { tone: string; label: string; glyph: string }> = {
  recruiter_outreach: { tone: 'neutral', label: 'Recruiter outreach', glyph: '○' },
  applied:            { tone: 'neutral', label: 'Applied',            glyph: '○' },
  screening:          { tone: 'neutral', label: 'Screening',          glyph: '◔' },
  interview:          { tone: 'live',    label: 'Interview',          glyph: '◑' },
  offer:              { tone: 'good',    label: 'Offer',              glyph: '●' },
  rejected:           { tone: 'bad',     label: 'Rejected',           glyph: '✕' },
  withdrawn:          { tone: 'neutral', label: 'Withdrawn',          glyph: '—' },
}

export const STATUSES = Object.keys(TONE) as Status[]
export const statusLabel = (s: Status) => TONE[s]?.label ?? s

export function Chip({ status }: { status: Status }) {
  const t = TONE[status] ?? { tone: 'neutral', label: String(status), glyph: '○' }
  return (
    <span className={`chip chip-${t.tone}`}>
      <span className="glyph" aria-hidden="true">{t.glyph}</span>{t.label}
    </span>
  )
}

export function FitBar({ score }: { score?: number | null }) {
  if (score === null || score === undefined) return <span className="sub">Not scored</span>
  const pct = Math.max(0, Math.min(100, Math.round(score)))
  const colour = pct >= 75 ? 'var(--green)' : pct >= 60 ? 'var(--amber)' : 'var(--red)'
  return (
    <div className="fitbar">
      <div className="track"><div className="fill" style={{ width: `${pct}%`, background: colour }} /></div>
      <span className="num mono">{pct}%</span>
    </div>
  )
}

export function Panel({ title, right, children }:
  { title?: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      {title && (
        <header className="panel-head">
          <h2>{title}</h2>
          {right && <div style={{ marginLeft: 'auto' }}>{right}</div>}
        </header>
      )}
      <div className="panel-body">{children}</div>
    </section>
  )
}

export function StatStrip({ stats }: { stats: { label: string; value: string | number }[] }) {
  return (
    <dl className="stat-strip">
      {stats.map(s => (
        <div className="stat" key={s.label}>
          <dt>{s.label}</dt><dd>{s.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const msg = error instanceof Error ? error.message : String(error)
  return <p className="err" role="alert">{msg}</p>
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="empty">{children}</p>
}
