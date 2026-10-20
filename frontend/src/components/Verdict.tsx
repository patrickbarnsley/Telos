import type { ScamVerdict } from '../api/types'

/** An employer verdict, shown as a shape and a word as well as a colour.
 *
 *  This is the part of Telos no competitor offers, so it earns real estate:
 *  the verdict is stated plainly, and the reasons are separated into what is
 *  reassuring and what is not, rather than blended into a paragraph.
 */
const TONE: Record<string, { cls: string; glyph: string; label: string }> = {
  legitimate:  { cls: 'good',    glyph: '●', label: 'Looks legitimate' },
  suspicious:  { cls: 'live',    glyph: '◑', label: 'Treat with caution' },
  likely_scam: { cls: 'bad',     glyph: '✕', label: 'Likely a scam' },
}

export function Verdict({ v }: { v: ScamVerdict }) {
  const t = TONE[v.verdict ?? ''] ?? { cls: 'neutral', glyph: '○', label: v.verdict ?? 'Unclear' }
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span className={`chip chip-${t.cls}`} style={{ fontSize: 13, padding: '5px 12px' }}>
          <span className="glyph" aria-hidden="true">{t.glyph}</span>{t.label}
        </span>
        {v.confidence && <span className="sub" style={{ color: 'var(--muted)', fontSize: 12.5 }}>
          {v.confidence} confidence
        </span>}
      </div>

      {v.summary && <p style={{ fontSize: 14, marginBottom: 16 }}>{v.summary}</p>}

      <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))' }}>
        {!!(v.red_flags ?? []).length && (
          <div>
            <h4 style={{ fontSize: 12.5, color: 'var(--red)', marginBottom: 7 }}>Reasons for concern</h4>
            <ul style={{ paddingLeft: 18, fontSize: 13.5, display: 'grid', gap: 6 }}>
              {v.red_flags!.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </div>
        )}
        {!!(v.green_flags ?? []).length && (
          <div>
            <h4 style={{ fontSize: 12.5, color: 'var(--green)', marginBottom: 7 }}>Reasons for confidence</h4>
            <ul style={{ paddingLeft: 18, fontSize: 13.5, display: 'grid', gap: 6 }}>
              {v.green_flags!.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
