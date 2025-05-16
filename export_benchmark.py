#!/usr/bin/env python3
"""
Bridge script to export benchmark results to CSV format.
Takes a benchmark ID as argument and exports the data using the exporter module.
"""

import os
import sys
import io
import json
import argparse
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout

# Set up logging
LOG_FILE = "/Users/maxcembalest/Desktop/repos/eyeonthebenchmarks/export_benchmark.log"

def log_to_file(message):
    """Write debug message to log file"""
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

# Clear log file on start
with open(LOG_FILE, 'w') as f:
    f.write(f"{datetime.now()}: Starting benchmark export\n")
    
# Import the exporter module from the engine directory but redirect stdout first
# This is needed because the imported modules print debug information to stdout
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))

# Redirect stdout temporarily to capture any debug output from imports
f = io.StringIO()
with redirect_stdout(f):
    from exporter import export_benchmark_to_csv

# Log the captured output
debug_output = f.getvalue()
if debug_output:
    log_to_file(f"Debug output from imports: {debug_output}")

def export_benchmark(benchmark_id):
    """Export a benchmark to CSV format"""
    log_to_file(f"Exporting benchmark ID: {benchmark_id}")
    
    try:
        # Create exports directory in the project root if it doesn't exist
        exports_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "exports"
        os.makedirs(exports_dir, exist_ok=True)
        
        log_to_file(f"Exporting to directory: {exports_dir}")
        
        # Call the export function but capture any debug output to prevent it from mixing with our JSON output
        f = io.StringIO()
        with redirect_stdout(f):
            csv_path = export_benchmark_to_csv(benchmark_id, exports_dir)
        
        # Log any captured output
        debug_output = f.getvalue()
        if debug_output:
            log_to_file(f"Debug output from export function: {debug_output}")
        
        log_to_file(f"CSV file created: {csv_path}")
        
        return {
            "success": True,
            "filepath": csv_path,
            "message": f"Benchmark exported successfully to {csv_path}"
        }
        
    except Exception as e:
        error_msg = f"Error exporting benchmark: {str(e)}"
        log_to_file(error_msg)
        print(error_msg, file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export benchmark results to CSV")
    parser.add_argument('benchmark_id', type=int, help="ID of the benchmark to export")
    
    args = parser.parse_args()
    
    log_to_file(f"Command line argument: benchmark_id={args.benchmark_id}")
    
    result = export_benchmark(args.benchmark_id)
    log_to_file(f"Export completed with result: {json.dumps(result)}")
    print(json.dumps(result))
