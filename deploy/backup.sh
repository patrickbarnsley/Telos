#!/usr/bin/env bash
#
# Nightly database backup to S3.
#
# Supabase's own backups exist, but they are theirs, on their retention, and
# reachable only through their console. This is a copy that belongs to Telos:
# encrypted at rest, versioned by date, restorable with one psql command, and
# still there if the Supabase account itself is what goes wrong.
#
# Installed by cloud-init on the app host and run by cron. It is deliberately
# noisy on failure: a backup that has been silently failing for six weeks is
# worse than no backup, because you believed in it.

set -euo pipefail

BUCKET="${TELOS_BACKUP_BUCKET:?TELOS_BACKUP_BUCKET is required}"
RETAIN_DAYS="${TELOS_BACKUP_RETAIN_DAYS:-30}"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
WORK="$(mktemp -d)"
DUMP="${WORK}/telos-${STAMP}.dump"

cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

fail() {
    log "BACKUP FAILED: $*"
    # Surface the failure where it will actually be seen.
    if [ -n "${TELOS_ALERT_TOPIC:-}" ]; then
        aws sns publish --topic-arn "${TELOS_ALERT_TOPIC}" \
            --subject "Telos backup failed" \
            --message "The nightly database backup failed at ${STAMP}: $*" >/dev/null 2>&1 || true
    fi
    exit 1
}

# DATABASE_URL is read from the same place the app reads it, so the backup can
# never drift onto a stale database after a credential rotation.
if [ -z "${DATABASE_URL:-}" ]; then
    if [ -f /opt/telos/.env ]; then
        # shellcheck disable=SC1091
        set -a; . /opt/telos/.env; set +a
    fi
fi
[ -n "${DATABASE_URL:-}" ] || fail "DATABASE_URL is not set"

log "Dumping database"
# Custom format: compressed, and restorable table by table with pg_restore.
pg_dump --format=custom --no-owner --no-privileges --file="${DUMP}" "${DATABASE_URL}" \
    || fail "pg_dump returned non-zero"

SIZE=$(stat -c%s "${DUMP}")
log "Dump written, ${SIZE} bytes"

# A dump far smaller than the last one usually means a partial or empty database.
# Refusing to upload it protects the good copies from being aged out behind it.
if [ "${SIZE}" -lt 10240 ]; then
    fail "dump is only ${SIZE} bytes, which is too small to be a real database"
fi

log "Verifying the dump is readable"
pg_restore --list "${DUMP}" >/dev/null 2>&1 || fail "pg_restore cannot read the dump"

KEY="db/$(date -u +%Y/%m)/telos-${STAMP}.dump"
log "Uploading to s3://${BUCKET}/${KEY}"
aws s3 cp "${DUMP}" "s3://${BUCKET}/${KEY}" \
    --storage-class STANDARD_IA \
    --only-show-errors \
    || fail "upload to S3 failed"

# Confirm the object is actually there. A silent upload failure is the exact
# failure mode this whole script exists to prevent.
aws s3api head-object --bucket "${BUCKET}" --key "${KEY}" >/dev/null \
    || fail "uploaded object is not present in the bucket"

log "Backup complete: s3://${BUCKET}/${KEY} (${SIZE} bytes)"

# Retention is enforced by the bucket's own lifecycle rule, not by this script:
# a delete loop running on the same host that writes the backups is one bad
# variable away from erasing all of them.
log "Retention (${RETAIN_DAYS} days) is handled by the bucket lifecycle policy"
