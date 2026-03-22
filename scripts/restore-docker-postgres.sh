#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${1:-}"
COMPOSE_FILE="${2:-./docker-compose.production.yml}"

if [[ -z "$INPUT_PATH" ]]; then
  echo "Usage: ./scripts/restore-docker-postgres.sh <backup.dump> [compose-file]" >&2
  exit 1
fi

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "Backup file not found: $INPUT_PATH" >&2
  exit 1
fi

CONTAINER_ID="$(docker compose -f "$COMPOSE_FILE" ps -q postgres)"
if [[ -z "$CONTAINER_ID" ]]; then
  echo "PostgreSQL container not found. Start the production stack first." >&2
  exit 1
fi

CONTAINER_PATH="/tmp/eip-restore.dump"
docker cp "$INPUT_PATH" "${CONTAINER_ID}:${CONTAINER_PATH}"
docker exec "$CONTAINER_ID" sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/eip-restore.dump'
docker exec "$CONTAINER_ID" rm -f "$CONTAINER_PATH"

echo "Restore completed from $INPUT_PATH"
