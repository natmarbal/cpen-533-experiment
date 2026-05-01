import os
import glob
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats as st
import yaml

# Configure if needed
DATA_DIR = 'data/'

def get_experiment_durations(policy, delay):
    """Retrieves durations from YAML or uses default values."""
    yaml_path = f"yaml_configs/{policy}_delay{delay}.yaml"
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
                return config.get('warmup_duration_sec', 30), config.get('fault_duration_sec', 60)
            except Exception:
                pass
    return 30, 60

def parse_delay_to_float(d):
    """Converts a delay string (0s, 100us, 50ms) to a float value for sorting."""
    d = str(d).lower()
    if d in ['0s', '0ms', '0us', '0']: return 0.0
    if d.endswith('us'): return float(d[:-2]) * 1e-6
    if d.endswith('ms'): return float(d[:-2]) * 1e-3
    if d.endswith('s'):  return float(d[:-1])
    try: return float(d)
    except: return 0.0

def get_delay_order(delays):
    """Returns unique delay strings sorted by their numerical value."""
    return sorted(list(set(delays)), key=parse_delay_to_float)

def get_95_ci(data):
    """Calculates 95% Confidence Interval."""
    if len(data) < 2: return 0.0
    return st.sem(data) * st.t.ppf((1 + 0.95) / 2., len(data) - 1)

def parse_data(policy_prefix):
    """Parses throughput and latency CSVs."""
    tput_records, lat_records = [], []
    pattern = re.compile(rf'{DATA_DIR.rstrip("/")}/([^/]+)/trial_(\d+)_(\w+)\.csv')
    
    for filepath in glob.glob(os.path.join(DATA_DIR, '**', '*.csv'), recursive=True):
        match = pattern.search(filepath)
        if not match: continue
        exp_name, trial, ftype = match.groups()
        if not exp_name.startswith(policy_prefix): continue
        
        delay_match = re.search(r'delay(.+)$', exp_name)
        if not delay_match: continue
        
        delay, trial = delay_match.group(1), int(trial)
        try:
            df = pd.read_csv(filepath)
            df['delay'], df['trial'] = delay, trial
            if ftype == 'tput': tput_records.append(df)
            elif ftype == 'lat': lat_records.append(df)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            
    return (pd.concat(tput_records, ignore_index=True) if tput_records else pd.DataFrame(),
            pd.concat(lat_records, ignore_index=True) if lat_records else pd.DataFrame())

def plot_degradation(tput_df, policy):
    """Calculates degradation by comparing fault vs warmup interval values."""
    trial_results = []
    for (delay, trial), g in tput_df.groupby(['delay', 'trial']):
        w, f = get_experiment_durations(policy, delay)
        warm = g[(g['second'] > 0) & (g['second'] <= w)]['requests_completed'].mean()
        slow = g[(g['second'] > w) & (g['second'] <= w + f)]['requests_completed'].mean()
        if pd.notnull(warm) and warm > 0:
            deg = ((warm - slow) / warm * 100.0)
            trial_results.append({'delay': delay, 'trial': trial, 'deg': deg})
    
    df = pd.DataFrame(trial_results)
    if '0s' not in df['delay'].values:
        df = pd.concat([df, pd.DataFrame([{'delay': '0s', 'trial': 0, 'deg': 0.0}])], ignore_index=True)
        
    order = get_delay_order(df['delay'])
    s = df.groupby('delay')['deg'].agg(['mean', get_95_ci]).reindex(order).dropna()
    
    plt.figure(figsize=(10, 6))
    plt.bar(s.index, s['mean'], yerr=s['get_95_ci'], capsize=5, color='lightskyblue', edgecolor='black', alpha=0.8)
    plt.ylabel('Performance Degradation (%)', fontweight='bold')
    plt.title(f'Performance Degradation: {policy.replace("_", " ").title()}', fontsize=14, fontweight='bold')
    plt.ylim(bottom=0)
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(f'{policy}_performance_degradation.png')
    plt.close()

