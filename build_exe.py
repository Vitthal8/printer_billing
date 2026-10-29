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

def build_exe() -> None:
    if not ENTRY.exists():
        raise FileNotFoundError(f"Entry script not found: {ENTRY}")
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database file not found: {DB_FILE}")

    ensure_runtime_dirs()

    pyinstaller = [sys.executable, "-m", "PyInstaller"]
    sep = ";" if os.name == "nt" else ":"

    cmd = [
        *pyinstaller,
        "--name", "PrintBillPro",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--add-data", f"{DB_FILE}{sep}.",
        str(ENTRY),
    ]

    print("Running:")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    dist_exe = ROOT / "dist" / ("PrintBillPro.exe" if os.name == "nt" else "PrintBillPro")
    if dist_exe.exists():
        print(f"\nEXE created: {dist_exe}")
    else:
        print("\nBuild finished, but the expected EXE file was not found in dist/.")

if __name__ == "__main__":
    build_exe()