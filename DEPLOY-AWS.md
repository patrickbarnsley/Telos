# Telos on AWS

One Graviton EC2 instance running Docker and Caddy, plus the landing page on
S3 + CloudFront. No GitHub in the deployment path, and no SSH.

Full step-by-step walkthrough: see the launch runbook.

---

## Architecture

```
                 Route 53  (usetelosapp.com)
                       |
        +--------------+----------------+
        |                               |
  CloudFront + ACM              Elastic IP -> EC2 t4g.small
        |                               |
   S3 (private, OAC)            Caddy :443  (auto TLS, WebSockets)
   landing page                        |
                                  Telos container :8501
                                        |
                          Supabase Postgres + Anthropic API
```

| Stack | Template | Contains |
|---|---|---|
| `telos-dns` | `infra/telos-dns.yaml` | Route 53 hosted zone |
| `telos-site` | `infra/telos-site.yaml` | S3, CloudFront, OAC, ACM, DNS |
| `telos-app` | `infra/telos-app.yaml` | VPC, EC2, Elastic IP, IAM, deploy bucket, DNS |

---

## Two architectures that were rejected, and why

**App Runner.** Streamlit drives its UI over a WebSocket. App Runner does not
proxy WebSockets, the container passes health checks and the browser hangs on a
loading spinner permanently. Caddy handles the upgrade natively.

**ECS Fargate behind an ALB.** Built, tested, and costed at **$47.65/month**, of
which the load balancer and its two public IPv4 addresses were $24.73, over
half the bill, to balance a single container. The template is kept at
`infra/reference/telos-app-fargate.yaml` with the conditions that would justify
returning to it: more than one task, zero-downtime deploys, or a single reboot
becoming an unacceptable outage.

---

## What it costs

| Item | Per month |
|---|---|
| EC2 t4g.small (2 vCPU / 2 GB, Graviton) | $12.26 |
| EBS 20 GB gp3 | $1.60 |
| Public IPv4 address | $3.65 |
| Route 53 hosted zone + queries | $0.60 |
| S3 + CloudFront (landing page) | $0.05 |
| ACM / Let's Encrypt certificates | $0.00 |
| **Total** | **$18.16** |

Against the Fargate build at $47.65, that saves **$29.49/month, $354/year.**

Note the public IPv4 charge: AWS bills $0.005/hour for every public IPv4
address, attached or idle. One address is unavoidable for a public app. The
Fargate stack needed three.

Anthropic API usage is billed separately and scales with real users. The
per-account quotas in `core/plans.py` bound it.

---

## Steps

```powershell
.\deploy\deploy.ps1 -Step dns        # then set nameservers at your registrar, WAIT
.\deploy\deploy.ps1 -Step secrets    # six values into SSM Parameter Store
.\deploy\deploy.ps1 -Step site       # landing page
.\deploy\deploy.ps1 -Step app        # instance + first code deploy
.\deploy\deploy.ps1 -Step status
```

Docker is **not** required on your machine. The image is built on the instance,
natively for ARM, so there is no cross-compilation and no ECR.

Deploy everything in **us-east-1**: CloudFront only accepts certificates issued
there.

### Shipping a change

```powershell
.\deploy\deploy.ps1 -Step release
```

Zips the source, uploads it to a private S3 bucket, and triggers a rebuild on the
instance through SSM Run Command. No SSH, no registry.

---

## Operating it

```powershell
.\deploy\deploy.ps1 -Step logs      # recent application logs
.\deploy\deploy.ps1 -Step status    # instance and container state
.\deploy\deploy.ps1 -Step destroy   # tear down (S3 buckets retained)
```

Shell access, without SSH or a key pair:

```powershell
aws ssm start-session --target <instance-id> --region us-east-1
```

Port 22 is never opened. There is no key pair to lose.

### What the instance does on its own

- **Rebuilds on reboot**: a systemd unit brings the compose stack back up.
- **Patches itself**: `dnf-automatic` applies security updates.
- **Keeps Supabase awake**: a daily timer runs one trivial query. Supabase
  pauses Free-plan projects after 7 days of low activity, which would otherwise
  leave a visitor looking at a database error during a quiet week.
