#!/usr/bin/env python3
"""Validate the public N1-MHKit package structure and processed data.

The validator checks required files, core columns, row counts, plausible ranges,
figures and plain-text identifier patterns. It is a technical validation utility,
not an ethics or legal assessment.
"""
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path
import pandas as pd

REQUIRED_FILES = [
    'README.md', 'CITATION.cff', 'LICENSE_DATA.txt', 'LICENSE_CODE.txt',
    'datapackage.json', 'metadata/data_dictionary.csv', 'metadata/device_dictionary.csv',
    'metadata/schema_measurements_strict_v4.json', 'metadata/artifact_evaluation_matrix.csv',
    'metadata/privacy_risk_assessment.md', 'data_processed/clean_measurements_wide.csv',
    'data_processed/clean_measurements_long.csv', 'data_processed/ecg_pdf_labels.csv',
    'data_processed/pcg_audio_features.csv', 'code/run_all.py'
]
REQUIRED_DIRS = ['code','data_raw','data_processed','metadata','docs','reports','figures','figures_jcis']
REQUIRED_COLUMNS = [
    'session_id','timestamp_local_iso','date_local','day_index','hour_decimal_local',
    'sleep_duration_min','sleep_score','steps_daily','omron_sbp_mmHg','omron_dbp_mmHg',
    'omron_hr_bpm','ppg_spo2_pct','ppg_pulse_bpm','env_temperature_C','env_humidity_pct',
    'env_pressure_hPa','body_temperature_C','ecg_signal_reanalysable'
]
RANGE_CHECKS = {
    'omron_sbp_mmHg': (80,220), 'omron_dbp_mmHg': (40,140), 'omron_hr_bpm': (40,180),
    'ppg_spo2_pct': (70,100), 'ppg_pulse_bpm': (40,180), 'samsung_sbp_mmHg': (80,220),
    'samsung_dbp_mmHg': (40,140), 'samsung_hr_bpm': (40,180), 'samsung_spo2_pct': (70,100),
    'env_temperature_C': (-20,50), 'env_humidity_pct': (0,100), 'env_pressure_hPa': (950,1050),
    'body_temperature_C': (34,42), 'pm1': (0,1000), 'pm2_5': (0,1000), 'pm10': (0,1000),
    'pcg_sampling_rate_Hz': (1000,192000), 'pcg_duration_s': (1,3600), 'ecg_report_hr_bpm': (40,180)
}

def add(rows, level, item, status, message):
    rows.append({'level': level, 'item': item, 'status': status, 'message': message})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.', help='Package root')
    ap.add_argument('--outdir', default='validation_outputs')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    outdir=(root/args.outdir).resolve() if not Path(args.outdir).is_absolute() else Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows=[]
    for d in REQUIRED_DIRS:
        p=root/d
        add(rows,'ERROR' if not p.is_dir() else 'INFO',f'dir:{d}','PASS' if p.is_dir() else 'FAIL', 'required directory present' if p.is_dir() else 'required directory missing')
    for f in REQUIRED_FILES:
        p=root/f
        add(rows,'ERROR' if not p.exists() else 'INFO',f'file:{f}','PASS' if p.exists() else 'FAIL', 'required file present' if p.exists() else 'required file missing')
    wide_path=root/'data_processed/clean_measurements_wide.csv'
    if wide_path.exists():
        df=pd.read_csv(wide_path)
        add(rows,'INFO','clean_measurements_wide row count','PASS' if len(df)==52 else 'FAIL', f'row count = {len(df)}; expected 52')
        missing_cols=[c for c in REQUIRED_COLUMNS if c not in df.columns]
        add(rows,'ERROR' if missing_cols else 'INFO','required columns','PASS' if not missing_cols else 'FAIL', 'missing: '+', '.join(missing_cols) if missing_cols else 'all required columns present')
        if 'date_local' in df.columns:
            dates=pd.to_datetime(df['date_local'], errors='coerce')
            add(rows,'INFO','date range','PASS', f'{dates.min().date()} to {dates.max().date()}')
        for col,(lo,hi) in RANGE_CHECKS.items():
            if col in df.columns:
                s=pd.to_numeric(df[col], errors='coerce').dropna()
                bad=s[(s<lo)|(s>hi)]
                add(rows,'ERROR' if len(bad) else 'INFO',f'range:{col}','PASS' if len(bad)==0 else 'FAIL', f'{len(bad)} values outside [{lo},{hi}]')
        if 'ecg_signal_reanalysable' in df.columns:
            vals=set(str(x).lower() for x in df['ecg_signal_reanalysable'].dropna().unique())
            add(rows,'INFO','ECG signal reanalysable flag','PASS' if vals <= {'false','0'} else 'WARN', f'observed values: {sorted(vals)}')
    patterns={
        'email': re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
        'phone_like': re.compile(r'(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){3,}\d{2,4}'),
        'romanian_cnp_like': re.compile(r'\b[1-9]\d{12}\b')
    }
    findings=[]
    skip={'file_checksums_sha256.txt'}
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.csv','.json','.md','.txt','.cff','.py'} and p.name not in skip:
            txt=p.read_text(encoding='utf-8', errors='ignore')
            for name,pat in patterns.items():
                hits=pat.findall(txt)
                if hits:
                    findings.append({'file': str(p.relative_to(root)), 'pattern': name, 'count': len(hits)})
    if findings:
        add(rows,'WARN','plain-text identifier scan','WARN', f'{len(findings)} files had regex findings; inspect privacy_scan_findings.csv')
        with (outdir/'privacy_scan_findings.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f, fieldnames=['file','pattern','count']); w.writeheader(); w.writerows(findings)
    else:
        add(rows,'INFO','plain-text identifier scan','PASS','no email/phone/CNP-like patterns found in plain text, CSV, JSON, Markdown or Python files')
    with (outdir/'validation_report.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['level','item','status','message'])
        w.writeheader(); w.writerows(rows)
    (outdir/'validation_report.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    n_errors=sum(1 for r in rows if r['level']=='ERROR' and r['status']=='FAIL')
    n_warn=sum(1 for r in rows if r['level']=='WARN')
    print(f'Validation complete: {n_errors} errors, {n_warn} warnings. Report: {outdir/"validation_report.csv"}')
    return 1 if n_errors else 0
if __name__=='__main__':
    raise SystemExit(main())
