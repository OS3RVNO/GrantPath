from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_DIR = BACKEND_ROOT / "data-test"

if TEST_DATA_DIR.exists():
    shutil.rmtree(TEST_DATA_DIR)

os.environ.setdefault("EIP_DATA_DIR", str(TEST_DATA_DIR))
os.environ.setdefault("EIP_DISABLE_AUTOSCAN", "1")
os.environ.setdefault("EIP_ADMIN_USERNAME", "admin")
os.environ.setdefault("EIP_ADMIN_PASSWORD", "TestAdminPassword!2026")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
