#!/bin/sh
set -eu

payload_directory="/work/payload"
dump_file="$payload_directory/database.dump"
manifest_file="$payload_directory/manifest.env"

log_event() {
    printf '{"timestamp":"%s","level":"%s","service":"backup-agent","event":"%s"}\n' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$1" "$2"
}

cleanup() {
    exit_code=$?
    trap - EXIT
    rm -rf "$payload_directory"
    if [ "$exit_code" -ne 0 ]; then
        log_event error backup_failed >&2
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

log_event info backup_started
rm -rf "$payload_directory"
mkdir -p "$payload_directory"

pg_isready --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" --dbname="$PGDATABASE"

pg_dump \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE" \
    --format=custom \
    --compress=zstd:6 \
    --no-owner \
    --no-privileges \
    --file="$dump_file"

if [ ! -s "$dump_file" ]; then
    exit 1
fi

task_count="$(psql \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE" \
    --tuples-only \
    --no-align \
    --command="SELECT count(*) FROM tasks;")"

{
    printf 'database=%s\n' "$PGDATABASE"
    printf 'created_at=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    printf 'task_count=%s\n' "$task_count"
} > "$manifest_file"

if ! restic cat config >/dev/null 2>&1; then
    restic init
fi

restic backup "$payload_directory" \
    --host="${BACKUP_HOST:-task-manager}" \
    --tag=postgres \
    --tag="database-${PGDATABASE}"

restic forget \
    --host="${BACKUP_HOST:-task-manager}" \
    --tag=postgres \
    --keep-daily=7 \
    --keep-weekly=4 \
    --keep-monthly=3 \
    --prune

restic check --read-data
restic snapshots --host="${BACKUP_HOST:-task-manager}" --tag=postgres --latest=1
log_event info backup_completed
