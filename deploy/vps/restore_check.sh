#!/usr/bin/env bash
# Monthly proof that the backups can actually be restored: restore the latest
# restic snapshot into a temp dir, open the restored long-term memory with
# Chroma, list both Postgres dumps, and fail if anything is empty. Run from
# /opt/ciel/deploy/vps by root's crontab with .env sourced (see README.md,
# section 11). Pings Healthchecks.io only when every check passed.
set -euo pipefail

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
if [ "$count" -lt 1 ]; then
  echo "the restored long-term memory is empty" >&2
  exit 1
fi

for name in langflow supabase; do
  dump=$(find "$TMP" -type f -name "$name.dump")
  if [ -z "$dump" ] || [ "$(printf '%s\n' "$dump" | wc -l)" -ne 1 ]; then
    echo "expected exactly one restored $name.dump, found: ${dump:-none}" >&2
    exit 1
  fi
  entries=$(docker run --rm -v "$dump:/dump/$name.dump:ro" postgres:17.2 \
    pg_restore --list "/dump/$name.dump" | grep -vc '^;' || true)
  echo "$name.dump: $entries entries"
  if [ "$entries" -lt 1 ]; then
    echo "$name.dump lists no entries" >&2
    exit 1
  fi
done

curl -fsS -m 10 --retry 3 "$HEALTHCHECKS_RESTORE_URL"
