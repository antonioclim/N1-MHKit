#!/usr/bin/env python3
"""MHEALTH adapter scaffold for N1-MHKit.

This script maps a local MHEALTH subject log into a minimal N1-MHKit long-format table.
It does not download or redistribute third-party data. Provide the local file path.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Path to a local MHEALTH subject log file')
    ap.add_argument('--outdir', default='external_validation/reproduced_mhealth')
    ap.add_argument('--max-rows', type=int, default=5000)
    args = ap.parse_args()
    inp = Path(args.input)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    # MHEALTH log files are whitespace-delimited; no header in the canonical distribution.
    df = pd.read_csv(inp, sep=r'\s+', header=None, nrows=args.max_rows)
    long_rows = []
    for idx, row in df.iterrows():
        # Use row index as time surrogate when timestamps are not provided.
        for col in df.columns[:-1]:
            long_rows.append({
                'external_dataset': 'MHEALTH',
                'external_record_id': int(idx),
                'time_index': int(idx),
                'variable_name': f'mhealth_col_{col}',
                'value': row[col],
                'unit': 'unknown',
                'source_device': 'MHEALTH wearable sensors',
                'measurement_modality': 'wearable_activity_monitoring',
                'measurement_level': 'sample_level',
                'qc_flag': '',
            })
        long_rows.append({
            'external_dataset': 'MHEALTH',
            'external_record_id': int(idx),
            'time_index': int(idx),
            'variable_name': 'activity_label',
            'value': row[df.columns[-1]],
            'unit': 'category',
            'source_device': 'MHEALTH annotation',
            'measurement_modality': 'activity_context',
            'measurement_level': 'sample_level',
            'qc_flag': '',
        })
    long = pd.DataFrame(long_rows)
    long.to_csv(out/'external_validation_mhealth_long.csv', index=False)
    summary = pd.DataFrame([
        {'metric':'input_rows', 'value': len(df)},
        {'metric':'output_long_rows', 'value': len(long)},
        {'metric':'variables_mapped', 'value': long['variable_name'].nunique()},
        {'metric':'missing_values', 'value': int(long['value'].isna().sum())},
    ])
    summary.to_csv(out/'external_validation_mhealth_summary.csv', index=False)
    print(f'MHEALTH adapter complete: {len(df)} input rows -> {len(long)} long rows. Output: {out}')

if __name__ == '__main__':
    main()
