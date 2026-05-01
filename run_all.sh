#!/bin/bash

CONFIG_DIR="./yaml_configs"

if [ ! -d "$CONFIG_DIR" ]; then
    echo "Error: Directory $CONFIG_DIR not found."
    exit 1
fi

echo "Ensuring cluster is down before starting..."
make cluster-down
make clear-faults

for FILE in "$CONFIG_DIR"/*.yaml; do
    FILENAME=$(basename "$FILE")
    
    echo "------------------------------------------------"
    echo "Running config for: $FILENAME"
    
    make run-config CONFIG="yaml_configs/$FILENAME"
done

echo "------------------------------------------------"
echo "All configurations processed. Shutting down cluster..."
make cluster-down
echo "Done."