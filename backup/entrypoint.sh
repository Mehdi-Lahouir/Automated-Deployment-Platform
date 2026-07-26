#!/bin/sh
set -eu

require_variable() {
    variable_name="$1"
    eval "variable_value=\${$variable_name:-}"
    if [ -z "$variable_value" ]; then
        printf '{"timestamp":"%s","level":"error","service":"backup-agent","event":"configuration_invalid","variable":"%s"}\n' \
            "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$variable_name" >&2
        exit 2
    fi
}

require_variable RESTIC_REPOSITORY
require_variable RESTIC_PASSWORD
require_variable PGHOST
require_variable PGUSER
require_variable PGPASSWORD
require_variable PGDATABASE

export PGPORT="${PGPORT:-5432}"

case "$RESTIC_REPOSITORY" in
    s3:*)
        require_variable AWS_ACCESS_KEY_ID
        require_variable AWS_SECRET_ACCESS_KEY
        ;;
esac

case "${MODE:-backup}" in
    backup)
        exec /usr/local/bin/run-backup.sh
        ;;
    restore)
        exec /usr/local/bin/run-restore.sh
        ;;
    snapshots)
        exec restic snapshots --tag postgres
        ;;
    check)
        exec restic check --read-data
        ;;
    *)
        printf '{"timestamp":"%s","level":"error","service":"backup-agent","event":"configuration_invalid","variable":"MODE"}\n' \
            "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >&2
        exit 2
        ;;
esac
