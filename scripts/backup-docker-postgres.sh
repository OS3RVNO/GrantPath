#!/usr/bin/env bash
set -euo pipefail

OUTPUT_PATH="${1:-./backups/eip-$(date +%Y%m%d-%H%M%S).dump}"
COMPOSE_FILE="${2:-./docker-compose.production.yml}"

CONTAINER_ID="$(docker compose -f "$COMPOSE_FILE" ps -q postgres)"
if [[ -z "$CONTAINER_ID" ]]; then
  echo "PostgreSQL container not found. Start the production stack first." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"
CONTAINER_PATH="/tmp/eip-backup.dump"

docker exec "$CONTAINER_ID" sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/eip-backup.dump'
docker cp "${CONTAINER_ID}:${CONTAINER_PATH}" "$OUTPUT_PATH"
docker exec "$CONTAINER_ID" rm -f "$CONTAINER_PATH"

echo "Backup written to $OUTPUT_PATH"
