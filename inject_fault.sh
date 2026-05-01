#!/bin/bash

# This script manages a transient fault based on a YAML configuration file.
# Usage: ./inject_fault.sh <config_file>

CONFIG_FILE=$1

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Fault injector config file not found or not provided: '$CONFIG_FILE'"
    echo "Usage: ./inject_fault.sh <config_file>"
    exit 1
fi

WARMUP=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['warmup_duration_sec'])")
FAULT_DURATION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['fault_duration_sec'])")
DELAY=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['fault_injection_delay'])")

echo "Fault injector: Waiting $WARMUP seconds (warmup) before injecting delay..."
sleep "$WARMUP"

echo "Fault injector: Selecting a random server container..."
CONTAINER_ID=$(docker-compose ps -q server_w1 server_w2 server_w3 | shuf -n 1)

if [ -z "$CONTAINER_ID" ]; then
    echo "Fault injector: No server container found!"
    exit 1
fi

# Inject delay using traffic control (tc)
docker exec "$CONTAINER_ID" tc qdisc del dev eth0 root 2>/dev/null || true
docker exec "$CONTAINER_ID" tc qdisc add dev eth0 root netem delay "$DELAY"

if [ $? -eq 0 ]; then
    echo "Fault injector: $DELAY delay successfully injected into $CONTAINER_ID."
else
    echo "Fault injector: Failed to inject delay."
    exit 1
fi

echo "Fault injector: Waiting $FAULT_DURATION seconds (fault duration) before clearing fault..."
sleep "$FAULT_DURATION"

echo "Fault injector: Clearing fault from container $CONTAINER_ID..."
docker exec "$CONTAINER_ID" tc qdisc del dev eth0 root 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Fault injector: Delay cleared from $CONTAINER_ID."
else
    echo "Fault injector: Failed to clear delay (container may have exited)."
fi
