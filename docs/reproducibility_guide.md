# Reproducibility guide

Run the following commands from the repository root:

```bash
pip install -r code/requirements.txt
python code/run_all.py --input-zip data_raw/zenodo_original_15532319.zip --outdir reproduced_outputs
python code/validate_package_v4.py --root . --outdir validation_outputs
python code/reproducibility_smoke_test.py
```

Expected outputs include clean wide and long measurement tables, technical summaries, device-pairing outputs and regenerated figures.
