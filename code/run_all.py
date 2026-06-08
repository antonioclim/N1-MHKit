#!/usr/bin/env python3
"""Reproducible pipeline for the Multimodal N-of-1 Health Monitoring Dataset.

Usage:
    python run_all.py --input-zip data_raw/zenodo_original_15532319.zip --outdir reproduced_outputs

The script parses the centralised CSV in the original Zenodo archive, validates file structure,
creates analysis-ready tables, QC reports, descriptive statistics, device-agreement summaries,
exploratory correlations and figures.
"""
from __future__ import annotations
import argparse, csv, io, zipfile, re, math, contextlib, wave, tempfile, shutil, subprocess
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt


def parse_zip_dt(name: str):
    m = re.match(r'(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(am|pm)(?:\.zip)?$', name)
    if not m:
        return None
    y, mo, d, h, mi, s, ap = m.groups()
    h = int(h)
    if ap == 'pm' and h != 12:
        h += 12
    if ap == 'am' and h == 12:
        h = 0
    return datetime(int(y), int(mo), int(d), h, int(mi), int(s))


def clean_num(s):
    if s is None:
        return np.nan
    s = str(s).strip().replace('%', '').replace('bpm', '').replace('BPM', '').replace(',', '.')
    if not s or s.upper() in {'N/A', 'NA'}:
        return np.nan
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else np.nan


def parse_bp(s):
    nums = re.findall(r'\d+', str(s or ''))
    if len(nums) >= 3:
        return tuple(map(float, nums[:3]))
    return (np.nan, np.nan, np.nan)


def parse_samsung(s):
    s = str(s or '')
    sys = dia = pulse = spo2 = np.nan
    m = re.search(r'(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', s)
    if m:
        sys, dia, pulse = map(float, m.groups())
    sm = re.search(r'SpO\s*2\s*(\d+)', s, re.I) or re.search(r'SpO2\s*(\d+)', s, re.I)
    if sm:
        spo2 = float(sm.group(1))
    rhythm = 'sinus' if re.search(r'sin|syn', s, re.I) else ''
    return sys, dia, pulse, spo2, rhythm


def parse_sleep(s):
    res = {}
    s = str(s or '')
    m = re.search(r'(\d+):(\d+)\s*h', s)
    if m:
        res['sleep_duration_min'] = int(m.group(1))*60 + int(m.group(2))
    m = re.search(r'sleep score\s*(\d+)', s, re.I)
    if m:
        res['sleep_score'] = float(m.group(1))
    for key in ['REM', 'light', 'deep', 'awake']:
        m = re.search(key + r'\s*(\d+)%?', s, re.I)
        if m:
            res[key.lower() + '_pct'] = float(m.group(1))
    return res


def parse_steps(s):
    s = str(s or '')
    m = re.search(r'(?:total|plus|after)\s*(\d+)\s*steps', s, re.I) or re.search(r'(\d+)\s*steps', s, re.I)
    return int(m.group(1)) if m else np.nan


def bh(pvals):
    pvals = np.asarray(pvals, dtype=float)
    m = len(pvals)
    order = np.argsort(pvals)
    qvals = np.empty(m)
    minq = 1.0
    for j in range(m-1, -1, -1):
        k = order[j]
        minq = min(minq, pvals[k] * m / (j + 1))
        qvals[k] = minq
    return qvals


