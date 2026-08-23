# Telos

> *Telos is the Greek word for ultimate purpose. The app helps you find and reach yours.*

**[usetelosapp.com](https://usetelosapp.com)** · **[Live demo — no signup](https://app.usetelosapp.com/?demo=1)** · **[Product case study](CASE-STUDY.md)**

Telos is a career campaign system for job seekers. Track every application, score your
resume against any job description with AI, and get a specific path to the role you
actually want.

---

## Why I built this

My wife went through a job transition and couldn't tell me which jobs had rejected her,
where she stood with any of them, or whether she was making progress. She was losing
confidence — not because she wasn't qualified, but because she had no system and no signal.

Plenty of people manage complex projects and pipelines all day at work, then run the
highest-stakes campaign of their life out of a spreadsheet and memory. Telos gives that
search the same structure, clarity, and honest feedback you'd demand from any other
serious project.

I'm also the second user. Every product decision here was made against a search I was
running myself.

---

## What it does

### Track
Log every job you're pursuing and move it through the pipeline — applied, screening,
interview, offer, rejected, withdrawn. Notes, contacts, posted vs. requested salary, and
the job description all live on the record. Funnel metrics update as you go.

### Match
Paste a job description and get scored against your active resume the way a real ATS
scores you. See which requirements you explicitly meet, which you miss, and which
certifications would close the gap. Telos also researches the employer and flags likely
scams before you spend time on an application.

### Guide
Get an ordered critical path from where you are to your target role — milestones with
timelines, concrete actions, and success criteria, built from your resume, your goals,
and your actual match history. An advisor chat lets you drill into any part of it.

---

## Product decisions

### The pivot: self-hosted → hosted

**v1 shipped self-hosted.** Each user cloned the repo, brought their own Anthropic API
key, and deployed their own instance. The reasoning was sound on paper: no auth to build,
no central database, no infrastructure bill, and users owned their own data.

**It was the wrong call, and the evidence was unambiguous.** Almost nobody who wanted to
use Telos got as far as using it. "Create an Anthropic account, generate an API key, fork
a repo, deploy it" is four steps of friction in front of a product whose value you can't
see until step five. The people it was built for — job seekers, mid-search, already
stressed — were exactly the people least willing to spend an evening on deployment.

**So the model changed.** Telos is now hosted, with accounts, a shared database, and the
AI cost absorbed on my side. Users sign up and it works.

What I'd take from it: I optimised v1 for *my* costs — build time, infrastructure, API
spend — and called it a user benefit. Data ownership was a real advantage, but it was
solving a problem my users didn't have yet, at the price of the one they did.

### Why the free tier is metered rather than unlimited

Every AI action has a marginal cost that I pay. An unlimited free tier on someone else's
API key isn't generous, it's just undated. Metering it makes the economics honest and
visible: tracking is unlimited because tracking is free to serve, and AI scoring is capped
because it isn't.

### Why the demo is read-only and pre-generated

A hiring manager or a curious job seeker shouldn't have to create an account to find out
what the product does. The demo account is fully populated with a fictional candidate's
pipeline, real match output, and a real roadmap. It costs nothing to serve because the AI
output is pre-generated and every write is blocked at the database layer, not at the
button — a single choke point rather than trusting each UI path to check.

### Why Match requires a linked job

You see a job, you log it, then you score it. Enforcing that order means every match
result is attached to a real job, the scam check always has a company to research, and
match history stays clean enough to be worth analysing later.

### What was cut, and why

| Feature | Decision | Reasoning |
|---|---|---|
| LinkedIn / Indeed scraping | Cut | Active bot detection, no public API, real legal risk. Naming the tradeoff is worth more than shipping a fragile scraper. |
| Auto-apply | Cut permanently | Floods employers with low-quality applications and hurts the people using it. Telos makes each application better, not more numerous. |
| Payments | Deferred | Pro is defined and priced, but takes a waitlist rather than a card. Wire Stripe when someone actually wants to pay, not before. |
| Browser extension | Roadmap | Right feature, wrong time. |
| AI resume tailoring | Roadmap | Natural next step once Match is validated. |
| Bring your own AI key | Roadmap | The optional version of the thing that failed as a requirement. |

---

## Pricing

| | Free | Pro — $9/mo |
|---|---|---|
| Job tracking | Unlimited | Unlimited |
| Pipeline metrics | Unlimited | Unlimited |
| AI match scores | 10 / month | 200 / month |
| Career roadmaps | 1 / month | 10 / month |
| Advisor chat | — | Unlimited |
| Employer scam checks | 10 / month | 200 / month |
| Outcome analytics | — | Included |

Pro is not taking payments yet. It exists as a defined tier with a waitlist so that
demand can be measured before payment infrastructure is built.

---

## Architecture

```
telos/
├── app.py                  # Landing, auth gate, demo entry, plan summary
├── pages/
│   ├── 0_Profile.py        # Resume upload, versioning, career paths
│   ├── 1_Track.py          # Job pipeline and funnel metrics
│   ├── 2_Match.py          # ATS scoring and employer checks
│   ├── 3_Guide.py          # Critical path and advisor chat
│   └── 4_Admin.py          # Usage analytics and outcome correlation
├── core/
│   ├── database.py         # All Postgres access; demo write-guard
│   ├── ai_engine.py        # Claude API wrapper — the only Claude-aware file
│   ├── auth.py             # Supabase email/password
│   ├── plans.py            # Tiers, usage metering, quota enforcement
│   ├── demo.py             # Read-only demo account and seed data
│   ├── models.py           # Job, Profile
│   └── app_styles.py       # Dark theme
└── requirements.txt
```

### Stack

| Layer | Choice | Why |
|---|---|---|
| UI + backend | Streamlit | Fast to ship, immediately demoable |
| Database | Supabase PostgreSQL | Persistent across deployments; migrated off SQLite when the app went multi-user |
| Auth | Supabase email/password | Managed sessions without building auth from scratch |
| AI | Anthropic Claude API | Isolated in `ai_engine.py` and swappable |
| Hosting | Streamlit Community Cloud | Free, GitHub-connected |

### The AI module

`ai_engine.py` is the only file that knows Claude exists. Everything else calls plain
functions:

```python
from core.ai_engine import score_match, generate_critical_path, chat_with_advisor
```

Prompt construction, API calls, response parsing, and error handling all live behind that
boundary. Swapping providers is a one-file change. That was intentional from day one.

### Data access

Every read and write in `database.py` is scoped to its owner. A row ID alone is never
sufficient to reach a row — `get_job(job_id, tester_name)`, not `get_job(job_id)` — so
that the boundary holds when the data layer is eventually put behind an HTTP API.

---

## Security

**What's protected today**

- Authentication is handled by Supabase; passwords are never stored by this app.
- Every query is parameterised. No string-interpolated SQL.
- Every row-level read and write is scoped to the owning account.
- API keys and the database URL live in Streamlit's encrypted secrets manager or a local
  `.env`, never in the repository.
- HTTPS is enforced by the host.
- AI usage is metered per account, so a single user cannot run up an unbounded bill.

**Honest limitations**

- Data is not encrypted at rest beyond what the managed Postgres provider does by default.
- There is no formal security audit. This is a solo project.
- The demo account is shared by every anonymous visitor by design. Nothing in it is real.

---

## Roadmap

**Next** — payments for Pro once the waitlist justifies it; AI resume tailoring per job
description; multi-resume comparison against a single posting.

**Later** — a React + FastAPI rebuild on AWS (App Runner, Amplify, S3, Cognito, Bedrock),
gated on the hosted version validating demand first. Building that infrastructure before
the product earns it would be premature scaling, and the current stack has not yet become
the constraint.

**Someday** — browser extension for capturing listings; community and peer accountability;
aggregated anonymised success-path data by role.

---

## Running it locally

Requires Python 3.10+, a Postgres database, an Anthropic API key, and a Supabase project.

```bash
git clone https://github.com/patrickbarnsley/Telos
cd Telos

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=your_key_here
DATABASE_URL=postgresql://user:password@host:5432/dbname
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_ANON_KEY=your_anon_key
OWNER_EMAILS=you@example.com
ADMIN_PASSWORD=choose_something
```

```bash
streamlit run app.py
```

Tables are created automatically on first run.

---

## About

Built by [Patrick Barnsley](https://linkedin.com/in/patrickbarnsley).

Telos exists because the job search is broken for candidates: no signal, no structure, no
honest feedback. It's built to change that.
