# Technical validation report V1.0

## Dataset structure
- Valid timestamped sessions: 52.
- Observation period: 2021-07-19 to 2021-07-26.
- Calendar days represented: 8.
- Core cardiovascular variables from Omron are complete for 52/52 sessions.
- PCG WAV metadata are present for 52/52 sessions.
- ECG PDF report heart-rate values are present for 52/52 sessions.

## Data-quality findings
- ECG data are available as PDF reports; waveform-level ECG reanalysis is not supported in V1.
- PCG WAV files have metadata including sampling rate, channels, sample width and duration. Diagnostic PCG interpretation is not included.
- Daily sleep and step variables are repeated across same-day sessions; inferential analyses must avoid treating them as fully independent session-level repeated measures.
- PM variables are partly missing and highly collinear; PM2.5 should be treated as the primary PM metric for exploratory analyses.

## Interpretation level
The package is appropriate for technical validation, device agreement and exploratory N-of-1 idiographic analysis. It is not appropriate for causal inference, population-level generalisation or clinical decision support.
