import argparse
import json
import time
import urllib.request
import threading
import sys
import yaml
import os

completed = 0
experiment_running = True
latencies = []
throughput_slice = []

completed_lock = threading.Lock()
latencies_lock = threading.Lock()
throughput_lock = threading.Lock()

def invoke_serving_function(port, req_timeout):
    global completed
    hostname = "localhost"
    url = f"http://{hostname}:{port}"
    
    start_time = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=req_timeout) as response:
            body = response.read().decode('utf-8')
            resp_data = json.loads(body)
            
            now = time.time()
            latency_us = int((now - start_time) * 1e6)
            with latencies_lock:
                latencies.append((now, latency_us))
            
            with completed_lock:
                completed += 1
                
    except Exception as e:
        if "timed out" not in str(e).lower() and "time out" not in str(e).lower():
            print(f"Failed to invoke {url}: {e}")

def run_experiment(run_duration, target_concurrency, port, req_timeout, concurrency):
    global experiment_running, completed, latencies, throughput_slice
    
    start = time.time()
    end_time = start + run_duration
    
    if target_concurrency <= 0:
        print("Target concurrency must be > 0")
        sys.exit(1)
        
    experiment_running = True
    completed = 0
    with latencies_lock:
        latencies = []
    with throughput_lock:
        throughput_slice = []
    
    last_completed = 0

    def monitor_throughput():
        nonlocal last_completed
        while experiment_running:
            time.sleep(1.0)
            with completed_lock:
                current_completed = completed
            
            with throughput_lock:
                throughput_slice.append((time.time(), current_completed - last_completed))
            
            last_completed = current_completed

    throughput_thread = threading.Thread(target=monitor_throughput)
    throughput_thread.daemon = True
    throughput_thread.start()
    
    def worker():
        while time.time() < end_time and experiment_running:
            invoke_serving_function(port, req_timeout)
            
    print(f"Starting {concurrency} workers")
    worker_threads = []
    for _ in range(int(concurrency)):
        t = threading.Thread(target=worker)
        t.start()
        worker_threads.append(t)
        
    while time.time() < end_time:
        time.sleep(0.5)
            
    print(f"Cleaning up...")
    experiment_running = False
    
    for t in worker_threads:
        t.join()
        
    throughput_thread.join()
    
    duration = time.time() - start
    real_rps = completed / duration
    print(f"Completed requests: {completed}")
    print(f"Real Throughput (RPS): {real_rps:.2f}")
    return real_rps

def write_latencies(concurrency, filename, data_dir, trial):
    os.makedirs(data_dir, exist_ok=True)
    fname = os.path.join(data_dir, f"trial_{trial}_{filename}")
    print(f"The measured latencies are saved in {fname}")
    with open(fname, 'w') as f:
        f.write("timestamp,latency_us\n")
        for ts, lat in latencies:
            f.write(f"{ts},{lat}\n")

def write_throughput(concurrency, filename, data_dir, trial):
    os.makedirs(data_dir, exist_ok=True)
    fname = os.path.join(data_dir, f"trial_{trial}_{filename}")
    print(f"The measured throughput values are saved in {fname}")
    with open(fname, 'w') as f:
        f.write("timestamp,second,requests_completed\n")
        for i, (ts, val) in enumerate(throughput_slice):
            f.write(f"{ts},{i+1},{val}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--concurrency', type=float, default=1.0, help="Number of concurrent workers (closed-loop)")
    parser.add_argument('--time', type=int, default=100, help="Run the experiment for X seconds")
    parser.add_argument('--latf', type=str, default='lat.csv', help="CSV file for the latency measurements in microseconds")
    parser.add_argument('--tputf', type=str, default='tput.csv', help="CSV file for throughput over time (RPS)")
    parser.add_argument('--port', type=int, default=80, help="The port number to use")
    parser.add_argument('--config', type=str, help="Path to YAML configuration file")
    parser.add_argument('--trial', type=int, default=1, help="Trial number (for indexing output files)")
    args = parser.parse_args()
    
    if args.config:
        if os.path.isfile(args.config):
            print(f"Loading configuration from {args.config}")
            with open(args.config, 'r') as f:
                config = yaml.safe_load(f)
                if 'concurrency' in config:
                    args.concurrency = float(config['concurrency'])
                if 'total_duration_sec' in config:
                    args.time = int(config['total_duration_sec'])
                if 'experiment_name' in config:
                    experiment_name = config['experiment_name']
        else:
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)
    else:
        print("Error: No configuration file provided via --config.")
        sys.exit(1)
    
    data_dir = os.path.join("data", experiment_name)
    
    real_rps = run_experiment(args.time, args.concurrency, args.port, int(args.concurrency))
    
    write_latencies(args.concurrency, args.latf, data_dir, args.trial)
    write_throughput(args.concurrency, args.tputf, data_dir, args.trial)
