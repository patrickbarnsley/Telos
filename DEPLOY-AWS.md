# Telos on AWS

ECS Fargate behind an Application Load Balancer, plus the landing page on
S3 + CloudFront. No GitHub anywhere in the deployment path.

---

## Why not App Runner

Your Phase 2 plan named App Runner. It doesn't work for this app.

Streamlit talks to the browser over a WebSocket — the page loads, then opens
`/_stcore/stream` and does everything through it. **App Runner does not proxy
WebSockets.** The container starts, health checks pass, and the app sits on a
loading spinner forever. This is a known limitation people hit repeatedly.

An Application Load Balancer handles the `Upgrade: websocket` handshake
correctly, so the architecture is ECS Fargate behind an ALB.

This is worth keeping as an interview answer. "I planned App Runner, found it
couldn't carry the protocol my framework depends on, and moved to Fargate behind
an ALB" is a better technical-fluency signal than having picked the right thing
by luck.

---

## What gets built

```
                    Route 53  (usetelosapp.com)
                         |
        +----------------+------------------+
        |                                   |
  CloudFront + ACM                   ALB + ACM  :443
        |                                   |
   S3 (private, OAC)              ECS Fargate task
   landing page                    Telos container :8501
                                          |
                            Supabase Postgres + Anthropic API
```

Three CloudFormation stacks:

| Stack | Template | Contains |
|---|---|---|
| `telos-dns` | `infra/telos-dns.yaml` | Route 53 hosted zone |
| `telos-site` | `infra/telos-site.yaml` | S3, CloudFront, OAC, ACM, DNS records |
| `telos-app` | `infra/telos-app.yaml` | VPC, subnets, ALB, target group, ECS cluster, Fargate service, IAM roles, ACM, DNS record, logs |

Secrets live in SSM Parameter Store as SecureString and are injected as
environment variables at task start. Nothing sensitive is in the image.

---

## Prerequisites

- AWS account with billing enabled
- AWS CLI v2, authenticated (`aws sts get-caller-identity` should return your account)
- Docker Desktop running
- Control of DNS for `usetelosapp.com` at your registrar

Deploy everything in **us-east-1**. CloudFront only accepts certificates issued
there, and keeping one region avoids a class of confusing errors.

---

## Steps

All commands run from the repo root.

### 1. Hosted zone

```powershell
.\deploy\deploy.ps1 -Step dns
```

Prints four nameservers. **Set them at your registrar, then wait.** Verify with:

```powershell
nslookup -type=NS usetelosapp.com
```

Do not move on until that returns AWS nameservers. Both remaining stacks request
DNS-validated certificates; if the zone isn't authoritative yet, CloudFormation
sits in `CREATE_IN_PROGRESS` and eventually fails. Propagation is usually under
an hour but the TTL on your old records governs it.

### 2. Secrets

```powershell
.\deploy\deploy.ps1 -Step secrets
```

Prompts for six values, masked. Press Enter to keep an existing value.

`OWNER_EMAILS` is your own address — it gives your account unmetered AI usage.
Without it you get the Free plan's 10 match scores a month like everyone else.

### 3. Landing page

```powershell
.\deploy\deploy.ps1 -Step site
```

Creates the bucket and distribution, uploads `telos-site/index.html`, invalidates
the cache. First run takes 10-20 minutes, mostly certificate validation and
CloudFront propagation.

### 4. Application

```powershell
.\deploy\deploy.ps1 -Step app
```

Builds the image for `linux/amd64`, pushes to ECR, deploys the stack. 10-15
minutes on first run.

### 5. Check it

```powershell
.\deploy\deploy.ps1 -Step status
```

Then open `https://app.usetelosapp.com/?demo=1` and click through as if you were
a hiring manager.

---

## Routine releases

After the first deploy, shipping a change is one command:

```powershell
.\deploy\deploy.ps1 -Step release
```