def parse_centralised(input_zip: Path, outdir: Path):
    zf = zipfile.ZipFile(input_zip)
    names = zf.namelist()
    central_name = next((n for n in names if Path(n).name == 'Centralised Data.csv'), None)
    if central_name is None:
        raise RuntimeError('Centralised Data.csv not found in input archive')
    rows = list(csv.reader(io.StringIO(zf.read(central_name).decode('utf-8-sig'))))
    session_zips = sorted([Path(n).name for n in names if re.match(r'2021_.*\.zip$', Path(n).name)], key=lambda n: parse_zip_dt(Path(n).stem))
    record_rows = []
    for idx, row in enumerate(rows):
        if row and row[0].strip().isdigit():
            n = int(row[0])
            if 1 <= n <= 52:
                record_rows.append((idx, n, row))
    sleep_by_date, steps_by_date = {}, {}
    current_date = None
    for idx, n, row in record_rows:
        dt = parse_zip_dt(Path(session_zips[n-1]).stem)
        if dt is None:
            continue
        s = row[1] if len(row) > 1 else ''
        if 'sleep score' in s:
            current_date = dt.date()
            sleep_by_date[current_date] = parse_sleep(s)
        # scan row and nearby rows for total steps
        for rr in rows[idx:idx+4]:
            step = parse_steps(rr[1] if len(rr)>1 else '')
            if not (isinstance(step, float) and math.isnan(step)):
                steps_by_date[dt.date()] = step
                break
    recs = []
    for idx, n, row in record_rows:
        zipname = session_zips[n-1]
        dt = parse_zip_dt(Path(zipname).stem)
        sleep = sleep_by_date.get(dt.date(), {}) if dt else {}
        sys, dia, hr = parse_bp(row[4] if len(row)>4 else '')
        swsys, swdia, swh, swspo2, rhythm = parse_samsung(row[12] if len(row)>12 else '')
        act = row[15] if len(row)>15 else ''
        stress_label = (row[13] if len(row)>13 else '').strip()
        stress_map = {'low stress':1, 'medium stress':2, 'high stress':3}
        r = {
            'session_id': n,
            'timestamp_local_iso': dt.strftime('%Y-%m-%dT%H:%M:%S+03:00') if dt else '',
            'datetime': dt,
            'date_local': dt.date().isoformat() if dt else '',
            'day_index': (dt.date() - parse_zip_dt(Path(session_zips[0]).stem).date()).days + 1 if dt else np.nan,
            'hour_decimal_local': dt.hour + dt.minute/60 + dt.second/3600 if dt else np.nan,
            'raw_session_zip': zipname,
            'sleep_duration_min': sleep.get('sleep_duration_min', np.nan),
            'sleep_score': sleep.get('sleep_score', np.nan),
            'rem_pct': sleep.get('rem_pct', np.nan),
            'light_pct': sleep.get('light_pct', np.nan),
            'deep_pct': sleep.get('deep_pct', np.nan),
            'awake_pct': sleep.get('awake_pct', np.nan),
            'steps_daily': steps_by_date.get(dt.date(), np.nan) if dt else np.nan,
            'omron_sbp_mmHg': sys, 'omron_dbp_mmHg': dia, 'omron_hr_bpm': hr,
            'env_temperature_C': clean_num(row[6] if len(row)>6 else ''),
            'env_humidity_pct': clean_num(row[7] if len(row)>7 else ''),
            'env_pressure_hPa': clean_num(row[8] if len(row)>8 else ''),
            'body_temperature_C': clean_num(row[9] if len(row)>9 else ''),
            'ppg_spo2_pct': clean_num(row[10] if len(row)>10 else ''),
            'ppg_pulse_bpm': clean_num(row[11] if len(row)>11 else ''),
            'samsung_sbp_mmHg': swsys, 'samsung_dbp_mmHg': swdia, 'samsung_hr_bpm': swh, 'samsung_spo2_pct': swspo2,
            'samsung_rhythm_label': rhythm, 'samsung_stress_label': stress_label, 'samsung_stress_ordinal': stress_map.get(stress_label.lower(), np.nan),
            'activity': act, 'smoking_flag': int(bool(re.search('smok', act, re.I))), 'coffee_flag': int(bool(re.search('cof', act, re.I))), 'beer_flag': int(bool(re.search('beer', act, re.I))), 'office_flag': int(bool(re.search('office', act, re.I))), 'meal_flag': int(bool(re.search('breakfast|lunch|dinner|brunch', act, re.I))),
            'pm1': clean_num(row[16] if len(row)>16 else ''), 'pm2_5': clean_num(row[17] if len(row)>17 else ''), 'pm10': clean_num(row[18] if len(row)>18 else ''),
            'weather': (row[19] if len(row)>19 else '').strip(), 'wake_med_notes': (row[20] if len(row)>20 else '').strip(),
        }
        r['pulse_pressure_mmHg'] = r['omron_sbp_mmHg'] - r['omron_dbp_mmHg']
        r['map_estimated_mmHg'] = r['omron_dbp_mmHg'] + r['pulse_pressure_mmHg']/3
        recs.append(r)
    df = pd.DataFrame(recs).sort_values('datetime').reset_index(drop=True)
    return df



