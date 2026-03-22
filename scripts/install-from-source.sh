#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required" >&2
  exit 1
fi

if [[ ! -x "$REPO_ROOT/.venv/bin/python" ]]; then
  python3 -m venv "$REPO_ROOT/.venv"
fi

"$REPO_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$REPO_ROOT/.venv/bin/python" -m pip install -r "$REPO_ROOT/backend/requirements.txt"

cd "$REPO_ROOT/frontend"
npm ci
npm run build

cat <<EOF

GrantPath source install completed.

Run the backend with:
  ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir ./backend

Run the frontend with:
  cd frontend
  npm run dev
EOF
