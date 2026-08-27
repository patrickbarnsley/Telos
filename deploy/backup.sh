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

# Anything that might carry the connection string goes through this before it
# reaches a log. Greedy to the LAST '@' on purpose: a non-greedy match stops at
# the first '@' and so leaks the tail of any password that contains one.
mask() { sed -E 's#://[^:/@]+:.*@#://***:***@#'; }

DATABASE_URL="$(read_env DATABASE_URL)"
if [ -z "$DATABASE_URL" ]; then
    echo "BACKUP FAILED: DATABASE_URL not found in $ENV_FILE" >&2
    exit 1
fi

BUCKET="${TELOS_BACKUP_BUCKET:?TELOS_BACKUP_BUCKET is required}"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DUMPNAME="telos-$STAMP.dump"
DUMP="$WORK/$DUMPNAME"

# Amazon Linux ships a PostgreSQL 16 client and Supabase runs 17, and pg_dump
# refuses to dump a server newer than itself. Rather than bolt the PGDG repo
# onto a Graviton host, run the client out of the official image at whatever
# major the server actually reports. Detecting it beats pinning it: the day
# Supabase moves to 18 this keeps working instead of failing every night with
# nobody watching. Docker already runs the app here, so it is not a new
# dependency. The host's own psql is older than the server but still connects
# fine, which is all this query needs.
VERSION_RAW="$(PGCONNECT_TIMEOUT=15 psql "$DATABASE_URL" -tAc 'SHOW server_version_num' 2>&1)"
VERSION_NUM="$(printf '%s' "$VERSION_RAW" | tr -d '[:space:]')"
# Insist the whole reply is the number. Sniffing digits out of a failure message
# would happily read "port 6543" as major 65 and carry on.
if ! printf '%s' "$VERSION_NUM" | grep -qE '^[0-9]{5,6}$'; then
    echo "BACKUP FAILED: could not read the server version" >&2
    printf '%s\n' "$VERSION_RAW" | mask >&2
    exit 1
fi
MAJOR="$(printf '%s' "$VERSION_NUM" | cut -c1-2)"
if [ "$MAJOR" -lt 13 ]; then
    echo "BACKUP FAILED: implausible server major version $MAJOR" >&2
    exit 1
fi

# Alpine for the smaller pull, but not every major is published with that tag,
# so fall back to the full image before giving up.
IMAGE="postgres:$MAJOR-alpine"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1 && ! docker pull -q "$IMAGE" >/dev/null 2>&1; then
    IMAGE="postgres:$MAJOR"
    if ! docker image inspect "$IMAGE" >/dev/null 2>&1 && ! docker pull -q "$IMAGE" >/dev/null 2>&1; then
        echo "BACKUP FAILED: no postgres client image for major version $MAJOR" >&2
        exit 1
    fi
fi

# The connection string is exported and handed over with a bare -e, so it never
# appears as an argument in ps on the host. --user keeps the dump owned by the
# caller instead of by root inside the container.
export PGURL="$DATABASE_URL"
if ! ERR="$(docker run --rm \
        --user "$(id -u):$(id -g)" \
        --entrypoint sh \
        -e PGURL \
        -e DUMPNAME="$DUMPNAME" \
        -e PGCONNECT_TIMEOUT=30 \
        -v "$WORK:/work" \
        "$IMAGE" \
        -c 'exec pg_dump --format=custom --no-owner --no-privileges --file="/work/$DUMPNAME" "$PGURL"' 2>&1)"; then
    echo "BACKUP FAILED: pg_dump returned non-zero" >&2
    printf '%s\n' "$ERR" | mask >&2
    exit 1
fi

if [ ! -f "$DUMP" ]; then
    echo "BACKUP FAILED: pg_dump reported success but wrote no file" >&2
    exit 1
fi

SIZE=$(stat -c%s "$DUMP")
# A dump this small is not a real database. Refusing it stops a broken copy
# ageing out the good ones under the bucket lifecycle rule.
if [ "$SIZE" -lt 10240 ]; then
    echo "BACKUP FAILED: dump is only $SIZE bytes" >&2
    exit 1
fi

# Read it back with a client of the same major that wrote it. The host's 16
# cannot parse a 17 archive header, so this check has to run in the image too.
if ! docker run --rm \
        --user "$(id -u):$(id -g)" \
        --entrypoint sh \
        -e DUMPNAME="$DUMPNAME" \
        -v "$WORK:/work" \
        "$IMAGE" \
        -c 'exec pg_restore --list "/work/$DUMPNAME"' >/dev/null 2>&1; then
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
