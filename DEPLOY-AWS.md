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
proxy WebSockets — the container passes health checks and the browser hangs on a
loading spinner permanently. Caddy handles the upgrade natively.

**ECS Fargate behind an ALB.** Built, tested, and costed at **$47.65/month**, of
which the load balancer and its two public IPv4 addresses were $24.73 — over
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

Against the Fargate build at $47.65, that saves **$29.49/month — $354/year.**

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

Deploy everything in **us-east-1** — CloudFront only accepts certificates issued
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

- **Rebuilds on reboot** — a systemd unit brings the compose stack back up.
- **Patches itself** — `dnf-automatic` applies security updates.
- **Keeps Supabase awake** — a daily timer runs one trivial query. Supabase
  pauses Free-plan projects after 7 days of low activity, which would otherwise
  leave a visitor looking at a database error during a quiet week.
- **Rotates logs** — container logs capped at 10 MB x 3 files.

---

## Honest caveats

- **The AWS deploy has not been run end to end.** My sandbox has no route to AWS,
  no container registry, and no PowerShell. Verified: all templates pass
  `cfn-lint` clean; the app serves, `/_stcore/health` returns 200, and the
  WebSocket upgrade returns `101 Switching Protocols`. Not verified: the image
  build, the PowerShell script, and the deploy itself.
- **One instance means one point of failure.** A reboot is roughly a minute of
  downtime, and a bad deploy has no automatic rollback — though `docker compose`
  makes reverting easy. For a portfolio app this is the right trade.
- **Database and auth stay on Supabase.** RDS would roughly double the bill and
  Cognito replaces working auth with migration work. Being able to explain why
  you didn't move them is a better interview answer than having moved them.
- **This host carries forward.** When the React + FastAPI rebuild happens, the
  same instance and the same Caddy serve it — static frontend plus a proxied
  API on the same box. None of this is throwaway.