Builds, pushes a timestamped tag, and rolls the service. The deployment circuit
breaker is enabled, so a broken image rolls back automatically instead of taking
the site down.

---

## What this costs

Realistic monthly estimate, us-east-1, low traffic:

| Item | Cost |
|---|---|
| Application Load Balancer | ~$17 |
| Fargate task, 0.5 vCPU / 1 GB, always on | ~$18 |
| Route 53 hosted zone + queries | ~$1 |
| CloudWatch Logs (30-day retention) | ~$0.50 |
| ECR storage | ~$0.10 |
| S3 + CloudFront at low traffic | ~$0-1 |
| ACM certificates | free |
| **Total** | **~$37-40/month** |

Compare: Railway or Render runs the same container for $5-7/month, and Streamlit
Community Cloud is free. You're paying roughly $35/month over the cheapest
working option, and about $30/month over Railway, for the AWS line on your
resume and the architecture experience behind it. That may well be worth it —
it's a training and credibility budget, not an infrastructure bill — but it
should be a number you chose rather than one you discovered.

**Ways to cut it:**

- **Fargate Spot** saves roughly 70% of the $18 compute. The tradeoff is that
  AWS can reclaim the task with two minutes' notice, which drops live sessions.
  Fine for a portfolio app, not for paying users.
- **Drop to 0.25 vCPU / 0.5 GB** saves about $9. I'd advise against it —
  pandas, pdfplumber and Pillow in one container will sit close to 512 MB, and
  an OOM-killed task looks exactly like a broken app.
- The ALB is not removable. Nothing cheaper on AWS terminates TLS, serves a
  custom domain, and proxies WebSockets.

**Set a billing alarm before you walk away from this.** Billing → Budgets, a
$60/month threshold with an email alert. Ten minutes, and it's the difference
between noticing a mistake in a day versus in a month.

---

## Operating it

```powershell
# Live logs
aws logs tail /ecs/telos-app --follow --region us-east-1

# Service state and recent events
.\deploy\deploy.ps1 -Step status

# Tear it all down (S3 bucket is retained deliberately)
.\deploy\deploy.ps1 -Step destroy
```

### If something breaks

**Task starts then stops repeatedly** — almost always a missing SSM parameter.
Re-run `-Step secrets` and check the log group.

**502 from the ALB** — the container isn't answering on 8501 yet. Check whether
the target group shows healthy targets; the grace period is 90 seconds.

**App loads but shows "Connecting..." forever** — the WebSocket isn't getting
through. On this stack it should; if you ever move to a proxy in front of the
ALB, that proxy must forward `Upgrade` and `Connection` headers.

**Certificate stack stuck** — nameservers aren't live. Confirm with `nslookup`
before redeploying.

---

## Honest caveats

- **I could not test the AWS deploy end to end.** My sandbox has no route to
  AWS, no container registry, and no PowerShell. The templates pass `cfn-lint`
  clean and the Dockerfile's runtime behaviour is verified — the app serves,
  `/_stcore/health` returns 200, and the WebSocket upgrade returns
  `101 Switching Protocols`. The image build itself and the PowerShell script
  have not been executed. Expect to hit one or two small things on the first
  run; that's normal for a first infrastructure deploy and the errors are
  usually legible.
- **The database stays on Supabase.** Moving to RDS adds ~$15/month minimum and
  a migration risk for no user-visible gain. "Postgres on Supabase, app on AWS"
  is a perfectly defensible architecture — and being able to explain *why* you
  didn't move it is a better answer than having moved it reflexively.
- **Cognito isn't here either.** Supabase auth works today. Swapping auth
  providers is real migration work with zero user benefit. Do it if you want the
  Cognito line specifically, not because the diagram looks tidier.
- **One task means brief downtime on deploy.** The rolling update starts a new
  task before draining the old one, but Streamlit session state lives in the
  process, so anyone mid-session gets reconnected.
