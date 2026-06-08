# Technical architecture

N1-MHKit is organised around a layered data architecture:

1. Raw layer: original session archives, centralised tables and raw signal/report objects.
2. Intermediate layer: parsed wide tables with harmonised timestamps.
3. Processed layer: analysis-ready wide and long tables, device-pairing outputs and quality-control flags.
4. Metadata layer: schema, dictionaries, provenance notes and privacy documentation.
5. Reporting layer: validation reports, figures and checksums.

The workflow is schema-first: variables are documented with units, source devices, measurement level, processing status and interpretation boundaries.
