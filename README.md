## CPEN 533 Project Code

### Core Components
- client: Closed-loop client with 6 workers that generates requests logs throughput and latency metrics.
- server: Backend server that implements a Python version of the [vSwarm spinning benchmark](https://github.com/vhive-serverless/vSwarm/tree/main/benchmarks/spinning).
- NGINX configs: Least connections, round robin and weighted round robin (with 1/3 of servers each assigned to weights 1, 2 and 3).
- docker-compose: Used to set-up the NGINX load balancer, 6 backend servers, and the client.

### Relevant Scripts
- `generate_configs.py`: Auto-populates the `yaml_configs` directory with YAML config files for different experiment scenarios (e.g. different load balancing policies and network delays for different experiment runs).
- `run_all.sh`: Iterates through all generated configs and executes the full experimental suite.
- `inject_fault.sh`: Implements the injection of network delay (using `tc`) into a backend server container (based on [`blockade`](https://github.com/worstcase/blockade)).
- `plot.py`: Processes the raw CSV data collected in the `data/` directory to generate plots (saved as `*.png` files) showing performance degradation, tail latency, and throughput from experiment outputs.

### Prerequisites
This set-up was run and tested on a laptop with 8 cores and 16GiB of RAM, and the following software versions:
- OS: Fedora Linux 44 (beta release)
- Docker: version 29.4.1, build 1.fc44
- Docker Compose: version 5.1.2
- Python: version 3.14.4
- Install Python dependencies for running scripts via
  ```bash
  pip install -r requirements.txt
  ```

### How to Run Experiments

##### 1. Build the Infrastructure
Build the Docker images for the client and backend servers:
```bash
make build-all
```

##### 2. Generate Experiment Configurations
Modify the global variables at the top of `generate_configs.py` (if necessary to adjust number of trials, etc.) and run
```bash
make configs
```

##### 3. Run the Experiments

To run the entire suite of experiments defined in `yaml_configs/`:
```bash
./run_all.sh
```

To run a single experiment (e.g., Round Robin with 10ms delay):
```bash
make run-config CONFIG=yaml_configs/round_robin_delay10ms.yaml
```

##### 4. Plot Results
Once the experiments are complete and data is populated in the `data/` directory, generate the plots:
```bash
python plot.py
```

This will produce several PNG files in the root directory:
- `{policy}_performance_degradation.png`: Bar charts showing throughput loss.
- `{policy}_latency_analysis.png`: Tail latency (p90-p999) and percentage increases.
- `{policy}_throughput_timeline.png`: Throughput over time with highlighted fault regions.
- `{policy}_latency_timeline.png`: p95 latency over time with highlighted fault regions.
