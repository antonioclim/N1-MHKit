# Normalisation and interpretation guide

This guide documents how N1-MHKit converts heterogeneous personal monitoring files into reproducible information-system artefacts.

## Levels of measurement

- Session-level variables: blood pressure, heart rate, pulse oximetry, body temperature, environmental measurements and contextual annotations recorded at a measurement session.
- Daily-level variables: sleep and step counts. These variables may be repeated across multiple sessions from the same day and should not be interpreted as independent session-level observations.
- Signal-level objects: WAV phonocardiographic files.
- Report-level objects: ECG PDF reports produced by the recording device.
- Contextual-event variables: activity notes such as coffee, smoking, meal, office activity or medication context.

## Interpretation boundary

The package supports data curation, reproducibility and information-systems evaluation. It does not perform clinical diagnosis, treatment recommendation, waveform-level ECG interpretation or causal health inference.
