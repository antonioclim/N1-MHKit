# N1-MHKit public release

N1-MHKit is a reproducible data-management package for multimodal personal health monitoring information systems. The package organises heterogeneous personal monitoring files into documented, validated and analysis-ready data products.

## Demonstration data

The demonstration data contain 52 timestamped measurement sessions from one adult participant. The modalities include cuff-based blood pressure, smartwatch-derived indicators, pulse oximetry, ECG PDF reports, phonocardiographic WAV audio, environmental measurements and contextual activity notes. The data are provided for research, data-management, reproducibility and software-testing purposes. They are not intended for clinical diagnosis, treatment decisions or population-level health inference.

## Repository structure

- `data_raw/`: source files and a provenance-preserving sanitized raw archive.
- `data_intermediate/`: parsed intermediate tables.
- `data_processed/`: analysis-ready wide and long tables, device-pairing outputs and technical summaries.
- `metadata/`: data dictionary, device dictionary, schema, design-science mapping, design principles and privacy documentation.
- `code/`: scripts for data reproduction, validation, checksums and the optional public-dataset adapter.
- `figures/` and `figures_jcis/`: generated figures with image metadata removed.
- `reports/`: technical validation and missingness reports.

## Reproduction

```bash
pip install -r code/requirements.txt
python code/run_all.py --input-zip data_raw/zenodo_original_15532319.zip --outdir reproduced_outputs
python code/validate_package_v4.py --root . --outdir validation_outputs
python code/reproducibility_smoke_test.py
```

## Scope boundary

This repository supports data-management and reproducibility research. It does not provide clinical advice, diagnosis, treatment guidance or causal health claims.
