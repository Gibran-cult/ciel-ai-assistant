#!/usr/bin/env bash
# Deploy what is on main: the VPS counterpart of Streamlit Community Cloud's
# "merge = deploy". Run from /opt/ciel/deploy/app by root's crontab every two
# minutes (README.md, step 7), or by hand.
#
# The app is restarted only after the new image has built. The deployed commit
# is recorded only after the restart, so a failed deploy is not forgotten: it
# is tried again, but at most once an hour, because a failed dependency
# install would otherwise download everything again every two minutes next to
# the live app.
set -euo pipefail

STATE=/var/lib/ciel
DEPLOYED=$STATE/app-deployed
ATTEMPTED=$STATE/app-attempted
RETRY_MINUTES=60

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

main() {
  # One run at a time: a slow build must not overlap the next cron run.
  exec 9>/run/ciel-app-update.lock
  if ! flock -n 9; then
    exit 0
  fi

  git fetch --quiet origin main
  git merge --ff-only origin/main > /dev/null

  local head
  head=$(git rev-parse HEAD)
  if [ -f "$DEPLOYED" ] && [ "$(cat "$DEPLOYED")" = "$head" ]; then
    exit 0
  fi
  # This commit failed less than RETRY_MINUTES ago: wait (or run by hand).
  if [ "${1:-}" != "--now" ] && [ -f "$ATTEMPTED" ] && [ "$(cat "$ATTEMPTED")" = "$head" ] \
    && [ -n "$(find "$ATTEMPTED" -mmin -"$RETRY_MINUTES")" ]; then
    exit 0
  fi

  mkdir -p "$STATE"
  echo "$head" > "$ATTEMPTED"
  echo "$(stamp) deploying $head"
  docker compose build app
  docker compose up -d
  # caddy/ is a directory mount, so the container sees a changed Caddyfile;
  # reloading an unchanged one is a no-op and keeps open connections.
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile

  echo "$head" > "$DEPLOYED"
  rm -f "$ATTEMPTED"
  # Each deploy leaves the previous image untagged; a lockfile change makes
  # that about 1 GB on a 60 GB disk.
  docker image prune -f > /dev/null
  echo "$(stamp) deployed $head"
}

# git merge can replace this file while bash is still reading it. Inside a
# function, the whole body is parsed before any of it runs.
main "$@"
