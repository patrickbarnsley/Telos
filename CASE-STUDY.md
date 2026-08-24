# Telos, Product Case Study

**Live:** [usetelosapp.com](https://usetelosapp.com) · **Demo, no signup:** [try it](https://app.usetelosapp.com/?demo=1) · **Code:** [github.com/patrickbarnsley/Telos](https://github.com/patrickbarnsley/Telos)

A career campaign system for job seekers. Built and shipped solo. This document
is about the decisions, including the ones I got wrong.

---

## The problem

My wife went through a job transition and couldn't tell me which companies had
rejected her, where she stood with any of them, or whether she was making
progress. She wasn't unqualified. She had no system and no signal, and the
absence of both was steadily costing her confidence.

That's the whole insight. Plenty of people manage complex pipelines all day at
work and then run the highest-stakes campaign of their life, their own career,
out of a spreadsheet and memory. The tooling that exists is either a glorified
to-do list or an auto-apply spam cannon. Nothing tells you *how you're actually
doing* or *what to fix*.

**Who has this problem:** mid-career people running a search of 20+ applications
over months, who care about targeting rather than volume. Not new grads applying
to 300 postings. Not executives working through recruiters.

I'm the second user. Every decision below was made against a search I was
running myself, which is the only reason I trust any of them.

---

## What it does

Three pillars, built in dependency order.

**Track**: every application in one pipeline, moving through applied →
screening → interview → offer → rejected → withdrawn. Notes, contacts, posted vs.
requested salary, and the job description live on the record. Funnel metrics
update as you go.

**Match**: paste a job description, get scored against your active resume the
way a real ATS scores you. Requirement-by-requirement breakdown of what you hit
and what you miss, specific certifications that would close the gap, and an
automatic employer legitimacy check before you invest time.

**Guide**: an ordered critical path from where you are to your target role.
Milestones with timelines, concrete actions, and success criteria, built from
your resume, your goals, and your actual match history. An advisor chat drills
into any part of it.

---

## Decisions

### Build order was a dependency graph, not a preference

Match needs a job to score against, so Track had to exist first. Guide uses
match history to build a smarter path, so Match had to exist before Guide. The
order wasn't taste; it was the only order that worked.

Sequencing this way also meant something usable shipped at every stage. Track
was valuable on day one, before any AI existed. Building all three in parallel
would have meant nothing usable for months and a high chance of shipping
nothing at all.

### Match scores are deliberately harsh

The engine is calibrated to real applicant tracking systems, which reject most
resumes. It only counts a requirement as met when the resume states it
explicitly, implied experience doesn't count. Temperature is set to zero so the
same resume and posting always produce the same score.

Users score lower than they expect and it doesn't feel good. That's the point.
A flattering score is worse than no score, because it costs you an application
you can't take back. The honest number is the product.

### Match requires a linked job

You see a job, you log it, then you score it. Enforcing that order means every
match result attaches to a real job, the scam check always has a company to
research, and the match history stays clean enough to analyse later. It adds a
step. It's worth the step.

### Auto-apply is cut permanently, not deferred

Every competitor in this space is racing toward one-click mass application. It
floods employers with low-quality applications and actively harms the people
using it, it's the mechanism that made the funnel this bad in the first place.
Telos makes each application better rather than making more of them. This is the
one roadmap item I'd refuse on principle rather than on sequencing.

### Job board scraping was cut for reasons worth naming

LinkedIn and Indeed run active bot detection and offer no public API. Building
this would have meant a fragile scraper with real legal exposure, on the
critical path of a product that hadn't validated anything yet. Cutting it cost
the most-requested feature. Naming *why* is more useful than shipping something
that breaks quietly.

---

## The pivot I got wrong first

**v1 shipped self-hosted.** Each user would clone the repo, bring their own
Anthropic API key, and deploy their own instance. On paper the reasoning was
clean: no auth to build, no central database, no infrastructure bill, and users
own their own data.

**It was wrong, and the evidence was unambiguous.** Almost nobody who wanted to
use Telos ever used it. "Create an Anthropic account, generate an API key, fork
a repo, deploy it" is four steps of friction in front of a product whose value
you cannot see until step five. The people it was built for, job seekers,
mid-search, already stressed, were precisely the people least willing to spend
an evening on deployment.

**So the model changed.** Telos is now hosted, with accounts, a shared database,
and the AI cost absorbed on my side. You sign up and it works.

What I take from it: I had optimised v1 for *my* costs, build time,
infrastructure, API spend, and told myself it was a user benefit. Data
ownership was a genuine advantage, but it solved a problem my users didn't have
yet, at the price of the one they did.

---

## Pricing without payments

Free tier: unlimited tracking, 10 AI match scores a month, one roadmap.
Pro at $19: 200 match scores, 10 roadmaps, unlimited advisor chat.

**Pro is defined, priced, and public, and takes a waitlist instead of a card.**

Two reasons. Metering is honest about the economics: tracking is unlimited
because tracking costs nothing to serve, and AI scoring is capped because it has
a real marginal cost I pay. An unlimited free tier on someone else's API key
isn't generous, it's just undated.

The price moved from $9 to $19 before launch. $9 was set by instinct rather
than by looking, and a survey of the field put comparable tools at $29 to $50.
Undercutting by 70 percent does not read as a bargain, it reads as a lesser
product, and it makes the later correction look like a price rise rather than
a correction. Pricing below the market is a decision, not a default, and I had
not actually decided it.

And building payments means Stripe, a refund policy, terms of service, and a
privacy policy that actually matters because I'm holding other people's resumes.
That's a week of work and a permanent support obligation, in exchange for
revenue from a product whose demand I haven't measured. The waitlist measures
the demand for the price of an afternoon.

---

## The infrastructure decision

Worth including because it's the clearest example of costing a decision rather
than reaching for the impressive option.

The app needed a custom domain, which the free host didn't support. The plan of
record was AWS App Runner.

**App Runner doesn't work here.** Streamlit drives its entire UI over a
WebSocket, and App Runner doesn't proxy WebSockets, the container passes health
checks and the browser hangs on a loading spinner permanently. Found by testing
the upgrade handshake directly rather than by deploying and wondering.

**So I built ECS Fargate behind an Application Load Balancer**, which handles
the upgrade correctly. It worked. Then I costed it: **$47.65/month**, of which
the load balancer and its public IP addresses were $24.73, more than half the
bill, to load-balance a single container.

**I moved to one Graviton EC2 instance running Docker and Caddy: $18.16/month.**
Caddy terminates TLS, renews certificates itself, and proxies WebSockets
natively, which removes the entire reason the load balancer existed. Same
availability profile for a single-container app, more memory than the Fargate
task had, 62% cheaper.

Both templates are in the repo. The Fargate one is kept at
`infra/reference/` with a header recording why it wasn't chosen and the specific
conditions that would justify going back: more than one task, zero-downtime
deploys mattering, or a single reboot becoming an unacceptable outage.

---

## What I got wrong

The section that matters most.

**I under-costed my own infrastructure.** My first estimate for the Fargate
build was $36.70/month. The real figure was $47.65. I'd omitted AWS's charge for
public IPv4 addresses, and that architecture quietly used three of them. An
11-dollar-a-month error on a bill I'd explicitly gone and looked up.

**The README drifted badly.** For months it documented SQLite, claimed the app
had no authentication, and told users to bring their own API key, after all
three had stopped being true. It was also backslash-escaped throughout, so it
rendered as literal markdown source on GitHub. The single file most likely to be
read by someone evaluating the project was both wrong and visibly broken, and I
didn't notice because I never read my own README.

**The data layer had unscoped queries.** Seven functions accepted a row ID with
no owner check, `get_job(job_id)` rather than `get_job(job_id, user)`. Not
exploitable through the UI, because IDs only ever came from the user's own
scoped lists. It would have become a real vulnerability the moment those IDs
arrived over HTTP, which is exactly what the planned API rewrite does. Caught and
fixed while it was still cheap.

**I set a validation gate and never defined it.** "Rebuild once demand is
validated" is not a gate, it's a phrase. Without a written threshold it would
have been rationalised open the moment I wanted to write React, or shut the
moment AWS looked like work. Defining it late is better than never; defining it
before I had feelings about the answer would have been better still.

**I built a login wall in front of a product nobody could see.** For months the
public link led to a sign-in form. Anyone evaluating it, including hiring
managers, saw a password field and left. Three pillars of working software sat
behind a door with no window. The fix (a landing page and a seeded, read-only
demo that needs no signup) took a day, and should have been there from the first
public link.

---

## What's next, and what gates it

A React and FastAPI rebuild is the obvious next step and is **deliberately
gated** on the hosted version showing real usage first. Building that before the
product earns it is premature scaling, and the current stack has not yet become
the constraint. The gate is now measurable: the admin panel tracks usage over
time and outcome correlation, and metering writes per-action usage events.

Beyond that: AI resume tailoring per job description, a browser extension for
capturing listings, and multi-resume comparison against a single posting.

---

## Stack

| Layer | Choice |
|---|---|
| UI + backend | Streamlit (Python) |
| Database | Supabase PostgreSQL |
| Auth | Supabase email/password |
| AI | Anthropic Claude API, isolated in `ai_engine.py` |
| Hosting | EC2 Graviton + Docker + Caddy, CloudFormation-defined |
| Landing page | S3 + CloudFront |

`ai_engine.py` is the only file that knows Claude exists. Everything else calls
plain functions. Swapping providers is a one-file change, decided on day one,
and the reason a future move to Bedrock is a module replacement rather than a
rewrite.

---

*Built by [Patrick Barnsley](https://linkedin.com/in/patrickbarnsley).*