- **Rotates logs** - container logs capped at 10 MB x 3 files.
- **Backs up the database nightly** - `pg_dump` at 08:15 UTC to
  `s3://telos-backups-<account-id>/db/YYYY/MM/`. The dump is verified with
  `pg_restore --list` before upload and rejected if it is implausibly small, so
  a broken dump cannot age out the good ones. Retention is 30 days, enforced by
  the bucket lifecycle rule rather than by a delete loop on the host. The
  instance role has `PutObject` and `GetObject` on that bucket and deliberately
  no `DeleteObject`.


### Restoring from a backup

```powershell
# List what is there
aws s3 ls s3://telos-backups-<account-id>/db/ --recursive

# Pull one down and restore it into a scratch database first. Never restore
# straight over production: confirm the dump is what you think it is.
aws s3 cp s3://telos-backups-<account-id>/db/2026/08/telos-2026-08-24T08-15-00Z.dump .
pg_restore --list telos-2026-08-24T08-15-00Z.dump          # inspect contents
pg_restore --no-owner --no-privileges -d "<scratch-db-url>" telos-2026-08-24T08-15-00Z.dump
```

An untested backup is not a backup. Restore one into a scratch database at
least once so the procedure is known to work before the day it is needed.

### Controlling AI spend

Two independent limits protect the bill:

| Limit | Where | Effect |
|---|---|---|
| Per-user monthly quotas | `core/plans.py` | One person cannot burn the budget |
| Global monthly ceiling | `core/spend.py`, default $40 | Everyone together cannot either |

Every Claude API call goes through `_invoke` in `core/ai_engine.py`, which
checks the ceiling before the request and writes the real token cost to the
`ai_spend` table after it. Admin, then the AI Spend tab, shows the running
total, the cost per feature, and a 30 day chart.

Both knobs live in Parameter Store and take effect on the next restart, with no
code change and no redeploy:

```powershell
aws ssm put-parameter --name /telos/TELOS_AI_MONTHLY_CAP --value 60 --type SecureString --overwrite
aws ssm put-parameter --name /telos/TELOS_AI_MODEL --value claude-sonnet-4-5 --type SecureString --overwrite
```

Opus is the default and the most expensive tier at $5 in / $25 out per million
tokens. Sonnet is roughly 2.5x cheaper on output and Haiku roughly 5x. If AI
cost becomes the binding constraint, changing the model is the first lever, not
cutting features.

**This ceiling is the app's own accounting, not an invoice.** Set a billing
alarm in the Anthropic console as well. Two independent limits fail
independently.

---

## Running the tests

```bash
DATABASE_URL=postgresql://user:pass@host/scratch_db python3 tests/run_all.py
```

142 checks across six suites: database and quota behaviour, page rendering for
every account type, admin access control, the auth flows, data export and
deletion, and AI cost accounting. They need a real PostgreSQL database, because
the properties most worth testing here (owner scoping, transactional deletion,
quota counting) are enforced in SQL. A mocked database would pass while the real
one leaked data between users.

The suites delete rows. Point `DATABASE_URL` at a scratch database, never
production.

---

## Honest caveats

- **The backup and the spend cap have been tested in code, not on AWS.** The
  cap, the pricing arithmetic and the error messages are covered by the test
  suite. The nightly timer, the S3 upload and the IAM policy are verified only
  by `cfn-lint` and by reading. Check that the first backup actually lands in
  the bucket the morning after the deploy, and restore it once.
- **`pg_dump` must match the server major version.** The bootstrap installs the
  PostgreSQL 16 client and falls back to 15. If Supabase moves to a newer major,
  `pg_dump` will refuse with a version mismatch and the backup will fail loudly,
  which is the correct behaviour but does need acting on.
- **One instance means one point of failure.** A reboot is roughly a minute of
  downtime, and a bad deploy has no automatic rollback, though `docker compose`
  makes reverting easy. For a portfolio app this is the right trade.
- **Database and auth stay on Supabase.** RDS would roughly double the bill and
  Cognito replaces working auth with migration work. Being able to explain why
  you didn't move them is a better interview answer than having moved them.
- **This host carries forward.** When the React + FastAPI rebuild happens, the
  same instance and the same Caddy serve it, static frontend plus a proxied
  API on the same box. None of this is throwaway.
