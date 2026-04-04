"""
Download the Kaggle dataset to data/predictive_maintenance.csv.

Prerequisites:
    pip install kaggle
    Set KAGGLE_USERNAME and KAGGLE_KEY environment variables
    (or place ~/.kaggle/kaggle.json with your credentials)

Usage:
    python scripts/download_data.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

DATASET = "shivamb/machine-predictive-maintenance-classification"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
TARGET_FILE = OUTPUT_DIR / "predictive_maintenance.csv"


def main():
    if TARGET_FILE.exists():
        print(f"Dataset already exists: {TARGET_FILE}")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    try:
        import kaggle  # noqa: F401
    except ImportError:
        print("Installing kaggle package...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle", "-q"])

    print(f"Downloading dataset: {DATASET}")
    subprocess.check_call([
        sys.executable, "-m", "kaggle", "datasets", "download",
        "-d", DATASET,
        "-p", str(OUTPUT_DIR),
        "--unzip",
    ])

    # Kaggle extracts to a file named predictive_maintenance.csv
    downloaded = OUTPUT_DIR / "predictive_maintenance.csv"
    if not downloaded.exists():
        # Try to find the CSV if the name differs
        csvs = list(OUTPUT_DIR.glob("*.csv"))
        if csvs:
            shutil.move(str(csvs[0]), str(TARGET_FILE))
        else:
            print("ERROR: CSV not found after download. Check the Kaggle dataset.")
            sys.exit(1)

    print(f"Dataset saved to: {TARGET_FILE}")
    import pandas as pd
    df = pd.read_csv(TARGET_FILE)
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
