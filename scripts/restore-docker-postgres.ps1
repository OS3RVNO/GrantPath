param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$ComposeFile = ".\docker-compose.production.yml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Backup file not found: $InputPath"
}

$containerId = docker compose -f $ComposeFile ps -q postgres
if (-not $containerId) {
    throw "PostgreSQL container not found. Start the production stack first."
}

$containerPath = "/tmp/eip-restore.dump"
docker cp $InputPath "${containerId}:${containerPath}"
docker exec $containerId sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/eip-restore.dump'
docker exec $containerId rm -f $containerPath

Write-Host "Restore completed from $InputPath"
