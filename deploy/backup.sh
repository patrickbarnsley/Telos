#!/bin/bash
# Nightly database backup to S3.
set -uo pipefail

ENV_FILE="${TELOS_ENV_FILE:-/opt/telos/.env}"

# Read one key out of the env file WITHOUT sourcing it. Docker's env_file parser
# treats the value as a literal string; bash 'source' would expand $, run
# backticks, and choke on &. A database password containing any of those would
# silently produce an empty value here, and the failure would surface as an
# unrelated pg_dump error hours later.
read_env() {
    grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2-
}

DATABASE_URL="$(read_env DATABASE_URL)"
if [ -z "$DATABASE_URL" ]; then
    echo "BACKUP FAILED: DATABASE_URL not found in $ENV_FILE" >&2
    exit 1
fi

BUCKET="${TELOS_BACKUP_BUCKET:?TELOS_BACKUP_BUCKET is required}"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DUMP="$WORK/telos-$STAMP.dump"

if ! pg_dump --format=custom --no-owner --no-privileges --file="$DUMP" "$DATABASE_URL"; then
    echo "BACKUP FAILED: pg_dump returned non-zero" >&2
    exit 1
fi

SIZE=$(stat -c%s "$DUMP")
# A dump this small is not a real database. Refusing it stops a broken copy
# ageing out the good ones under the bucket lifecycle rule.
if [ "$SIZE" -lt 10240 ]; then
    echo "BACKUP FAILED: dump is only $SIZE bytes" >&2
    exit 1
fi

if ! pg_restore --list "$DUMP" >/dev/null 2>&1; then
    echo "BACKUP FAILED: pg_restore cannot read the dump" >&2
    exit 1
fi

KEY="db/$(date -u +%Y/%m)/telos-$STAMP.dump"
if ! aws s3 cp "$DUMP" "s3://$BUCKET/$KEY" --storage-class STANDARD_IA --only-show-errors; then
    echo "BACKUP FAILED: upload to S3 failed" >&2
    exit 1
fi
if ! aws s3api head-object --bucket "$BUCKET" --key "$KEY" >/dev/null 2>&1; then
    echo "BACKUP FAILED: uploaded object is not in the bucket" >&2
    exit 1
fi

echo "backup ok: s3://$BUCKET/$KEY ($SIZE bytes)"
