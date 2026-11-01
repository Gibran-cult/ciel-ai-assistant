#!/usr/bin/env bash
# Deploy what is on main: the VPS counterpart of Streamlit Community Cloud's
# "merge = deploy". Run from /opt/ciel/deploy/app by root's crontab every two
# minutes (README.md, step 7), or by hand.
#
# The app is restarted only after the new image has built. The deployed commit
# is recorded only after the restart, so a failed build is tried again on the
# next run (and logged each time) instead of being skipped.
set -euo pipefail

DEPLOYED=/var/lib/ciel/app-deployed

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

  echo "$(stamp) deploying $head"
  docker compose build app
  docker compose up -d
  # The Caddyfile is a bind mount: a changed file needs a reload, not a
  # recreate. Reloading an unchanged one is harmless.
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile

  mkdir -p "$(dirname "$DEPLOYED")"
  echo "$head" > "$DEPLOYED"
  echo "$(stamp) deployed $head"
}

# git merge can replace this file while bash is still reading it. Inside a
# function, the whole body is parsed before any of it runs.
main "$@"
