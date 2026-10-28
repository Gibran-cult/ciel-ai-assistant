#!/usr/bin/env bash
# Nightly off-site backup of everything the VPS cannot rebuild: Langflow's
# Postgres, Langflow's home volume (long-term memory in Chroma, uploads) and
# Supabase (its free plan has no backups of its own). Encrypted by restic and
# sent to Cloudflare R2. Run from /opt/ciel/deploy/vps by root's crontab, with
# .env sourced first (see README.md, section 11).
#
# Fails without pinging Healthchecks.io, so a missed ping is the alarm.
set -euo pipefail

# 1. Refuse to start on a nearly full disk: dumps and the restic cache need room.
used=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
if [ "$used" -gt 80 ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) disk is ${used}% full (limit 80%): backup not started" >&2
  exit 1
fi

# One fixed work path: restic forget groups snapshots by host and paths, so a
# random temp dir would put every night in its own group and nothing would be pruned.
WORK=/var/tmp/ciel-backup-work
rm -rf "$WORK"
mkdir -m 700 "$WORK"
trap 'rm -rf "$WORK"' ERR  # the dumps hold user data: never leave them behind

# 2. Langflow's own database (flows, users, API keys, encrypted credentials).
docker compose exec -T postgres pg_dump -U langflow -Fc langflow > "$WORK/langflow.dump"

# 3. Supabase (chat history, Pro quotas, payments). SUPABASE_DB_URL is the
# Session pooler connection string: the direct host is IPv6-only on the free
# plan and Docker containers have no IPv6, so run on the host network.
docker run --rm --network host postgres:17.2 pg_dump -Fc "$SUPABASE_DB_URL" > "$WORK/supabase.dump"

# 4. Langflow's home volume holds Chroma files that must not change mid-copy:
# pause Langflow for the duration of the snapshot. The trap goes first so an
# error or a signal can never leave it paused.
project=${COMPOSE_PROJECT_NAME:-vps}
volume=$(docker volume ls -q \
  --filter "label=com.docker.compose.project=$project" \
  --filter "label=com.docker.compose.volume=langflow_home")
if [ -z "$volume" ] || [ "$(printf '%s\n' "$volume" | wc -l)" -ne 1 ]; then
  echo "expected exactly one langflow_home volume in project $project, found: ${volume:-none}" >&2
  exit 1
fi
mountpoint=$(docker volume inspect --format '{{ .Mountpoint }}' "$volume")

trap 'docker compose unpause langflow' EXIT
docker compose pause langflow
restic backup "$mountpoint" "$WORK"
docker compose unpause langflow
trap - EXIT

# 5. About five weeks of history: 7 daily + 4 weekly snapshots.
restic forget --keep-daily 7 --keep-weekly 4 --prune

rm -rf "$WORK"

# 6. Tell Healthchecks.io it worked.
curl -fsS -m 10 --retry 3 "$HEALTHCHECKS_BACKUP_URL"
