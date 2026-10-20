import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { BillingState, OfferedPrice } from '../api/types'
import { ErrorNote } from '../components/ui'

/** Format what Stripe said, rather than what anyone typed.
 *
 *  Every amount on this screen comes from the Price object the checkout will
 *  actually charge against. Nothing here knows what Telos costs, which is the
 *  point: the screen and the charge cannot disagree.
 */
function money(cents: number | null, currency: string): string {
  if (cents == null) return ''
  const whole = cents % 100 === 0
  return new Intl.NumberFormat(undefined, {
    style: 'currency', currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100)
}

function cadence(p: OfferedPrice): string {
  if (!p.interval) return 'one time'
  if (p.interval_count > 1) return `every ${p.interval_count} ${p.interval}s`
  return `per ${p.interval}`
}

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

  // No configured prices means Telos is not charging. Show no paywall at all
  // rather than an upgrade panel with nothing behind it. A paywall that fails
  // closed costs a sale; one that fails open quotes a price nobody can pay.
  const prices = data.prices ?? []
  if (prices.length === 0) return null

  const founding = prices.find(p => p.kind === 'founding')
  const recurring = prices.find(p => p.kind === 'founding' || p.kind === 'monthly')
  const annual = prices.find(p => p.kind === 'annual')

  return (
    <section className="panel">
      <header className="panel-head"><h2>Upgrade to Pro</h2></header>
      <div className="panel-body">
        <ErrorNote error={checkout.error} />

        {founding && data.founding_seats_left > 0 && (
          <p style={{ marginBottom: 14, fontSize: 13.5 }}>
            <span className="chip chip-good" style={{ marginRight: 8 }}>
              <span className="glyph" aria-hidden="true">{'●'}</span>
              {data.founding_seats_left} founding{' '}
              {data.founding_seats_left === 1 ? 'seat' : 'seats'} left
            </span>
            <span style={{ color: 'var(--muted)' }}>
              {money(founding.amount_cents, founding.currency)} {cadence(founding)},
              locked for as long as you stay.
            </span>
          </p>
        )}

        <div style={{ display: 'grid', gap: 12,
                      gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))' }}>
          {recurring && (
            <div style={{ border: '1px solid var(--gold)', borderRadius: 10, padding: '15px 17px' }}>
              <b style={{ fontSize: 14 }}>{founding ? 'Founding' : 'Monthly'}</b>
              <div className="mono" style={{ fontSize: 26, margin: '4px 0 2px' }}>
                {money(recurring.amount_cents, recurring.currency)}
              </div>
              <span style={{ color: 'var(--muted)', fontSize: 12.5, display: 'block', marginBottom: 12 }}>
                {cadence(recurring)}{founding && ', locked'}
              </span>
              <button className="btn" style={{ width: '100%' }}
                      disabled={checkout.isPending}
                      onClick={() => checkout.mutate(false)}>
                {checkout.isPending ? 'Opening…' : 'Upgrade'}
              </button>
            </div>
          )}

          {annual && (
            <div style={{ border: '1px solid var(--hairline)', borderRadius: 10, padding: '15px 17px' }}>
              <b style={{ fontSize: 14 }}>Annual</b>
              <div className="mono" style={{ fontSize: 26, margin: '4px 0 2px' }}>
                {money(annual.amount_cents, annual.currency)}
              </div>
              <span style={{ color: 'var(--muted)', fontSize: 12.5, display: 'block', marginBottom: 12 }}>
                {cadence(annual)}
              </span>
              <button className="btn ghost" style={{ width: '100%' }}
                      disabled={checkout.isPending}
                      onClick={() => checkout.mutate(true)}>
                Upgrade
              </button>
            </div>
          )}
        </div>

        <p style={{ color: 'var(--muted)', fontSize: 12.5, marginTop: 14 }}>
          Cancel any time from this page. No card details ever reach Telos; checkout
          is handled by Stripe.
        </p>
      </div>
    </section>
  )
}
