param(
    [string]$OutputPath = ".\backups\eip-$(Get-Date -Format 'yyyyMMdd-HHmmss').dump",
    [string]$ComposeFile = ".\docker-compose.production.yml"
)

$ErrorActionPreference = "Stop"

$containerId = docker compose -f $ComposeFile ps -q postgres
if (-not $containerId) {
    throw "PostgreSQL container not found. Start the production stack first."
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$containerPath = "/tmp/eip-backup.dump"
docker exec $containerId sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/eip-backup.dump'
docker cp "${containerId}:${containerPath}" $OutputPath
docker exec $containerId rm -f $containerPath

Write-Host "Backup written to $OutputPath"