def load_cached_ecg_metadata():
    """Load cached ECG PDF report metadata from the package, if available.

    This keeps the default pipeline fast and deterministic. Use --parse-ecg-pdfs
    only when raw PDF text extraction must be repeated from the session archives.
    """
    try:
        root = Path(__file__).resolve().parents[1]
        cache = root / 'data_processed' / 'ecg_pdf_labels.csv'
        if cache.exists():
            cached = pd.read_csv(cache)
            if 'raw_session_zip' in cached.columns:
                return cached.set_index('raw_session_zip').to_dict(orient='index')
    except Exception:
        pass
    return {}


def add_nested_metadata(input_zip: Path, df: pd.DataFrame, tmpdir: Path, parse_ecg_pdfs: bool = False):
    """Add WAV metadata and ECG report metadata.

    By default, WAV metadata are regenerated from raw nested archives, while ECG
    report metadata are loaded from the cached package table when available. This
    avoids slow and platform-dependent PDF text extraction during routine reviewer
    reproduction. To force raw PDF parsing, run with --parse-ecg-pdfs.
    """
    tmpdir.mkdir(parents=True, exist_ok=True)
    wav_meta, ecg_meta = {}, {}
    cached_ecg = load_cached_ecg_metadata() if not parse_ecg_pdfs else {}
    pdftotext_path = shutil.which('pdftotext') if parse_ecg_pdfs else None
    with zipfile.ZipFile(input_zip) as outer:
        outer_names = set(outer.namelist())
        for zname in df['raw_session_zip'].dropna().astype(str).unique():
            if zname not in outer_names:
                continue
            with outer.open(zname) as fh:
                nested_bytes = fh.read()
            with zipfile.ZipFile(io.BytesIO(nested_bytes)) as inner:
                names = inner.namelist()
                wav_name = next((n for n in names if n.endswith('recording.wav')), None)
                if wav_name:
                    wav_path = tmpdir / (Path(zname).stem + '_recording.wav')
                    wav_path.write_bytes(inner.read(wav_name))
                    try:
                        with contextlib.closing(wave.open(str(wav_path), 'rb')) as w:
                            wav_meta[zname] = {
                                'pcg_sampling_rate_Hz': w.getframerate(),
                                'pcg_channels': w.getnchannels(),
                                'pcg_sample_width_bytes': w.getsampwidth(),
                                'pcg_duration_s': w.getnframes()/w.getframerate(),
                                'pcg_file_size_bytes': wav_path.stat().st_size,
                            }
                    except Exception:
                        pass
                    finally:
                        try:
                            wav_path.unlink()
                        except Exception:
                            pass

                if zname in cached_ecg:
                    row = cached_ecg[zname]
                    ecg_meta[zname] = {
                        'ecg_report_hr_bpm': row.get('ecg_report_hr_bpm', np.nan),
                        'ecg_report_check_time': row.get('ecg_report_check_time', ''),
                        'ecg_signal_reanalysable': False,
                    }
                    continue

                if parse_ecg_pdfs and pdftotext_path:
                    pdf_name = next((n for n in names if n.endswith('ekg.pdf')), None)
                    if pdf_name:
                        hr = np.nan
                        check = ''
                        pdf_path = tmpdir / (Path(zname).stem + '_ekg.pdf')
                        pdf_path.write_bytes(inner.read(pdf_name))
                        try:
                            txt = subprocess.run(
                                [pdftotext_path, '-layout', str(pdf_path), '-'],
                                capture_output=True, text=True, timeout=1
                            ).stdout
                            m = re.search(r'HR\s*[:：]?\s*(\d+)', txt)
                            if m:
                                hr = float(m.group(1))
                            cm = re.search(r'Check Time\s*:?\s*([0-9\-: ]+)', txt)
                            if cm:
                                check = cm.group(1).strip()
                        except Exception:
                            pass
                        finally:
                            try:
                                pdf_path.unlink()
                            except Exception:
                                pass
                        ecg_meta[zname] = {
                            'ecg_report_hr_bpm': hr,
                            'ecg_report_check_time': check,
                            'ecg_signal_reanalysable': False,
                        }

    for col in ['pcg_sampling_rate_Hz','pcg_channels','pcg_sample_width_bytes','pcg_duration_s','pcg_file_size_bytes','ecg_report_hr_bpm','ecg_report_check_time','ecg_signal_reanalysable']:
        if col not in df.columns:
            df[col] = '' if col == 'ecg_report_check_time' else (False if col=='ecg_signal_reanalysable' else np.nan)
    for idx, row in df.iterrows():
        zname = row['raw_session_zip']
        for k, v in wav_meta.get(zname, {}).items():
            df.at[idx, k] = v
        for k, v in ecg_meta.get(zname, {}).items():
            df.at[idx, k] = v
    return df


