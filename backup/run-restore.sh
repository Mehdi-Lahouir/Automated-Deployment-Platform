#!/bin/sh
set -eu

snapshot_id="${SNAPSHOT_ID:-latest}"
target_database="${RESTORE_TARGET_DB:-tasks_restore_test}"
restore_directory="/restore"

log_event() {
    printf '{"timestamp":"%s","level":"%s","service":"backup-agent","event":"%s"}\n' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$1" "$2"
}

case "$snapshot_id" in
    *[!a-zA-Z0-9_-]*|"")
        log_event error configuration_invalid >&2
        exit 2
        ;;
esac

case "$target_database" in
    *[!a-zA-Z0-9_]*|"")
        log_event error configuration_invalid >&2
        exit 2
        ;;
esac

if [ "$target_database" = "$PGDATABASE" ] && [ "${ALLOW_PRODUCTION_RESTORE:-false}" != "true" ]; then
    log_event error production_restore_refused >&2
    exit 2
fi

cleanup() {
    exit_code=$?
    trap - EXIT
    rm -rf "$restore_directory"
    if [ "$exit_code" -ne 0 ]; then
        log_event error restore_failed >&2
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

log_event info restore_started
restic check --read-data
rm -rf "$restore_directory"
mkdir -p "$restore_directory"

restic restore "$snapshot_id" --tag=postgres --target="$restore_directory"

dump_file="$(find "$restore_directory" -type f -name database.dump -print -quit)"
manifest_file="$(find "$restore_directory" -type f -name manifest.env -print -quit)"
if [ -z "$dump_file" ] || [ -z "$manifest_file" ]; then
    exit 1
fi

expected_count="$(sed -n 's/^task_count=//p' "$manifest_file")"
case "$expected_count" in
    *[!0-9]*|"")
        exit 1
        ;;
esac

psql \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname=postgres \
    --set=target="$target_database" \
    --set=ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'target' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"target";
CREATE DATABASE :"target";
SQL

pg_restore \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$target_database" \
    --exit-on-error \
    --no-owner \
    --no-privileges \
    "$dump_file"

table_name="$(psql \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$target_database" \
    --tuples-only \
    --no-align \
    --command="SELECT to_regclass('public.tasks');")"
if [ "$table_name" != "tasks" ]; then
    exit 1
fi

restored_count="$(psql \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$target_database" \
    --tuples-only \
    --no-align \
    --command="SELECT count(*) FROM tasks;")"
if [ "$restored_count" != "$expected_count" ]; then
    exit 1
fi

log_event info restore_verified
