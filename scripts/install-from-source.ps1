param(
  [string]$PythonExe = "",
  [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = if ($PythonExe) {
  $PythonExe
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  "py -3.13"
} else {
  "python"
}
$VenvPython = Join-Path $RepoRoot ".venv\\Scripts\\python.exe"

if (-not (Test-Path $VenvPython)) {
  if ($PythonExe -eq "py -3.13") {
    py -3.13 -m venv (Join-Path $RepoRoot ".venv")
  } else {
    & $PythonExe -m venv (Join-Path $RepoRoot ".venv")
  }
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RepoRoot "backend\\requirements.txt")

Push-Location (Join-Path $RepoRoot "frontend")
npm ci
if (-not $SkipFrontendBuild) {
  npm run build
}
Pop-Location

Write-Host ""
Write-Host "GrantPath source install completed."
Write-Host "Run the backend with:"
Write-Host "  .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir .\\backend"
Write-Host "Run the frontend with:"
Write-Host "  cd frontend"
Write-Host "  npm run dev"