def descriptive(df, outdir):
    rows=[]
    for c in df.columns:
        s = pd.to_numeric(df[c], errors='coerce').dropna().astype(float)
        if len(s) >= 1:
            rows.append({'variable':c,'n':len(s),'missing_n':int(df[c].isna().sum()),'missing_pct':100*df[c].isna().mean(),'mean':s.mean(),'sd':s.std(ddof=1) if len(s)>1 else np.nan,'median':s.median(),'iqr':s.quantile(.75)-s.quantile(.25),'min':s.min(),'max':s.max()})
    pd.DataFrame(rows).to_csv(outdir/'descriptive_statistics.csv', index=False)


def correlations(df, outdir):
    candidates = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    rows=[]
    for i,a in enumerate(candidates):
        for b in candidates[i+1:]:
            sub=df[[a,b]].dropna()
            if len(sub)>=8 and sub[a].nunique()>1 and sub[b].nunique()>1:
                pr=stats.pearsonr(sub[a],sub[b]); sr=stats.spearmanr(sub[a],sub[b])
                rows.append({'a':a,'b':b,'n':len(sub),'pearson_r':pr.statistic,'pearson_p':pr.pvalue,'spearman_rho':sr.statistic,'spearman_p':sr.pvalue})
    corr=pd.DataFrame(rows)
    if len(corr):
        corr['pearson_q_bh']=bh(corr['pearson_p']); corr['spearman_q_bh']=bh(corr['spearman_p'])
    corr.to_csv(outdir/'exploratory_correlations.csv', index=False)
    return corr


def device_agreement(df, outdir):
    pairs=[
        ('omron_sbp_mmHg','samsung_sbp_mmHg','SBP'),
        ('omron_dbp_mmHg','samsung_dbp_mmHg','DBP'),
        ('omron_hr_bpm','samsung_hr_bpm','HR'),
        ('omron_hr_bpm','ecg_report_hr_bpm','HR'),
        ('ppg_pulse_bpm','ecg_report_hr_bpm','Pulse/HR'),
        ('ppg_spo2_pct','samsung_spo2_pct','SpO2')
    ]
    rows=[]
    for ref,comp,var in pairs:
        if ref not in df or comp not in df:
            continue
        d=df[[ref,comp]].dropna().astype(float)
        if d.empty:
            continue
        diff=d[ref]-d[comp]
        sd=diff.std(ddof=1) if len(diff)>1 else np.nan
        rows.append({
            'comparison':f'{ref} vs {comp}',
            'variable':var,
            'n':len(d),
            'bias_ref_minus_comp':diff.mean(),
            'sd_difference':sd,
            'loa_lower':diff.mean()-1.96*sd if not pd.isna(sd) else np.nan,
            'loa_upper':diff.mean()+1.96*sd if not pd.isna(sd) else np.nan,
            'mae':diff.abs().mean(),
            'count_abs_diff_gt_5':int((diff.abs()>5).sum()) if var != 'SpO2' else np.nan,
            'count_abs_diff_gt_2':int((diff.abs()>2).sum()) if var == 'SpO2' else np.nan,
        })
    out=pd.DataFrame(rows)
    out.to_csv(outdir/'device_agreement_summary.csv', index=False)
    if len(out):
        # Long-form paired data for reviewers.
        paired=[]
        for ref, comp, var in pairs:
            if ref in df and comp in df:
                for _, row in df[['session_id','timestamp_local_iso',ref,comp]].dropna().iterrows():
                    refv=float(row[ref]); compv=float(row[comp])
                    paired.append({
                        'session_id': row['session_id'],
                        'timestamp_local_iso': row['timestamp_local_iso'],
                        'variable': var,
                        'reference_device_variable': ref,
                        'comparison_device_variable': comp,
                        'reference_value': refv,
                        'comparison_value': compv,
                        'difference_ref_minus_comp': refv-compv,
                        'mean_of_methods': (refv+compv)/2
                    })
        pd.DataFrame(paired).to_csv(outdir/'clean_device_agreement.csv', index=False)
    return out


