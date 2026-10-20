# Brief for local Claude Code: finish the Telos nightly backup

You are running on Patrick's Windows machine with his PowerShell, AWS
credentials and the repo. A separate Claude session in the cloud holds the
product context and wrote everything below; it cannot see your machine, which
is exactly why you are doing the execution.

**Roles.** You execute and report real output. The cloud session holds the spec
and checks your result against the acceptance criteria at the end. Do not
redesign the approach without saying so explicitly.

---

## Where things stand

Repo: `C:\Users\patri\OneDrive\Desktop\AI Projects\telos-deploy\Telos-repo`
Branch `main`, remote `https://github.com/patrickbarnsley/Telos.git`.

**Step 0, before anything else.** The cloud session committed fixes that are not
on this machine yet. Pull them first or you will redo work and create conflicts:

```powershell
git pull "..\..\telos-main.bundle" main
git push origin main
```

Expect to land on commit `189f525 Stop the nightly backup failing silently`.

AWS, all in `us-east-1`:

| Thing | Value |
|---|---|
| Instance | `i-09018a35526792b92` (Amazon Linux 2023, Graviton/arm64, t4g.small) |
| Backup bucket | `telos-backups-082867429081` (exists, reachable, empty) |
| Stacks | `telos-app`, `telos-site`, `telos-dns` |
| Access | SSM Run Command only. No SSH, port 22 is closed. |

Already working on the instance: `/opt/telos/backup.sh` exists and is
executable, `telos-backup.timer` is enabled and armed for 08:26 UTC daily,
`pg_dump` 16.14 is installed, Docker is running the app.

## The one remaining defect

```
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 17.6; pg_dump version: 16.14
```

Supabase runs **PostgreSQL 17.6**. Amazon Linux 2023 ships a 16 client.
`pg_dump` refuses to dump a server newer than itself. The timer is armed, so
this would have failed every night with nobody noticing.

## Required fix

Do **not** add the PGDG third-party repo. Two reasons: it is extra surface on a
Graviton host, and it breaks again the day Supabase moves to 18.

Instead run `pg_dump` from the official Postgres Docker image, at the major
version the server actually reports. Docker is already the app's runtime on this
box, so it adds no new dependency.

Shape of the change to `/opt/telos/backup.sh`:

1. Read `DATABASE_URL` from `/opt/telos/.env` **literally**, never by sourcing.
   The existing script already does this; keep it:
   ```bash
   read_env() { grep -m1 "^$1=" /opt/telos/.env 2>/dev/null | cut -d= -f2-; }
   ```
2. Detect the server major version. The installed `psql` 16 connects to a 17
   server fine, so this works with what is already there:
   ```bash
   MAJOR=$(psql "$DATABASE_URL" -tAc "SHOW server_version_num" | cut -c1-2)
   ```
   Validate it is a plausible two-digit number before using it. If detection
   fails, fail loudly rather than guessing a version.
3. Run `pg_dump` and `pg_restore` inside `postgres:${MAJOR}-alpine`. Fall back to
   `postgres:${MAJOR}` if the alpine tag does not exist for that major.
   - Pass the connection string with `-e`, never as an argument, so it does not
     appear in `docker inspect` or `ps`.
   - Use `--user "$(id -u):$(id -g)"` so the dump file is owned by the host user
     and the script can read it afterwards.
   - Mount the work directory and write the dump inside it.
4. Keep every existing safety check: reject a dump under 10240 bytes, verify
   with `pg_restore --list` before upload, `head-object` after upload to confirm
   the object is really there.
5. **Never print `DATABASE_URL`.** Pipe anything that could contain it through:
   ```bash
   mask() { sed -E 's#://[^:/@]+:.*@#://***:***@#'; }
   ```
   Greedy to the last `@` on purpose: a non-greedy version leaks the tail of any
   password containing `@`. This was tested against eight connection-string
   shapes.

Apply it via SSM Run Command. Prefer `--cli-input-json file://...` with a JSON
file you generate, rather than fighting PowerShell quoting.

**Capture the command ID in a variable. Do not ask Patrick to paste it:**

```powershell
$id = aws ssm send-command --cli-input-json file://your-payload.json --query "Command.CommandId" --output text
Start-Sleep -Seconds 90
aws ssm get-command-invocation --command-id $id --instance-id i-09018a35526792b92 --query StandardOutputContent --output text
```

## Known environment traps, already paid for once each

- AWS CLI v2 bundles its own Python and **ignores `PYTHONIOENCODING`**. If you
  see `'charmap' codec can't encode`, run `chcp 65001`. Better: keep all output
  pure ASCII.
- The instance is **arm64**. Any image or binary must have an arm64 build.
- `UserData` runs only on first boot. Editing it in CloudFormation and updating
  the stack restarts the instance without re-running cloud-init. Anything that
  must exist on the *running* instance has to be applied over SSM.
- Keep `deploy.ps1` **pure ASCII, CRLF, with a UTF-8 BOM**. PowerShell 5.1 reads
  a BOM-less UTF-8 file as ANSI, and a single smart quote breaks the script.
- The repo has a `.gitattributes` pinning LF for everything except `.ps1`. Do
  not fight it.
- `telos-site/` is deliberately gitignored. Never commit it.
- Never commit `telos-secrets.txt` or `.env`. Both are ignored; keep it that way.

## Acceptance criteria

Report the real output for each. Do not summarize, paste what the commands said.

1. `git log --oneline -1` shows `189f525` or later, and `git push origin main`
   succeeded.
2. A backup run on demand prints `backup ok: s3://telos-backups-082867429081/db/...`
   with a byte count over 10240.
3. `aws s3 ls s3://telos-backups-082867429081/db/ --recursive` lists at least one
   object.
4. `systemctl list-timers telos-backup.timer` shows a `NEXT` time.
5. A **restore** proves the dump is real, not just present. Download it and run
   `pg_restore --list` against it, and confirm the `jobs`, `profile` and
   `match_results` tables appear. An untested backup is not a backup.
6. No output anywhere contains the database password. Check before pasting.
7. Mirror the working script into the repo in **two** places so a rebuilt
   instance gets it: `deploy/backup.sh`, and the `cat > /opt/telos/backup.sh`
   heredoc inside `infra/telos-app.yaml`. Then `cfn-lint infra/telos-app.yaml`
   must pass clean.

## Do not

- Do not touch `app.py`, `core/`, or `pages/`. They are tested and deployed.
- Do not run `deploy.ps1 -Step app` unless you say why first. It updates the
  stack and restarts the instance.
- Do not rewrite commit authorship. These are Patrick's commits on his portfolio
  repo and must stay in his name.
- Do not push anything without showing Patrick the diff first.
