import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { BillingState } from '../api/types'
import { ErrorNote } from '../components/ui'

/** The upgrade path, and the way out of it.
 *
 *  Two things stated plainly because hiding either is what makes people
 *  distrust a paywall: what the price actually is, and that cancelling takes
 *  one click and does not require emailing anyone.
 */
export function Upgrade() {
  const { data } = useQuery({
    queryKey: ['billing'], queryFn: () => api.get<BillingState>('/api/billing'),
  })

  const checkout = useMutation({
    mutationFn: (annual: boolean) =>
      api.post<{ url: string }>('/api/billing/checkout', { annual }),
    onSuccess: r => { window.location.href = r.url },
  })

  const portal = useMutation({
    mutationFn: () => api.post<{ url: string }>('/api/billing/portal'),
    onSuccess: r => { window.location.href = r.url },
  })

  if (!data) return null

  if (data.plan === 'pro') {
    return (
      <section className="panel">
        <header className="panel-head"><h2>Your plan</h2></header>
        <div className="panel-body">
          <ErrorNote error={portal.error} />
          <p style={{ fontSize: 14, marginBottom: 6 }}>
            You are on <b>{data.plan_label}</b>.
            {data.current_period_end && (
              <> Renews {String(data.current_period_end).slice(0, 10)}.</>
            )}
          </p>
          <p style={{ color: 'var(--muted)', fontSize: 13.5, marginBottom: 14 }}>
            Change your card, download invoices or cancel. Cancelling keeps every
            row of your data; only the monthly allowance goes back to Free.
          </p>
          <button className="btn ghost" disabled={!data.has_subscription || portal.isPending}
                  onClick={() => portal.mutate()}>
            {portal.isPending ? 'Opening…' : 'Manage billing'}
          </button>
        </div>
      </section>
    )
  }

  const founding = data.founding_seats_left > 0

  return (
    <section className="panel">
      <header className="panel-head"><h2>Upgrade to Pro</h2></header>
      <div className="panel-body">
        <ErrorNote error={checkout.error} />

        {founding && (
          <p style={{ marginBottom: 14, fontSize: 13.5 }}>
            <span className="chip chip-good" style={{ marginRight: 8 }}>
              <span className="glyph" aria-hidden="true">{'●'}</span>
              {data.founding_seats_left} founding {data.founding_seats_left === 1 ? 'seat' : 'seats'} left
            </span>
            <span style={{ color: 'var(--muted)' }}>$12 a month, locked for as long as you stay.</span>
          </p>
        )}

        <div style={{ display: 'grid', gap: 12,
                      gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))' }}>
          <div style={{ border: '1px solid var(--gold)', borderRadius: 10, padding: '15px 17px' }}>
            <b style={{ fontSize: 14 }}>Monthly</b>
            <div className="mono" style={{ fontSize: 26, margin: '4px 0 2px' }}>
              ${founding ? 12 : 19}
            </div>
            <span style={{ color: 'var(--muted)', fontSize: 12.5, display: 'block', marginBottom: 12 }}>
              per month{founding && ', locked'}
            </span>
            <button className="btn" style={{ width: '100%' }}
                    disabled={checkout.isPending}
                    onClick={() => checkout.mutate(false)}>
              {checkout.isPending ? 'Opening…' : 'Upgrade'}
            </button>
          </div>

          <div style={{ border: '1px solid var(--hairline)', borderRadius: 10, padding: '15px 17px' }}>
            <b style={{ fontSize: 14 }}>Annual</b>
            <div className="mono" style={{ fontSize: 26, margin: '4px 0 2px' }}>$190</div>
            <span style={{ color: 'var(--muted)', fontSize: 12.5, display: 'block', marginBottom: 12 }}>
              per year, two months off
            </span>
            <button className="btn ghost" style={{ width: '100%' }}
                    disabled={checkout.isPending}
                    onClick={() => checkout.mutate(true)}>
              Upgrade
            </button>
          </div>
        </div>

        <p style={{ color: 'var(--muted)', fontSize: 12.5, marginTop: 14 }}>
          Cancel any time from this page. No card details ever reach Telos; checkout
          is handled by Stripe.
        </p>
      </div>
    </section>
  )
}