def figures(df, outdir):
    figdir=outdir/'figures'; figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'figure.dpi':150, 'savefig.dpi':300, 'font.size':8})

    # 1. Timeline
    fig, ax=plt.subplots(figsize=(8,3.5))
    ax.scatter(pd.to_datetime(df['datetime']), df['hour_decimal_local'])
    ax.set_title('Timeline of 52 multimodal measurement sessions')
    ax.set_ylabel('Hour of day')
    ax.set_xlabel('Measurement timestamp')
    ax.grid(True, alpha=.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figdir/'figure_1_measurement_timeline.png')
    plt.close(fig)

    # 2. Missingness heatmap
    selected=[c for c in [
        'omron_sbp_mmHg','omron_dbp_mmHg','omron_hr_bpm','ppg_spo2_pct','ppg_pulse_bpm',
        'samsung_sbp_mmHg','samsung_dbp_mmHg','samsung_hr_bpm','samsung_spo2_pct',
        'env_temperature_C','env_humidity_pct','env_pressure_hPa','pm1','pm2_5','pm10',
        'sleep_score','steps_daily','pcg_duration_s','ecg_report_hr_bpm'
    ] if c in df.columns]
    miss=df[selected].isna().astype(int).T
    fig, ax=plt.subplots(figsize=(8,4))
    im=ax.imshow(miss, aspect='auto')
    ax.set_yticks(range(len(selected))); ax.set_yticklabels(selected)
    ax.set_xlabel('Session index')
    ax.set_title('Missingness map (1 = missing, 0 = observed)')
    fig.colorbar(im, ax=ax, fraction=.025, pad=.02)
    fig.tight_layout()
    fig.savefig(figdir/'figure_2_missingness_heatmap.png')
    plt.close(fig)

    # Bland-Altman plots
    def bland_altman(ref, comp, fname, title):
        if ref not in df or comp not in df:
            return
        d=df[[ref,comp]].dropna().astype(float)
        if len(d)<2:
            return
        mean=(d[ref]+d[comp])/2
        diff=d[ref]-d[comp]
        bias=diff.mean(); sd=diff.std(ddof=1)
        fig, ax=plt.subplots(figsize=(5.5,4))
        ax.scatter(mean,diff)
        ax.axhline(bias, linestyle='--')
        ax.axhline(bias+1.96*sd, linestyle=':')
        ax.axhline(bias-1.96*sd, linestyle=':')
        ax.set_xlabel('Mean of methods')
        ax.set_ylabel('Reference - comparator')
        ax.set_title(title)
        ax.grid(True, alpha=.3)
        fig.tight_layout()
        fig.savefig(figdir/fname)
        plt.close(fig)
    bland_altman('omron_sbp_mmHg','samsung_sbp_mmHg','figure_3_bland_altman_sbp.png','Bland-Altman: Omron vs Samsung SBP')
    bland_altman('omron_dbp_mmHg','samsung_dbp_mmHg','figure_4_bland_altman_dbp.png','Bland-Altman: Omron vs Samsung DBP')

    # Exploratory association plots
    for x,y,name,title in [
        ('env_pressure_hPa','omron_dbp_mmHg','figure_5_dbp_pressure.png','DBP and atmospheric pressure'),
        ('env_temperature_C','omron_dbp_mmHg','figure_6_dbp_temperature.png','DBP and ambient temperature'),
        ('samsung_stress_ordinal','omron_hr_bpm','figure_7_stress_hr.png','Heart rate and stress category')
    ]:
        if x in df and y in df:
            sub=df[[x,y]].dropna().astype(float)
            if len(sub)<2:
                continue
            fig, ax=plt.subplots(figsize=(5,4))
            ax.scatter(sub[x], sub[y])
            if len(sub)>2 and sub[x].nunique()>1:
                z=np.polyfit(sub[x],sub[y],1)
                xs=np.linspace(sub[x].min(), sub[x].max(),100)
                ax.plot(xs,z[0]*xs+z[1], linestyle='--')
            ax.set_xlabel(x); ax.set_ylabel(y); ax.set_title(title)
            ax.grid(True, alpha=.3)
            fig.tight_layout()
            fig.savefig(figdir/name)
            plt.close(fig)

    # Spearman correlation matrix
    corr_vars=[c for c in [
        'omron_sbp_mmHg','omron_dbp_mmHg','omron_hr_bpm','env_temperature_C','env_humidity_pct',
        'env_pressure_hPa','body_temperature_C','ppg_spo2_pct','ppg_pulse_bpm','pm2_5',
        'sleep_score','steps_daily','samsung_stress_ordinal'
    ] if c in df.columns]
    cdf=df[corr_vars].apply(pd.to_numeric, errors='coerce')
    corr=cdf.corr(method='spearman')
    fig, ax=plt.subplots(figsize=(7,6))
    im=ax.imshow(corr, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_vars))); ax.set_xticklabels(corr_vars, rotation=90)
    ax.set_yticks(range(len(corr_vars))); ax.set_yticklabels(corr_vars)
    ax.set_title('Spearman correlation matrix')
    fig.colorbar(im, ax=ax, fraction=.046, pad=.04)
    fig.tight_layout()
    fig.savefig(figdir/'figure_9_spearman_correlation_matrix.png')
    plt.close(fig)

    # Simple network-ready visualisation without networkx
    edges=[]
    for i,a in enumerate(corr_vars):
        for j,b in enumerate(corr_vars):
            if j<=i:
                continue
            r=corr.loc[a,b]
            if pd.notna(r) and abs(r)>=0.5:
                edges.append((a,b,float(r)))
    if edges:
        import math
        nodes=sorted(set([e[0] for e in edges]+[e[1] for e in edges]))
        angles={node:2*math.pi*k/len(nodes) for k,node in enumerate(nodes)}
        pos={node:(math.cos(angles[node]), math.sin(angles[node])) for node in nodes}
        fig, ax=plt.subplots(figsize=(7,7))
        for a,b,r in edges:
            x=[pos[a][0],pos[b][0]]; y=[pos[a][1],pos[b][1]]
            ax.plot(x,y, linewidth=1+2*abs(r), alpha=.55)
        for node,(x,y) in pos.items():
            ax.scatter([x],[y], s=150)
            ax.text(x*1.12,y*1.12,node,ha='center',va='center',fontsize=7)
        ax.set_title('Exploratory association network |rho| >= 0.5')
        ax.axis('off')
        fig.tight_layout()
        fig.savefig(figdir/'figure_8_exploratory_network.png')
        plt.close(fig)

