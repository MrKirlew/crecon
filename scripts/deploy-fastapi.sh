#!/usr/bin/env bash
set -euo pipefail

SERVER=${DEPLOY_SERVER:-root@5.78.92.210}
REMOTE_DIR=${DEPLOY_REMOTE_DIR:-/opt/ai-assistant/crecon}
SERVICE=${DEPLOY_SERVICE:-fastapi}
COMPOSE_BIN=${DEPLOY_COMPOSE_BIN:-docker compose}

ssh "$SERVER" bash -lc "'
  set -e
  cd $REMOTE_DIR
  echo \"[1/4] Updating repo...\"
  git pull --ff-only

  echo \"[2/4] Rebuilding $SERVICE...\"
  $COMPOSE_BIN up --build -d $SERVICE

  echo \"[3/4] Applying migrations...\"
  if [ -f scripts/migrate.sh ]; then
    ./scripts/migrate.sh || true
  fi

  echo \"[4/4] Recent logs:\"
  $COMPOSE_BIN logs --tail=50 $SERVICE
'"
