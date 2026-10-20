# Brief for Claude Code: React and FastAPI migration

Written by the cloud Claude session. Same agreement as the earlier briefs: you
execute and report real output, it holds the spec, and you contradict the spec
out loud rather than working around it.

**This runs in parallel with the live app. Streamlit keeps serving
app.usetelosapp.com untouched for the whole migration.** Nothing here may break
or block the September launch.

---

## Why this shape

Streamlit cannot be replaced incrementally. It owns the page lifecycle, the
session, and the routing, and it is currently also the backend: the pages import
`core/` directly and there is no API.

Two things make this cheaper than a normal rewrite, and both should be exploited
rather than redone.

**`core/` is already framework-agnostic.** `database.py`, `plans.py`,
`ai_engine.py`, `auth.py`, `spend.py` and `errors.py` know nothing about
Streamlit beyond a few `st.session_state` reads. That is the hard, dangerous,
well-tested part and it does not get rewritten. FastAPI wraps it.

**The design is already specified.** The prototype at
https://claude.ai/code/artifact/60989c58-a5da-4a69-afe0-088f3b876ac7 is real
HTML and CSS with the tokens, spacing, states and contrast ratios already
validated. Components lift from it. Do not redesign anything; if a question
about appearance comes up, the prototype is the answer.

---

## Architecture

    React (Vite, TypeScript)  ->  FastAPI  ->  core/*.py  ->  Postgres, Claude, Supabase
    served as static files        /api/*        unchanged

Caddy serves the built static files and proxies `/api/*` to FastAPI. Two
containers behind the one Caddy already running on the instance.

**Keep Python.** Do not port `core/` to TypeScript. Every security property
proven this week (owner scoping, quota enforcement, the spend choke point, the
prompt fencing, the coherence validator) lives there, and re-implementing it in
another language re-opens every one of them.

---

## Stage 1: the API, with no frontend

Build and verify this before writing any React.

`api/main.py`, FastAPI, one thin router per pillar. Every endpoint is a wrapper
over an existing `core/` function. If an endpoint needs logic that is not
already in `core/`, that logic belongs in `core/`, not the router.

Endpoints, grouped:

    POST   /api/auth/signup, /login, /logout, /reset, /reset/confirm
    GET    /api/me                       plan, quotas used, target role
    GET    /api/jobs                     list
    POST   /api/jobs                     create
    PATCH  /api/jobs/{id}                update
    DELETE /api/jobs/{id}
    GET    /api/profile, PUT /api/profile
    GET    /api/resumes, POST /api/resumes (multipart), PUT /api/resumes/{id}/active
    POST   /api/match                    score a job
    GET    /api/match/{id}
    POST   /api/match/{id}/interview-prep
    GET    /api/roadmap, POST /api/roadmap
    POST   /api/advisor                  one message
    GET    /api/export, DELETE /api/account

Rules:

- **Owner scoping is not optional.** Every handler resolves the account from the
  session and passes it to the `core/` function. Never accept an account
  identifier from the request body. The IDOR defects fixed earlier were exactly
  this mistake in a different shape.
- Errors go through `core/errors.py`. The API returns the friendly message and
  an HTTP status. Never a traceback, never a raw exception string.
- Quota checks stay in `core/plans.py`. The router calls `quota_gate`; it does
  not re-implement counting.
- File upload: accept the multipart body, hand bytes to `extract_resume_text`.
  Cap the upload size at the same limit `.streamlit/config.toml` uses.

**Auth.** Session cookie, `HttpOnly`, `Secure`, `SameSite=Lax`, carrying the
same hashed session token the app already issues. Do not put a JWT in
`localStorage`; an XSS then reads it. The `user_sessions` table and
`remember_session` / `resume_session` / `forget_session` already do the work.

**Verification before moving on:** every endpoint exercised with `curl` or
`httpx` against a real database, and a test suite `tests/test_api.py` covering
at minimum: unauthenticated access is refused, one account cannot read or write
another account's rows, quotas are enforced at the boundary, and account
deletion removes what it claims to.

---

## Stage 2: the React app

Vite, React, TypeScript. Keep the dependency list short: a router, a data
fetching library, and nothing else. No component framework; the prototype's CSS
is the design system and it is already written.

Structure:

    src/
      api/          typed fetch wrappers, one per endpoint group
      components/   Rail, TopBar, StatStrip, Chip, FitBar, Panel, DataTable
      routes/       Pipeline, Match, Roadmap, Advisor, Profile
      styles/       tokens.css lifted verbatim from the prototype

Lift the tokens exactly. The nine-colour palette, the type scale, the surface
hierarchy and the contrast ratios were all validated; retyping them by hand is
how a validated palette quietly stops being validated.

Build order, so there is always something working:

1. Shell: rail, top bar, routing, empty pages
2. Pipeline, read only, table view
3. Profile, including resume upload
4. Match, including scoring and interview prep
5. Roadmap and Advisor
6. The kanban board, drag and drop, which is now possible and was the thing
   Streamlit could not do

**Numbers are set in the monospace face with tabular figures.** That single
choice does more for how the app reads than anything else in the prototype.

---

## Stage 3: deployment, in parallel

- New subdomain `beta.usetelosapp.com`, its own Caddy block, its own DNS record.
- Streamlit at `app.usetelosapp.com` is untouched throughout. Do not modify the
  existing Caddyfile block, the existing container, or the app stack's
  UserData beyond adding the new block.
- Both hit the same database. A user can move between them without losing state,
  which also makes side-by-side comparison honest.
- Cut over by pointing `app` at the new service only when the whole checklist
  below passes.
- **Create `SITE_URL` in Parameter Store when `beta.usetelosapp.com` goes up.**
  It has never existed: the instance's env script only started reading it on
  2026-08-27, and the parameter itself was never created, so the app has always
  fallen back to its code default. Supabase builds confirmation and
  password-reset links from it, so until it is set to the beta origin, a
  password reset requested on beta emails the user a link into the Streamlit
  app. That is silent, it only shows up in someone's inbox, and "reset a
  password" on the checklist below will pass while doing the wrong thing unless
  you check which host the emailed link points at.

**Cutover checklist.** Every one of these, on beta, before touching `app`:
sign up, log in, log out, reset a password, upload a resume, set it active,
add a job, score it, generate an interview prep, generate a roadmap, ask the
advisor, hit a free limit and see the right message, export data, delete the
account. On a phone as well as a laptop.

---

## What must not change

- `core/` behaviour. Refactor signatures if genuinely needed, never semantics.
- The AI choke point. Every call still goes through `_invoke`, still checks the
  spend ceiling, still writes the ledger.
- The prompt fencing, the coherence validator, the injection detection.
- The nightly backup, the spend ceiling, the infrastructure templates.
- `tests/run_all.py` keeps passing. Add to it; do not replace it.

## Realistic schedule

Eight to ten working days, and the estimate assumes the API stage is genuinely
finished before React starts. Compressing that is how a migration produces two
half-built systems instead of one working one.

Nothing here blocks the 1 September paywall, because Streamlit keeps serving
until the checklist passes.

## Report back

Per stage: what you built, real output, and anything in this spec that turned
out to be wrong. It was written without access to the running system.