def make_long_table(df, outdir):
    id_cols=[c for c in ['session_id','timestamp_local_iso','date_local','day_index','hour_decimal_local','raw_session_zip'] if c in df.columns]
    value_cols=[c for c in df.columns if c not in id_cols and c not in ['datetime']]
    long=df.melt(id_vars=id_cols, value_vars=value_cols, var_name='variable_name', value_name='value')
    long.to_csv(outdir/'clean_measurements_long.csv', index=False)


def make_qc_flags(df, outdir):
    ranges={
        'omron_sbp_mmHg':(80,220),'omron_dbp_mmHg':(40,140),'omron_hr_bpm':(40,180),
        'ppg_spo2_pct':(70,100),'ppg_pulse_bpm':(40,180),'body_temperature_C':(34,42),
        'env_temperature_C':(-20,50),'env_humidity_pct':(0,100),'env_pressure_hPa':(950,1050),
        'pm1':(0,500),'pm2_5':(0,500),'pm10':(0,500)
    }
    out=pd.DataFrame({'session_id':df['session_id']})
    for c,(lo,hi) in ranges.items():
        if c in df:
            vals=pd.to_numeric(df[c], errors='coerce')
            out[f'qc_{c}_range_flag']=vals.notna() & ((vals<lo)|(vals>hi))
    for c in ['omron_sbp_mmHg','omron_dbp_mmHg','omron_hr_bpm','env_temperature_C','env_humidity_pct','env_pressure_hPa','ppg_spo2_pct','ppg_pulse_bpm','pcg_duration_s','ecg_report_hr_bpm']:
        if c in df:
            out[f'missing_{c}']=df[c].isna()
    flag_cols=[c for c in out.columns if c.startswith('qc_') or c.startswith('missing_')]
    out['qc_flag_any']=out[flag_cols].any(axis=1) if flag_cols else False
    out.to_csv(outdir/'qc_flags.csv', index=False)


