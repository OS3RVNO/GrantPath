#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
PREFIX="/opt/eip"
SERVICE_USER="eip"
SERVICE_GROUP="eip"
ENV_DIR="/etc/eip"
ENV_FILE="$ENV_DIR/eip.env"
SERVICE_FILE="/etc/systemd/system/eip.service"
INSTALL_POSTGRES=1
APP_ENV="development"
PUBLIC_HOST=""
SCAN_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --prefix)
      PREFIX="$2"
      shift 2
      ;;
    --skip-postgres)
      INSTALL_POSTGRES=0
      shift
      ;;
    --user)
      SERVICE_USER="$2"
      SERVICE_GROUP="$2"
      shift 2
      ;;
    --production-host)
      APP_ENV="production"
      PUBLIC_HOST="$2"
      shift 2
      ;;
    --scan-root)
      SCAN_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd python3

detect_package_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "apt"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    echo "dnf"
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    echo "yum"
    return
  fi
  if command -v zypper >/dev/null 2>&1; then
    echo "zypper"
    return
  fi
  if command -v apk >/dev/null 2>&1; then
    echo "apk"
    return
  fi
  echo ""
}

PACKAGE_MANAGER="$(detect_package_manager)"
if [[ -z "$PACKAGE_MANAGER" ]]; then
  echo "No supported package manager found. Supported: apt-get, dnf, yum, zypper, apk." >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 0 && "$EUID" -ne 0 ]]; then
  echo "Run this installer as root or with sudo." >&2
  exit 1
fi

if [[ "$APP_ENV" == "production" && -z "$PUBLIC_HOST" ]]; then
  echo "Production install requires --production-host <fqdn>." >&2
  exit 1
fi

PACKAGES=(python3 python3-pip acl ca-certificates curl rsync)
if [[ "$PACKAGE_MANAGER" == "apt" ]]; then
  PACKAGES+=(python3-venv)
fi
if [[ ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
  PACKAGES+=(nodejs npm)
fi
if [[ "$INSTALL_POSTGRES" -eq 1 ]]; then
  PACKAGES+=(postgresql)
fi

install_packages() {
  case "$PACKAGE_MANAGER" in
    apt)
      run "apt-get update"
      run "DEBIAN_FRONTEND=noninteractive apt-get install -y ${PACKAGES[*]}"
      ;;
    dnf)
      run "dnf install -y ${PACKAGES[*]}"
      ;;
    yum)
      run "yum install -y ${PACKAGES[*]}"
      ;;
    zypper)
      run "zypper --non-interactive install ${PACKAGES[*]}"
      ;;
    apk)
      run "apk add --no-cache ${PACKAGES[*]}"
      ;;
  esac
}

install_packages

if [[ ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
  run "cd \"$FRONTEND_DIR\" && npm ci && npm run build"
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  run "useradd --system --create-home --home-dir \"$PREFIX\" --shell /usr/sbin/nologin \"$SERVICE_USER\""
fi

run "mkdir -p \"$PREFIX\" \"$ENV_DIR\""
run "rsync -a --delete --exclude .git --exclude node_modules --exclude .venv \"$REPO_ROOT/\" \"$PREFIX/\""
run "python3 -m venv \"$PREFIX/.venv\""
run "\"$PREFIX/.venv/bin/pip\" install --upgrade pip"
run "\"$PREFIX/.venv/bin/pip\" install -r \"$PREFIX/backend/requirements.txt\""

if [[ "$INSTALL_POSTGRES" -eq 1 ]]; then
  DB_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    systemctl enable --now postgresql || true
    su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='eip'\" | grep -q 1 || psql -c \"CREATE USER eip WITH PASSWORD '$DB_PASSWORD';\""
    su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='eip'\" | grep -q 1 || psql -c \"CREATE DATABASE eip OWNER eip;\""
  fi
else
  DB_PASSWORD=""
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -z "$SCAN_ROOT" ]]; then
    SCAN_ROOT="$PREFIX"
  fi
  APP_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  DB_URL_LINE=""
  if [[ "$INSTALL_POSTGRES" -eq 1 ]]; then
    DB_URL_LINE="EIP_DATABASE_URL=postgresql://eip:$DB_PASSWORD@127.0.0.1:5432/eip"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ORIGIN_LINE="EIP_ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000"
    TRUSTED_HOSTS_LINE="EIP_TRUSTED_HOSTS=127.0.0.1,localhost"
    SECURE_COOKIES_LINE="EIP_SECURE_COOKIES=0"
    SCAN_ROOT_LINE=""
    if [[ "$APP_ENV" == "production" ]]; then
      ORIGIN_LINE="EIP_ALLOWED_ORIGINS=https://$PUBLIC_HOST"
      TRUSTED_HOSTS_LINE="EIP_TRUSTED_HOSTS=$PUBLIC_HOST"
      SECURE_COOKIES_LINE="EIP_SECURE_COOKIES=1"
      SCAN_ROOT_LINE="EIP_DEFAULT_SCAN_ROOT=$SCAN_ROOT"
    fi
    cat <<EOF
