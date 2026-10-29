from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "main.py"
DB_FILE = ROOT / "printbill.db"

def ensure_runtime_dirs() -> None:
    for folder in ("invoices", "exports"):
        path = ROOT / folder
        path.mkdir(exist_ok=True)

def build_exe():
    ensure_runtime_dirs()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "PrintBillPro",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--add-data", f"{DB_FILE};.",
        str(ENTRY)
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)

if __name__ == "__main__":
    build_exe()
