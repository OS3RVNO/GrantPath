param(
  [string]$PythonExe = "",
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = if ($PythonExe) { $PythonExe } else { Join-Path $RepoRoot ".venv\Scripts\python.exe" }
$OutputDir = if ($OutputDir) { $OutputDir } else { Join-Path $RepoRoot "dist\windows" }
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendDir = Join-Path $RepoRoot "backend"
$DistDir = Join-Path $FrontendDir "dist"
$SpecDir = Join-Path $RepoRoot "build\pyinstaller"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null

Push-Location $FrontendDir
npm ci
npm run build
Pop-Location

& $PythonExe -m pip install pyinstaller

$PyInstallerArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onedir",
  "--name", "GrantPath",
  "--distpath", $OutputDir,
  "--workpath", (Join-Path $RepoRoot "build\pyinstaller\work"),
  "--specpath", $SpecDir,
  "--add-data", "$DistDir;frontend_dist",
  "--paths", $BackendDir,
  (Join-Path $BackendDir "launcher.py")
)

& $PythonExe @PyInstallerArgs

Write-Host ""
Write-Host "Windows package generated in $OutputDir\GrantPath"