def plot_latency(lat_df, tput_df, policy):
    """Calculates latency increase using warmup baseline."""
    abs_res, rel_res, warmup_stats = [], [], []
    pcts, lbls = [0.90, 0.95, 0.99, 0.999], ['p90', 'p95', 'p99', 'p999']
    
    for (delay, trial), g in lat_df.groupby(['delay', 'trial']):
        tp = tput_df[(tput_df['delay'] == delay) & (tput_df['trial'] == trial)]
        if tp.empty: continue
        
        t0 = (tp['timestamp'] - tp['second']).mean()
        w, f = get_experiment_durations(policy, delay)
        
        warm_lat = g[(g['timestamp'] > t0) & (g['timestamp'] <= t0+w)]['latency_us'] / 1e6
        fault_lat = g[(g['timestamp'] > t0+w) & (g['timestamp'] <= t0+w+f)]['latency_us'] / 1e6
        
        if not fault_lat.empty and not warm_lat.empty:
            a, r = {'delay': delay, 'trial': trial}, {'delay': delay, 'trial': trial}
            warm_quantiles = {l: warm_lat.quantile(p) for p, l in zip(pcts, lbls)}
            warmup_stats.append(warm_quantiles)
            
            for p, l in zip(pcts, lbls):
                v_f = fault_lat.quantile(p)
                v_w = warm_lat.quantile(p)
                a[l] = v_f
                r[l] = ((v_f - v_w) / v_w * 100.0) if v_w > 0 else 0.0
            abs_res.append(a), rel_res.append(r)
            
    df_a, df_r = pd.DataFrame(abs_res), pd.DataFrame(rel_res)
    
    if not df_a.empty and '0s' not in df_a['delay'].values and warmup_stats:
        baseline_abs = pd.DataFrame(warmup_stats).mean().to_dict()
        a0 = {**{'delay': '0s', 'trial': 0}, **baseline_abs}
        r0 = {**{'delay': '0s', 'trial': 0}, **{l: 0.0 for l in lbls}}
        df_a = pd.concat([df_a, pd.DataFrame([a0])], ignore_index=True)
        df_r = pd.concat([df_r, pd.DataFrame([r0])], ignore_index=True)

    order = get_delay_order(df_a['delay'])
    m_a, e_a = df_a.groupby('delay')[lbls].mean().reindex(order), df_a.groupby('delay')[lbls].agg(get_95_ci).reindex(order)
    m_r, e_r = df_r.groupby('delay')[lbls].mean().reindex(order), df_r.groupby('delay')[lbls].agg(get_95_ci).reindex(order)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    x, width = np.arange(len(m_a.index)), 0.18
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'] # p90, p95, p99, p999
    
    for i, l in enumerate(lbls):
        off = (i - 1.5) * width
        ax1.bar(x + off, m_a[l], width, yerr=e_a[l], capsize=3, label=l, edgecolor='black', alpha=0.8, color=colors[i])
        ax2.bar(x + off, m_r[l], width, yerr=e_r[l], capsize=3, label=l, edgecolor='black', alpha=0.8, color=colors[i])
    
    ax1.set_ylabel('Latency (s)', fontweight='bold')
    ax1.set_title(f'Tail Latency: {policy.replace("_", " ").title()}', fontsize=14, fontweight='bold')
    ax1.legend(title='Percentile', frameon=True, shadow=True)
    ax1.grid(axis='y', linestyle=':', alpha=0.6)
    
    ax2.set_ylabel('% Increase', fontweight='bold')
    ax2.set_title('Tail Latency Increase (%)', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(m_a.index, fontweight='bold')
    ax2.grid(axis='y', linestyle=':', alpha=0.6)
    plt.tight_layout(), plt.savefig(f'{policy}_latency_analysis.png'), plt.close()

def plot_timeline(tput_df, policy):
    """Plots throughput over time with fault region highlighted."""
    ts = tput_df.groupby(['delay', 'second'])['requests_completed'].mean().unstack(level=0)
    order = [d for d in get_delay_order(ts.columns) if d in ts.columns]
    
    plt.figure(figsize=(12, 6))
    
    for d in order:
        plt.plot(ts.index, ts[d], label=f'Delay {d}', linewidth=2, alpha=0.8)
    
    if order:
        w, f = get_experiment_durations(policy, order[0])
        plt.axvspan(w, w+f, color='salmon', alpha=0.15, label='Fault Active')
        plt.axvline(w, color='darkred', linestyle='--', linewidth=1.5, alpha=0.6)
        plt.axvline(w+f, color='darkred', linestyle='--', linewidth=1.5, alpha=0.6)
        
        y_limit = plt.gca().get_ylim()
        y_pos = y_limit[1] - (y_limit[1] - y_limit[0]) * 0.05
        plt.text(w + f/2, y_pos, 'FAULT DURATION', color='darkred', 
                 fontweight='bold', ha='center', va='top', 
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.2'))

    plt.ylabel('Throughput (req/s)', fontweight='bold')
    plt.xlabel('Time (s)', fontweight='bold')
    plt.title(f'Average Throughput vs Time: {policy.replace("_", " ").title()}', fontsize=14, fontweight='bold')
    plt.legend(loc='upper right', frameon=True, shadow=True)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(f'{policy}_throughput_timeline.png')
    plt.close()

def plot_latency_timeline(lat_df, tput_df, policy):
    """Plots latency over time with fault region highlighted."""
    lat_records = []
    for (delay, trial), g in lat_df.groupby(['delay', 'trial']):
        tp = tput_df[(tput_df['delay'] == delay) & (tput_df['trial'] == trial)]
        if tp.empty: continue
        t0 = (tp['timestamp'] - tp['second']).mean()
        g = g.copy()
        g['second'] = (g['timestamp'] - t0).astype(int)
        lat_records.append(g)
        
    if not lat_records: return
    
    df = pd.concat(lat_records, ignore_index=True)
    ts = df.groupby(['delay', 'second'])['latency_us'].quantile(0.95).unstack(level=0) / 1e6
    
    order = [d for d in get_delay_order(ts.columns) if d in ts.columns]
    plt.figure(figsize=(12, 6))
    
    for d in order:
        plt.plot(ts.index, ts[d], label=f'Delay {d} (p95)', linewidth=2, alpha=0.8)
        
    if order:
        w, f = get_experiment_durations(policy, order[0])
        plt.axvspan(w, w+f, color='salmon', alpha=0.15, label='Fault Active')
        plt.axvline(w, color='darkred', linestyle='--', linewidth=1.5, alpha=0.6)
        plt.axvline(w+f, color='darkred', linestyle='--', linewidth=1.5, alpha=0.6)
        
        y_limit = plt.gca().get_ylim()
        y_pos = y_limit[1] - (y_limit[1] - y_limit[0]) * 0.05
        plt.text(w + f/2, y_pos, 'FAULT DURATION', color='darkred', 
                 fontweight='bold', ha='center', va='top', 
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.2'))

    plt.ylabel('p95 Latency (s)', fontweight='bold')
    plt.xlabel('Time (s)', fontweight='bold')
    plt.title(f'p95 Latency vs Time: {policy.replace("_", " ").title()}', fontsize=14, fontweight='bold')
    plt.legend(loc='upper right', frameon=True, shadow=True)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(f'{policy}_latency_timeline.png')
    plt.close()

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR): exit(1)
    policies = set()
    for d in [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]:
        match = re.match(r'^(.+)_delay', d)
        policies.add(match.group(1) if match else d)
    
    for p in sorted(policies):
        tput_data, lat_data = parse_data(p)
        if tput_data.empty and lat_data.empty: continue
        if not tput_data.empty: 
            plot_degradation(tput_data, p)
            plot_timeline(tput_data, p)
        if not lat_data.empty and not tput_data.empty: 
            plot_latency(lat_data, tput_data, p)
            plot_latency_timeline(lat_data, tput_data, p)