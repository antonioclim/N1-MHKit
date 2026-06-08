# Privacy risk assessment

The repository contains personal health-monitoring data from one adult participant. Public reuse should be limited to research, data-management, reproducibility and software-testing purposes.

## Risk-sensitive elements

- Health-related measurements, including blood pressure, heart rate, oxygen saturation, ECG-report labels and contextual activity notes.
- Timestamped measurements that may reveal daily routines.
- WAV audio files and ECG PDF reports in the raw archive.

## Mitigations applied in this release

- Public documentation states that the data are not clinical diagnostic evidence.
- Processed tables use session identifiers and do not include names, addresses, emails or telephone numbers.
- Generated PNG figure metadata has been removed.
- Spreadsheet document properties have been removed.
- Common document-information metadata has been removed from ECG PDF reports in the packaged raw archive.
- A plain-text identifier scan is available through `code/validate_package_v4.py`.

## Required depositor confirmation before public release

The depositor should confirm that informed consent, data-protection requirements and publication permissions cover open release of the raw WAV and ECG PDF files. If this cannot be confirmed, release the processed tables and code openly and keep raw WAV/PDF files under restricted access.
