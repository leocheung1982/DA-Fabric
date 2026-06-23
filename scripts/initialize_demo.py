#!/usr/bin/env python3
"""Initialize demo environment — generate data and verify imports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    print("Initializing DA-Fabric demo environment...")

    # Generate synthetic data
    gen_script = PROJECT_ROOT / "scripts" / "generate_synthetic_data.py"
    subprocess.run([sys.executable, str(gen_script)], check=True)

    # Verify core imports
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.service_layer import DAFabricService

    service = DAFabricService(PROJECT_ROOT)
    counts = service.initialize()
    print(f"Service initialized: {counts}")
    print(f"Status: {service.get_status()}")
    print("\nDemo ready. Run:")
    print("  streamlit run ui/streamlit_app.py")
    print("  python run_demo.py --api")


if __name__ == "__main__":
    main()
