#!/usr/bin/env python3
"""Reset data to freshly generated synthetic seed data."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    print("Resetting DA-Fabric data...")
    gen_script = PROJECT_ROOT / "scripts" / "generate_synthetic_data.py"
    subprocess.run([sys.executable, str(gen_script)], check=True)

    results_dir = PROJECT_ROOT / "results"
    for csv in results_dir.glob("*.csv"):
        csv.unlink()
        print(f"  Removed {csv.name}")

    print("Reset complete.")


if __name__ == "__main__":
    main()