def write_modality_tables(df, outdir):
    pcg_cols=[c for c in ['session_id','timestamp_local_iso','raw_session_zip','pcg_sampling_rate_Hz','pcg_channels','pcg_sample_width_bytes','pcg_duration_s','pcg_file_size_bytes'] if c in df.columns]
    if pcg_cols:
        pcg=df[pcg_cols].copy()
        pcg['pcg_quality_score']='metadata_pass'
        pcg['first_10s_noise_flag']='possible; source description states up to 10 seconds of ambient noise may be present'
        pcg['usable_for_diagnostic_auscultation']='not assessed'
        pcg.to_csv(outdir/'pcg_audio_features.csv', index=False)
    ecg_cols=[c for c in ['session_id','timestamp_local_iso','raw_session_zip','ecg_report_hr_bpm','ecg_report_check_time','ecg_signal_reanalysable'] if c in df.columns]
    if ecg_cols:
        ecg=df[ecg_cols].copy()
        ecg['ecg_report_label_primary']='device-generated PDF report; rhythm label not machine-reanalysed in V2 pipeline'
        ecg['notes']='Waveform-level ECG reanalysis is not supported unless raw numerical ECG signal is added.'
        ecg.to_csv(outdir/'ecg_pdf_labels.csv', index=False)


def write_key_associations(corr, outdir):
    key_pairs=[
        ('omron_dbp_mmHg','env_temperature_C'),
        ('omron_dbp_mmHg','env_pressure_hPa'),
        ('omron_hr_bpm','steps_daily'),
        ('omron_hr_bpm','samsung_stress_ordinal'),
        ('omron_sbp_mmHg','steps_daily'),
        ('omron_dbp_mmHg','steps_daily'),
        ('pm2_5','omron_sbp_mmHg'),
        ('pm2_5','omron_hr_bpm'),
    ]
    rows=[]
    if corr is not None and len(corr):
        for a,b in key_pairs:
            hit=corr[((corr['a']==a)&(corr['b']==b))|((corr['a']==b)&(corr['b']==a))]
            if len(hit):
                rows.append(hit.iloc[0].to_dict())
    pd.DataFrame(rows).to_csv(outdir/'key_exploratory_associations.csv', index=False)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-zip', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--parse-ecg-pdfs', action='store_true', help='Force raw PDF text extraction instead of using cached ECG report metadata when available.')
    args=ap.parse_args()
    out=Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    df=parse_centralised(Path(args.input_zip), out)
    tmp_extract = out / '_tmp_extracted_raw'
    if tmp_extract.exists():
        shutil.rmtree(tmp_extract)
    tmp_extract.mkdir(parents=True, exist_ok=True)
    try:
        df=add_nested_metadata(Path(args.input_zip), df, tmp_extract, parse_ecg_pdfs=args.parse_ecg_pdfs)
    finally:
        shutil.rmtree(tmp_extract, ignore_errors=True)
    df.to_csv(out/'clean_measurements_wide.csv', index=False)
    make_long_table(df, out)
    make_qc_flags(df, out)
    write_modality_tables(df, out)
    descriptive(df, out)
    corr=correlations(df, out)
    write_key_associations(corr, out)
    device_agreement(df, out)
    figures(df, out)
    print(f'Pipeline completed. Outputs written to {out}')

if __name__ == '__main__':
    main()
