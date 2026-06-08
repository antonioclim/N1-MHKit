#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, csv
from pathlib import Path

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    skip={'dataset_manifest.csv','file_checksums_sha256.txt'}
    files=[p for p in root.rglob('*') if p.is_file() and p.name not in skip and '.venv' not in p.parts and 'reproduced_outputs' not in p.parts and 'validation_outputs' not in p.parts]
    rows=[]
    for p in sorted(files):
        rel=str(p.relative_to(root))
        rows.append({'path':rel,'size_bytes':p.stat().st_size,'sha256':sha256(p)})
    with (root/'dataset_manifest.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['path','size_bytes','sha256'])
        w.writeheader(); w.writerows(rows)
    with (root/'file_checksums_sha256.txt').open('w',encoding='utf-8') as f:
        for r in rows:
            f.write(f"{r['sha256']}  {r['path']}\n")
    print(f'wrote {len(rows)} file entries')
if __name__=='__main__': main()
