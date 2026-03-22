from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_DIR = BACKEND_ROOT / "data-test"
TEST_SCAN_ROOT = TEST_DATA_DIR / "scan-root"

if TEST_DATA_DIR.exists():
    shutil.rmtree(TEST_DATA_DIR)

os.environ.setdefault("EIP_DATA_DIR", str(TEST_DATA_DIR))
os.environ.setdefault("EIP_DISABLE_AUTOSCAN", "1")
os.environ.setdefault("EIP_ADMIN_USERNAME", "admin")
os.environ.setdefault("EIP_ADMIN_PASSWORD", "TestAdminPassword!2026")
os.environ.setdefault("EIP_DEFAULT_SCAN_ROOT", str(TEST_SCAN_ROOT))

TEST_SCAN_ROOT.mkdir(parents=True, exist_ok=True)
(TEST_SCAN_ROOT / "finance").mkdir(exist_ok=True)
(TEST_SCAN_ROOT / "finance" / "budgets").mkdir(exist_ok=True)
(TEST_SCAN_ROOT / "engineering").mkdir(exist_ok=True)
(TEST_SCAN_ROOT / "finance" / "budget-2026.txt").write_text(
    "budget, access, and ownership validation fixture\n",
    encoding="utf-8",
)
(TEST_SCAN_ROOT / "finance" / "budgets" / "Q1.csv").write_text(
    "month,amount\njan,1200\nfeb,1250\n",
    encoding="utf-8",
)
(TEST_SCAN_ROOT / "engineering" / "deploy.ps1").write_text(
    "Write-Host 'deployment fixture'\n",
    encoding="utf-8",
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
