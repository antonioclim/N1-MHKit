.PHONY: reproduce validate smoke checksums

reproduce:
	python code/run_all.py --input-zip data_raw/zenodo_original_15532319.zip --outdir reproduced_outputs

validate:
	python code/validate_package_v4.py --root . --outdir validation_outputs

smoke:
	python code/reproducibility_smoke_test.py

checksums:
	python code/generate_manifest_checksums.py --root .
