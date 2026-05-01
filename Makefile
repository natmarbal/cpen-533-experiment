.PHONY: all build-server build-client build-all run-server run-client docker-up cluster-up cluster-down run-trial run-config gen-configs

# Build both containers by default
all: build-all

# Generate configuration files
configs:
	python3 generate_configs.py

# Build all containers
build-all:
	docker-compose build

# Run the experiment using a specific YAML configuration for multiple trials
# Usage: make run-config CONFIG=yaml_configs/round_robin_delay10ms.yaml
run-config:
	@if [ -z "$(CONFIG)" ]; then echo "Please specify CONFIG=yaml_configs/your_config.yaml"; exit 1; fi
	@TRIALS=$$(python3 -c "import yaml; print(yaml.safe_load(open('$(CONFIG)'))['trials'])"); \
	echo "Ensuring cluster is up for $(CONFIG)..."; \
	$(MAKE) cluster-up CONFIG_FILE=$(CONFIG); \
	echo "Running $$TRIALS trials..."; \
	for i in $$(seq 1 $$TRIALS); do \
		echo "--------------------------------------------------"; \
		echo "Trial $$i/$$TRIALS starting..."; \
		$(MAKE) run-trial CONFIG_FILE=$(CONFIG) TRIAL_NUM=$$i; \
		echo "Trial $$i/$$TRIALS completed."; \
	done

# Clear any injected faults from all server containers
clear-faults:
	@echo "Clearing any existing faults..."
	@for cid in $$(docker-compose ps -q server_w1 server_w2 server_w3); do \
		docker exec $$cid tc qdisc del dev eth0 root 2>/dev/null || true; \
	done

# Start the NGINX and Server infrastructure
cluster-up:
	@POLICY=$$(python3 -c "import yaml; print(yaml.safe_load(open('$(CONFIG_FILE)'))['nginx_policy'])"); \
	NGINX_CONF=nginx_configs/$$POLICY.conf \
	docker-compose up -d --scale server_w1=2 --scale server_w2=2 --scale server_w3=2 nginx server_w1 server_w2 server_w3

# Stop the entire cluster
cluster-down:
	docker-compose down

# Run a single trial: inject fault and run client
run-trial:
	./inject_fault.sh $(CONFIG_FILE) & \
	CONFIG_FILE=$(CONFIG_FILE) TRIAL_NUM=$(TRIAL_NUM) \
	docker-compose run -T --no-deps --rm client

round_robin least_conn weighted_round_robin:
	$(MAKE) cluster-up CONFIG_FILE=yaml_configs/$@_delay10ms.yaml
