\# 🎯 Telos



> \*Telos is the Greek word for ultimate purpose. The app helps you find and reach yours.\*



\*\*Live App:\*\* \[telos-career.streamlit.app](https://telos-career.streamlit.app)



\---



\## Why I Built This



I built Telos because I found a fundamental flaw in the job market. Candidates have no real visibility into how well they match the jobs they're applying for, and career advisors rarely give honest, actionable guidance on how to close the gap.



The problem became personal when my wife went through a job transition. She was frustrated that she couldn't keep track of the jobs she'd applied to, where she stood with each one, or how well she was actually doing. She was losing confidence, not because she wasn't qualified, but because she had no system and no signal. She wanted to know which jobs had rejected her, how much progress she was making, and what she could do differently.



I built Telos to solve that. Many people are skilled at managing complex projects and pipelines in their professional lives, but few apply that same discipline to their own career. Telos gives job seekers the same clarity, structure, and AI-powered insight they would want in any other high-stakes campaign.



\---



\## What Telos Does



Telos is a self-hosted career campaign management app. Three pillars, each building on the last:



\### 📋 Track

Log every job you're pursuing. Track status across the full pipeline (applied, screening, interview, offer, rejected, withdrawn), add notes and contacts, and see your funnel metrics updated in real time: response rate, interview rate, and offer rate.



\### 🎯 Match

Paste any job description and get an AI-powered match score against your actual resume. See exactly which requirements you meet and which you're missing, get specific cert recommendations to close gaps, and get a recommended action list. Telos also researches the company in the background and flags potential scams before you invest time in an application.



\### 🗺️ Guide

Get a structured critical path from your current state to your target role. Telos analyzes your resume, your target role, your career goals, and your match history to build a specific set of ordered milestones with timelines, actions, and success criteria. An advisor chat lets you drill down on any part of the path.



\---



\## Security



Security is built into the architecture of Telos from the ground up, not added as an afterthought.



\### What is protected today



\*\*Your data never leaves your deployment.\*\* Because Telos is self-hosted, your resume, job history, match results, and career goals are stored only in your own instance. There is no central server where your sensitive career information sits alongside other users' data. This is a stronger privacy model than most SaaS tools can offer.



\*\*Your API key is never exposed.\*\* The Anthropic API key is stored in a local `.env` file that is permanently blocked from GitHub by `.gitignore`. In production on Streamlit Community Cloud, it is stored in an encrypted secrets manager and never appears in the codebase. No one can access your key from the repository.



\*\*Your database is never committed.\*\* The SQLite database file that holds your jobs, resume, and match history is blocked from GitHub by `.gitignore`. It exists only on your local machine or your Streamlit Cloud deployment.



\*\*HTTPS is enforced automatically.\*\* All traffic to your Streamlit Community Cloud deployment is encrypted in transit via HTTPS by default.



\### Honest limitations



Telos v1 is designed for personal use by a single user on their own deployment. With that context in mind, there are limitations worth knowing:



\- The app has no login or authentication system. Anyone who has your deployment URL can access it. Keep your URL private or use Streamlit's built-in sharing controls to restrict access.

\- The SQLite database is not encrypted at rest. If someone has physical access to the machine running your instance, the database file is readable.

\- There is no rate limiting on AI calls. Your Anthropic API usage is governed by your own account limits.



\### Security roadmap for v2



When Telos transitions to a centralized SaaS model, the following will be added:



\- Full user authentication (login, password, session management)

\- Encrypted database at rest

\- Rate limiting on all AI calls

\- Role-based access controls

\- Security audit before public launch



\---



\## Product Decisions



\### Why self-hosted?



Telos v1 is designed as a self-hosted open source app. Each user deploys their own instance rather than sharing a central platform. This was a deliberate decision for several reasons.



Speed to ship was the first one. Without an auth system, central database, or server to maintain, I could build a working product in weeks instead of months. Cost was the second. It's free to run and free to use with no infrastructure bill. The third reason was about sequencing correctly: the right question for v1 is whether the product is actually useful, not whether it can handle 100,000 users. Build the SaaS when there's proof it's worth building. And finally, users own their own data. Their resume, job history, and match results are all stored locally in their own instance.



The tradeoff is real. Users need their own Anthropic API key and need to deploy their own instance. That's friction. It's the right tradeoff for v1.



\### Why build Track, then Match, then Guide?



Each pillar depends on the one before it. Track had to exist first because Match needs a job to score against. Match had to exist before Guide because Guide uses match history to build a smarter critical path. The order isn't arbitrary; it's the dependency graph.



Building sequentially also meant something useful shipped at every stage. Track is immediately valuable on day one before the AI features exist at all. If all three had been built simultaneously, nothing would have been usable for months.



\### Why require a linked job before Match scoring?



This was a deliberate workflow enforcement decision. The right sequence is to see a job, log it in Track, then score it in Match. Enforcing that order means every match result is tied to a real job in the tracker, the scam check always has a company name to research, and the match history stays clean and organized.



\### What was cut and why



| Feature | Decision | Reasoning |

|---------|----------|-----------|

| LinkedIn / Indeed scraping | Cut | Active bot detection, no public APIs, legal risk. Surfacing this tradeoff is more valuable than shipping a fragile scraper. |

| Multi-user architecture | Deferred to v2 | Not needed for the self-hosted model. Each instance serves one user. |

| Payments / monetization | Deferred | Validate the product first. Charging adds legal, payment, and support complexity that doesn't serve v1 goals. |

| Browser extension | Roadmap | Too complex for v1. Right feature, wrong time. |

| AI resume tailoring | Roadmap | Natural v2 feature once Match is validated. |

| Community / messaging board | v3 | Requires centralized infrastructure that doesn't exist yet. |



\---



\## Architecture



```

telos/

├── app.py                    # Landing page and navigation

├── pages/

│   ├── 0\_Profile.py          # Resume upload and career goals

│   ├── 1\_Track.py            # Job pipeline tracker

│   ├── 2\_Match.py            # AI job description scoring

│   └── 3\_Guide.py            # Critical path generator and advisor chat

├── core/

│   ├── database.py           # All SQLite read/write in one place

│   ├── ai\_engine.py          # Claude API wrapper (swappable)

│   ├── models.py             # Data classes (Job, Profile)

│   └── app\_styles.py         # Dark professional theme

├── .env                      # API key, never committed

├── .gitignore

├── requirements.txt

└── README.md

```



\### The AI Module Design



`ai\_engine.py` is the only file that knows Claude exists. The rest of the app calls clean functions:



```python

from core.ai\_engine import score\_match, generate\_critical\_path, chat\_with\_advisor

```



`ai\_engine.py` handles prompt construction, API calls, response parsing, and error handling internally. The rest of the app never touches the Anthropic SDK directly. Swapping to a different AI provider in v2 is a one-file change. That was intentional from day one.



\### Stack



| Layer | Choice | Why |

|-------|--------|-----|

| UI + Backend | Streamlit (Python) | Fast to ship and immediately demoable |

| Database | SQLite via `sqlite3` | Zero setup, file-based, sufficient for single-user |

| AI | Anthropic Claude API | Isolated in `ai\_engine.py` and swappable |

| Deployment | Streamlit Community Cloud | Free, GitHub-connected, shareable URL |



\---



\## Roadmap



\### v2 — SaaS Transition

\- FastAPI backend (Python)

\- PostgreSQL database

\- React frontend

\- User authentication

\- No API key required, AI costs absorbed by subscription

\- Hosted at a custom domain



\### v2 Features

\- AI-powered resume tailoring per job description

\- Browser extension to capture job listings from any page

\- Application auto-fill

\- Multi-resume support

\- Bring your own AI provider



\### v3 Features

\- Community board to connect with people in your target roles

\- Peer accountability groups

\- Mentor matching

\- Aggregated anonymized success path data by role and industry



\---



\## How to Deploy Your Own Telos



\### Prerequisites

\- Python 3.10+

\- Git

\- Anthropic API key (\[console.anthropic.com](https://console.anthropic.com))



\### Local Setup



```bash

\# Clone the repo

git clone https://github.com/patrickbarnsley/Telos

cd Telos



\# Create and activate virtual environment

python -m venv venv

venv\\Scripts\\activate  # Windows

source venv/bin/activate  # Mac/Linux



\# Install dependencies

pip install -r requirements.txt



\# Add your API key

echo ANTHROPIC\_API\_KEY=your\_key\_here > .env



\# Run the app

streamlit run app.py

```



\### Deploy to Streamlit Community Cloud (Free)



1\. Fork this repo to your GitHub account

2\. Go to \[share.streamlit.io](https://share.streamlit.io)

3\. Connect your GitHub repo

4\. Set Main file path to `app.py`

5\. Add `ANTHROPIC\_API\_KEY = "your\_key\_here"` in the Secrets section

6\. Deploy



Your personal Telos instance will be live at `your-app-name.streamlit.app`.



\---



\## About



Built by \[Patrick Barnsley](https://linkedin.com/in/patrickbarnsley).



Telos exists because the job search process is broken for candidates. No signal, no structure, no honest feedback. It's built to change that.

