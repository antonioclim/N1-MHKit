#!/usr/bin/env python3
"""Minimal smoke test for the reconstructed N-of-1 multimodal health dataset package.

Run from the root of the extracted Zenodo package:
    python code/reproducibility_smoke_test.py
"""
from pathlib import Path
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "data_raw" / "zenodo_original_15532319.zip",
    ROOT / "data_processed" / "clean_measurements_wide.csv",
    ROOT / "data_processed" / "qc_flags.csv",
    ROOT / "metadata" / "data_dictionary.csv",
    ROOT / "code" / "run_all.py",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("Missing required files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)

wide = pd.read_csv(ROOT / "data_processed" / "clean_measurements_wide.csv")
qc = pd.read_csv(ROOT / "data_processed" / "qc_flags.csv")

checks = {
    "measurement_sessions": len(wide) == 52,
    "unique_calendar_days": wide["date_local"].nunique() == 8,
    "core_omron_complete": wide[["omron_sbp_mmHg", "omron_dbp_mmHg", "omron_hr_bpm"]].notna().all().all(),
    "qc_row_alignment": len(qc) == len(wide),
    "pcg_metadata_present": wide["pcg_duration_s"].notna().sum() == 52,
    "ecg_report_hr_present": wide["ecg_report_hr_bpm"].notna().sum() == 52,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    print("Smoke test failed:")
    for f in failed:
        print(" -", f)
    sys.exit(1)

print("Smoke test passed.")
for k in checks:
    print(f" - {k}: OK")