[dry-run] writing $ENV_FILE
EIP_ENV=$APP_ENV
${DB_URL_LINE}
EIP_DATA_DIR=$PREFIX/backend/data
EIP_FRONTEND_DIST_DIR=$PREFIX/frontend/dist
EIP_APP_SECRET_KEY=$APP_SECRET
$ORIGIN_LINE
$TRUSTED_HOSTS_LINE
$SECURE_COOKIES_LINE
$SCAN_ROOT_LINE
EOF
  else
    ORIGIN_LINE="EIP_ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000"
    TRUSTED_HOSTS_LINE="EIP_TRUSTED_HOSTS=127.0.0.1,localhost"
    SECURE_COOKIES_LINE="EIP_SECURE_COOKIES=0"
    SCAN_ROOT_LINE=""
    if [[ "$APP_ENV" == "production" ]]; then
      ORIGIN_LINE="EIP_ALLOWED_ORIGINS=https://$PUBLIC_HOST"
      TRUSTED_HOSTS_LINE="EIP_TRUSTED_HOSTS=$PUBLIC_HOST"
      SECURE_COOKIES_LINE="EIP_SECURE_COOKIES=1"
      SCAN_ROOT_LINE="EIP_DEFAULT_SCAN_ROOT=$SCAN_ROOT"
    fi
    cat > "$ENV_FILE" <<EOF
EIP_ENV=$APP_ENV
${DB_URL_LINE}
EIP_DATA_DIR=$PREFIX/backend/data
EIP_FRONTEND_DIST_DIR=$PREFIX/frontend/dist
EIP_APP_SECRET_KEY=$APP_SECRET
$ORIGIN_LINE
$TRUSTED_HOSTS_LINE
$SECURE_COOKIES_LINE
$SCAN_ROOT_LINE
EIP_EXPOSE_BOOTSTRAP_DETAILS=0
EIP_ENABLE_SCHEDULER=1
EIP_SCAN_INTERVAL_SECONDS=900
EIP_ENABLE_MATERIALIZED_ACCESS_INDEX=1
EOF
  fi
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  chown -R "$SERVICE_USER:$SERVICE_GROUP" "$PREFIX" "$ENV_DIR"
  mkdir -p "$PREFIX/backend/data"
  chown -R "$SERVICE_USER:$SERVICE_GROUP" "$PREFIX/backend/data"
fi

SERVICE_CONTENT="[Unit]
Description=GrantPath
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PREFIX/backend
EnvironmentFile=$ENV_FILE
ExecStart=$PREFIX/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --app-dir $PREFIX/backend
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] writing $SERVICE_FILE"
  echo "$SERVICE_CONTENT"
else
  printf "%s" "$SERVICE_CONTENT" > "$SERVICE_FILE"
  systemctl daemon-reload
  systemctl enable --now eip.service || true
fi

echo "Linux installation flow prepared."
echo "Application root: $PREFIX"
echo "Environment file: $ENV_FILE"
echo "Systemd service: $SERVICE_FILE"
