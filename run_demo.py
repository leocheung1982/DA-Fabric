#!/usr/bin/env python3
"""
DA-Fabric demo launcher.

Usage:
  python run_demo.py              # print instructions
  python run_demo.py --init       # initialize data
  python run_demo.py --experiments # run all experiments
  python run_demo.py --api        # start FastAPI backend
  python run_demo.py --ui         # start Streamlit UI
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def run_script(script: str) -> int:
    return subprocess.run([sys.executable, str(PROJECT_ROOT / script)], cwd=str(PROJECT_ROOT)).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="DA-Fabric Research Prototype Launcher")
    parser.add_argument("--init", action="store_true", help="Initialize demo data")
    parser.add_argument("--experiments", action="store_true", help="Run all experiments")
    parser.add_argument("--api", action="store_true", help="Start FastAPI backend")
    parser.add_argument("--ui", action="store_true", help="Start Streamlit UI")
    args = parser.parse_args()

    if args.init:
        sys.exit(run_script("scripts/initialize_demo.py"))

    if args.experiments:
        for script in [
            "experiments/run_matching_eval.py",
            "experiments/run_view_eval.py",
            "experiments/run_orchestration_eval.py",
            "experiments/run_proactive_eval.py",
            "experiments/run_ablation_eval.py",
            "experiments/plot_results.py",
        ]:
            print(f"\n{'='*60}\nRunning {script}\n{'='*60}")
            run_script(script)
        return

    if args.api:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--port", "8000"],
            cwd=str(PROJECT_ROOT),
        )
        return

    if args.ui:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py"],
            cwd=str(PROJECT_ROOT),
        )
        return

    print(
        """
DA-Fabric — Demand-Aware Data Fabric Framework (Research Prototype)

Quick start:
  1. pip install -r requirements.txt
  2. python scripts/generate_synthetic_data.py
  3. streamlit run ui/streamlit_app.py

Or use this launcher:
  python run_demo.py --init           # generate data & verify
  python run_demo.py --ui             # start Streamlit demo
  python run_demo.py --api            # start FastAPI (port 8000)
  python run_demo.py --experiments    # run all evaluations
        """
    )


if __name__ == "__main__":
    main()
