#!/bin/bash
# Simple script to run the Python benchmark loader and save output to a file
# that Electron can read

# Capture the full path to the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Run the Python script and save output to a file
python "$DIR/list_benchmarks.py" > "$DIR/benchmark_data.json"

# Add timestamp to track when this was last run
echo "Last updated: $(date)" > "$DIR/benchmark_data.timestamp"

# Echo success message
echo "Benchmark data saved to benchmark_data.json"
