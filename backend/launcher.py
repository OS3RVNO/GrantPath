from __future__ import annotations

import os
from pathlib import Path
import sys
import threading
import webbrowser

import uvicorn


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _configure_environment() -> tuple[str, int, str]:
    root = _bundle_root()
    local_app_data = Path(os.getenv("LOCALAPPDATA", str(root / "data")))
    data_dir = local_app_data / "GrantPath" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    frontend_dist = root / "frontend_dist"
    if frontend_dist.exists():
        os.environ.setdefault("EIP_FRONTEND_DIST_DIR", str(frontend_dist))

    os.environ.setdefault("EIP_ENV", "production")
    os.environ.setdefault("EIP_SECURE_COOKIES", "0")
    os.environ.setdefault("EIP_ALLOWED_ORIGINS", "http://127.0.0.1:8877,http://localhost:8877")
    os.environ.setdefault("EIP_TRUSTED_HOSTS", "127.0.0.1,localhost")
    os.environ.setdefault("EIP_DATA_DIR", str(data_dir))

    host = os.getenv("EIP_HOST", "127.0.0.1")
    port = int(os.getenv("EIP_PORT", "8877"))
    url = f"http://{host}:{port}"
    return host, port, url


def _open_browser(url: str) -> None:
    if os.getenv("EIP_OPEN_BROWSER", "1") != "1":
        return

    timer = threading.Timer(1.5, lambda: webbrowser.open(url, new=1))
    timer.daemon = True
    timer.start()


def main() -> None:
    host, port, url = _configure_environment()
    _open_browser(url)
    from app.main import app

    uvicorn.run(app, host=host, port=port, proxy_headers=False, workers=1)


if __name__ == "__main__":
    main()
