#!/usr/bin/env bash
# Monthly proof that the backups can actually be restored: restore the latest
# restic snapshot into a temp dir, open the restored long-term memory with
# Chroma, list both Postgres dumps, and fail if anything is empty. Run from
# /opt/ciel/deploy/vps by root's crontab with .env sourced (see README.md,
# section 11). Pings Healthchecks.io only when every check passed.
set -euo pipefail

# One run at a time (a run started by hand while cron runs one would fill the disk twice).
exec 9>/var/lock/ciel-restore.lock
if ! flock -n 9; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) another restore check is still running: not started" >&2
  exit 1
fi

# Fail closed: a count that is not a whole number (an error message, an empty
# string) must fail the check, never pass it. "$1" names the check, "$2" is the count.
require_positive_count() {
  case $2 in
    ''|*[!0-9]*)
      echo "$1: expected a number, got '$2'" >&2
      exit 1
      ;;
  esac
  [ "$2" -ge 1 ] || { echo "$1 is empty" >&2; exit 1; }
}

# The restore lands in /var/tmp, on the same disk as Langflow and Postgres:
# refuse to start unless at least twice the latest snapshot's size is free.
need=$(restic stats latest --mode restore-size --json \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["total_size"])')
require_positive_count "latest snapshot restore size" "$need"
free=$(df --output=avail -B1 /var/tmp | tail -n 1 | tr -dc '0-9')
require_positive_count "free bytes in /var/tmp" "$free"
if [ "$free" -lt $((2 * need)) ]; then
  echo "only $free bytes free in /var/tmp, need $((2 * need)) (2x the latest snapshot): restore not started" >&2
  exit 1
fi

TMP=$(mktemp -d /var/tmp/ciel-restore.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

restic restore latest --target "$TMP"

# restic restores absolute paths below the target: the Langflow volume's
# mountpoint and the backup work dir.
memory=$(find "$TMP" -type d -name long_term_memory -path '*/.ciel_ai/*')
if [ -z "$memory" ] || [ "$(printf '%s\n' "$memory" | wc -l)" -ne 1 ]; then
  echo "expected exactly one restored long_term_memory directory, found: ${memory:-none}" >&2
  exit 1
fi

# Chroma needs a writable copy (SQLite), and the files keep their original
# owner, so run as root against this throwaway restore.
count=$(docker run --rm --user root --entrypoint python \
  -e "MEMORY_DIR=/restore${memory#"$TMP"}" -v "$TMP:/restore" \
  langflowai/langflow:1.12.4 -c "
import os
import chromadb
client = chromadb.PersistentClient(path=os.environ['MEMORY_DIR'])
print(client.get_collection('ciel_long_term_memory').count())
")
echo "restored long-term memories: $count"
require_positive_count "restored long-term memory" "$count"

for name in langflow supabase; do
  dump=$(find "$TMP" -type f -name "$name.dump")
  if [ -z "$dump" ] || [ "$(printf '%s\n' "$dump" | wc -l)" -ne 1 ]; then
    echo "expected exactly one restored $name.dump, found: ${dump:-none}" >&2
    exit 1
  fi
  entries=$(docker run --rm -v "$dump:/dump/$name.dump:ro" postgres:17.2 \
    pg_restore --list "/dump/$name.dump" | grep -vc '^;' || true)
  echo "$name.dump: $entries entries"
  require_positive_count "$name.dump entries" "$entries"
done

curl -fsS -m 10 --retry 3 "$HEALTHCHECKS_RESTORE_URL"
