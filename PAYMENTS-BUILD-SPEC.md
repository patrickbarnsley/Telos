# Brief for Claude Code: payments and the margin fix

Written by the cloud Claude session that holds the product context. Same working
agreement as BACKUP-FIX-BRIEF.md: you execute and report real output, it holds
the spec and checks the result. Say so explicitly if you want to change the
approach rather than changing it quietly.

Repo: `Telos-repo`, branch `main`, remote github.com/patrickbarnsley/Telos.
Do not push without showing Patrick the diff.

---

## Part 1 is urgent. Do it before payments.

Telos loses money on every heavy Pro subscriber right now. Every AI call runs on
`claude-opus-4-5` at $5/$25 per million tokens. Priced against the real token
shapes in `core/ai_engine.py` and the allowances in `core/plans.py`, a $19
subscriber at full utilisation costs **$34.08** to serve against **$18.02** of
net revenue after Stripe. Fifty such users is minus $821 a month.

Do not build a paywall on top of that.

### 1a. Per-action model routing

`core/ai_engine.py` already funnels every call through `_invoke`, and `MODEL` is
already an environment-configurable module constant. Extend it so the model is
chosen per action rather than globally.

    ACTION_MODELS = {
        "match":      "claude-haiku-4-5",
        "scam_check": "claude-haiku-4-5",
        "jd_extract": "claude-haiku-4-5",
        "roadmap":    "claude-sonnet-4-5",
        "advisor":    "claude-sonnet-4-5",
    }

Rules:

- `_invoke` already receives `action`. Resolve the model from `ACTION_MODELS`,
  falling back to the existing `MODEL` when the action is unknown.
- Each entry must be overridable by environment variable, following the existing
  `TELOS_AI_MODEL` pattern: `TELOS_AI_MODEL_MATCH`, `TELOS_AI_MODEL_ROADMAP` and
  so on. Same reason as before, tuning cost should not need a deploy.
- Verify the model ids resolve against real available models before committing.
  Do not assume the strings above are current; check, and report what you find.
- `core/spend.py` already prices per model, so the ledger stays correct with no
  change. Confirm that rather than assuming it.

**Expected result:** cost per fully-utilised subscriber falls from $34.08 to
about $8.63, a margin of roughly +$9.39 instead of -$16.06.

### 1b. Correct the allowances

In `core/plans.py`, Pro currently advertises 200 match scores and unlimited
advisor chat. Unlimited against a metered API is a promise that cannot be kept.

- Pro match scores: 200 to **100**
- Pro advisor messages: unlimited to **200**
- Pro roadmaps: unchanged at 10
- Free tier: unchanged. It costs $0.40 a month at full use and it is the entire
  acquisition engine.

Update the pricing table in `telos-site/index.html` and `README.md` to match.
`telos-site/` is gitignored; edit it but do not commit it.

### 1c. Raise the spend ceiling

`TELOS_AI_MONTHLY_CAP` default in `core/spend.py`: $40 to **$150**. The ceiling
exists to stop a runaway loop, not to cap growth. At $40 it trips around 100
heavy free users and cuts AI off for paying customers, which is worse than the
bill. Also set it in Parameter Store so the running instance picks it up.

---

## Part 2: payments

### Decisions already made. Do not relitigate these.

| Decision | Value |
|---|---|
| Provider | Stripe |
| Billing model | Pay-as-you-go, 0.7% of billing volume, no monthly contract |
| Pro monthly | $19 |
| Founding price | $12/month, locked for life, **hard cap of 50 subscribers** |
| Annual | $190 |
| Free trial of Pro | **None.** The free tier is the trial. |
| Tax | Stripe Tax Basic, API integration. Confirm current pricing before wiring it. |

### What to build

**Checkout.** Stripe Checkout in subscription mode, hosted by Stripe. Do not
build a card form. Telos must never see a card number, and hosted Checkout keeps
the PCI surface at zero.

**Founding-seat cap.** The $12 price is capped at 50 active subscribers, and the
cap must be enforced server-side at checkout creation, not in the UI. Count
active founding subscriptions before creating the session; past 50, create the
session at $19 instead. A cap that can be beaten by refreshing is not a cap.

**Webhooks.** Signature verification is mandatory. Handle at minimum:
`checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`, `invoice.payment_failed`,
`invoice.payment_succeeded`. Make the handler idempotent, Stripe retries and will
deliver the same event more than once.

**Plan gating.** `core/plans.py` already has tiers, per-action quotas and
`set_plan`. Wire Stripe state into that, do not build a parallel system. A
webhook that changes subscription status should end in a `set_plan` call.

**Billing portal.** Stripe's hosted customer portal for card updates,
cancellation and invoice history. Users must be able to cancel without emailing
anyone. Link it from Profile, then Account.

**Failed payments.** Configure Stripe's retry schedule. On final failure,
downgrade to free rather than deleting anything. Their data stays, their
allowance shrinks. Nobody loses a job search because a card expired.

**Schema.** New table for the Stripe linkage: `tester_name`, `stripe_customer_id`,
`stripe_subscription_id`, `status`, `price_id`, `current_period_end`,
`created_at`, `updated_at`. Add it to `init_db()` and to `USER_TABLES` in
`core/database.py` so account deletion still erases everything. Follow the
`ai_spend` precedent: financial records survive deletion with the identity
stripped, so decide and document which side this table falls on.

### Security requirements, non-negotiable

- Webhook signature verification on every request. An unverified webhook endpoint
  lets anyone grant themselves a subscription.
- Stripe keys go in Parameter Store, never the repo. `.gitignore` already covers
  `.env` and `*secrets*.txt`; confirm the new keys land there.
- Never log a full Stripe key, customer email, or the raw webhook body.
- The founding-seat count must be a database query at checkout time, never a
  cached number or a UI check.

### Tests

Extend `tests/` and keep `tests/run_all.py` passing. New suite, `test_payments.py`:

- webhook signature verification rejects an unsigned or wrongly-signed payload
- duplicate delivery of the same event does not double-apply
- `checkout.session.completed` moves the account to pro
- `customer.subscription.deleted` moves it back to free and keeps their data
- `invoice.payment_failed` at final attempt downgrades without deleting rows
- founding-seat cap holds at 50 under concurrent checkout creation
- a pro account gets pro quotas, a free account gets free quotas
- account deletion removes or anonymises the billing row as decided above

Run against a real PostgreSQL scratch database, same as the existing suites.
Use Stripe's test mode and their fixture events rather than hand-written JSON.

---

## Do not

- Do not touch `app.py` styling in this task. UI is a separate day.
- Do not run `deploy.ps1 -Step app` without saying why first.
- Do not rewrite commit authorship. These are Patrick's commits.
- Do not build a card form, store a card number, or handle a PAN anywhere.
- Do not commit `telos-site/`, `.env`, or any secrets file.

## Report back

For each of 1a, 1b, 1c and each item in Part 2: what you did, the real command
output, and anything you found that contradicts this spec. The spec was written
without access to the machine, so if something here is wrong, say so rather than
working around it silently.
