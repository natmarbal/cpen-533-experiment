import os
import sys
import yaml

nginx_options = ['round_robin', 'weighted_round_robin', 'least_conn'] # load balancing policies
delays = ['100us', '1ms', '10ms', '100ms', '1s'] # Injected network delays

concurrency = 6 # number of concurrent workers (client)
trials = 30 # Number of times to repeat each config run
warmup_duration = 30 # in seconds
fault_duration = 60 # in seconds
recovery_duration = 30 # in seconds

output_dir = "yaml_configs"
os.makedirs(output_dir, exist_ok=True)

def generate_configs():
    for n_policy in nginx_options:
        for d in delays:
            config = {
                "experiment_name": f"{n_policy}_delay{d}",
                "concurrency": concurrency,
                "nginx_policy": n_policy,
                "fault_injection_delay": d,
                "trials": trials,
                "warmup_duration_sec": warmup_duration,
                "fault_duration_sec": fault_duration,
                "recovery_duration_sec": recovery_duration,
                "total_duration_sec": warmup_duration + fault_duration + recovery_duration,
            }
            
            filename = f"{output_dir}/{config['experiment_name']}.yaml"
            with open(filename, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
                        
    print(f"Generated all configurations in ./{output_dir}/")

if __name__ == "__main__":
    generate_configs()