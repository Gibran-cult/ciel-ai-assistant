#!/usr/bin/env bash
# Nightly off-site backup of everything the VPS cannot rebuild: Langflow's
# Postgres, Langflow's home volume (long-term memory in Chroma, uploads) and
# Supabase (its free plan has no backups of its own). Encrypted by restic and
# sent to Cloudflare R2. Run from /opt/ciel/deploy/vps by root's crontab, with
# .env sourced first (see README.md, section 11).
#
# Fails without pinging Healthchecks.io, so a missed ping is the alarm.
set -euo pipefail

# One run at a time: a second run would delete the first one's work dir and
# pause Langflow twice. Fails (no ping) when a backup is still running.
exec 9>/var/lock/ciel-backup.lock
if ! flock -n 9; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) another backup is still running: not started" >&2
  exit 1
fi

# One fixed work path: restic forget groups snapshots by host and paths, so a
# random temp dir would put every night in its own group and nothing would be pruned.
WORK=/var/tmp/ciel-backup-work

# A leftover from a run that was killed (power loss, SIGKILL) holds unencrypted
# dumps and eats disk space: remove it before anything else, including the disk check.
rm -rf "$WORK"

# Everything cheap that can fail comes before the dumps, so a missing setting
# never leaves a dump behind. (set -u would abort mid-run on an unset name.)
: "${SUPABASE_DB_URL:?}" "${RESTIC_REPOSITORY:?}" "${RESTIC_PASSWORD:?}"
: "${AWS_ACCESS_KEY_ID:?}" "${AWS_SECRET_ACCESS_KEY:?}" "${HEALTHCHECKS_BACKUP_URL:?}"

# 1. Refuse to start on a nearly full disk: dumps and the restic cache need room.
used=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
if [ "$used" -gt 80 ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) disk is ${used}% full (limit 80%): backup not started" >&2
  exit 1
fi

# Langflow's home volume holds Chroma files that must not change mid-copy.
project=${COMPOSE_PROJECT_NAME:-vps}
volume=$(docker volume ls -q \
  --filter "label=com.docker.compose.project=$project" \
  --filter "label=com.docker.compose.volume=langflow_home")
if [ -z "$volume" ] || [ "$(printf '%s\n' "$volume" | wc -l)" -ne 1 ]; then
  echo "expected exactly one langflow_home volume in project $project, found: ${volume:-none}" >&2
  exit 1
fi
mountpoint=$(docker volume inspect --format '{{ .Mountpoint }}' "$volume")

# One EXIT trap for every way out (success, error, set -e, a signal): never leave
# Langflow paused and never leave the unencrypted dumps behind. It goes first,
# before the work dir exists and before Langflow is paused.
paused=0
cleanup() {
  if [ "$paused" = 1 ]; then
    docker compose unpause langflow || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT
trap 'exit 1' INT TERM HUP  # exit runs the EXIT trap, with a non-zero status

mkdir -m 700 "$WORK"

# 2. Langflow's own database (flows, users, API keys, encrypted credentials).
docker compose exec -T postgres pg_dump -U langflow -Fc langflow > "$WORK/langflow.dump"

# 3. Supabase (chat history, Pro quotas, payments). SUPABASE_DB_URL is the
# Session pooler connection string: the direct host is IPv6-only on the free
# plan and Docker containers have no IPv6, so run on the host network.
docker run --rm --network host postgres:17.2 pg_dump -Fc "$SUPABASE_DB_URL" > "$WORK/supabase.dump"

# 4. Pause Langflow for the duration of the snapshot, at most 45 minutes: a hung
# upload must not keep Ciel down (timeout fails the run; the EXIT trap unpauses).
paused=1
docker compose pause langflow
timeout 45m restic backup "$mountpoint" "$WORK"
docker compose unpause langflow
paused=0

# 5. About five weeks of history: 7 daily + 4 weekly snapshots.
restic forget --keep-daily 7 --keep-weekly 4 --prune

rm -rf "$WORK"

# 6. Tell Healthchecks.io it worked.
curl -fsS -m 10 --retry 3 "$HEALTHCHECKS_BACKUP_URL"
