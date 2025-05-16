#!/usr/bin/env python3
"""
Bridge script to list benchmarks for the Electron UI.
Returns benchmark data in JSON format for the UI to render.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Debug to log file
LOG_FILE = "/Users/maxcembalest/Desktop/repos/eyeonthebenchmarks/list_benchmarks.log"

def log_to_file(message):
    """Write debug message to log file"""
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

# Clear log file on start
with open(LOG_FILE, 'w') as f:
    f.write(f"{datetime.now()}: Starting benchmark listing\n")

# Use absolute path to database file
DB_PATH = "/Users/maxcembalest/Desktop/repos/eyeonthebenchmarks/eotm_file_store.sqlite"
log_to_file(f"Using database path: {DB_PATH}")
print(f"Using database path: {DB_PATH}", file=sys.stderr)

def get_benchmarks():
    """Fetch benchmark data from the database"""
    log_to_file("Starting get_benchmarks function")
    
    if not os.path.exists(DB_PATH):
        log_to_file(f"Database file doesn't exist: {DB_PATH}")
        return []
    else:
        log_to_file(f"Database file found at: {DB_PATH}")
    
    try:
        log_to_file("Connecting to database...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        log_to_file("Database connection successful")
        
        # Query benchmarks table based on the exact database structure seen in database.sh
        cursor.execute("""
            SELECT 
                b.id, 
                b.timestamp, 
                b.label,
                b.description
            FROM 
                benchmarks b
            ORDER BY 
                b.timestamp DESC
        """)
        
        benchmark_rows = cursor.fetchall()
        benchmarks = []
        
        for benchmark_row in benchmark_rows:
            benchmark_id, timestamp, label, description = benchmark_row
            
            # Get file paths associated with this benchmark
            cursor.execute("""
                SELECT file_path 
                FROM benchmark_files 
                WHERE benchmark_id = ?
            """, (benchmark_id,))
            file_paths = [row[0] for row in cursor.fetchall()]
            files = [os.path.basename(path) for path in file_paths if path]
            
            # Get models used in this benchmark's runs
            cursor.execute("""
                SELECT DISTINCT model_name 
                FROM benchmark_runs 
                WHERE benchmark_id = ?
            """, (benchmark_id,))
            models = [row[0] for row in cursor.fetchall()]
            
            # Get token data from runs
            cursor.execute("""
                SELECT 
                    SUM(total_standard_input_tokens), 
                    SUM(total_cached_input_tokens),
                    SUM(total_output_tokens)
                FROM benchmark_runs 
                WHERE benchmark_id = ?
            """, (benchmark_id,))
            token_data = cursor.fetchone()
            std_tokens = token_data[0] if token_data and token_data[0] is not None else 0
            cached_tokens = token_data[1] if token_data and token_data[1] is not None else 0
            output_tokens = token_data[2] if token_data and token_data[2] is not None else 0
            
            # Calculate total tokens (standard + cached)
            total_tokens = std_tokens + cached_tokens + output_tokens
            
            # Get run count as total_items since we don't have prompt data
            cursor.execute("""
                SELECT COUNT(*) 
                FROM benchmark_runs 
                WHERE benchmark_id = ?
            """, (benchmark_id,))
            total_items = cursor.fetchone()[0]
            
            # Format timestamp
            formatted_timestamp = timestamp
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            benchmark = {
                "id": benchmark_id,
                "timestamp": formatted_timestamp,
                "status": "completed" if models else "in-progress",
                "label": label or f"Benchmark {benchmark_id}",
                "description": description,
                "models": models,
                "files": files,
                "mean_score": None,  # Not available in current schema
                "total_items": total_items,
                "elapsed_seconds": None,  # Not available in current schema
                "total_tokens": total_tokens,
            }
            
            benchmarks.append(benchmark)
        try:
            conn.close()
            log_to_file("Database connection closed properly")
        except Exception as close_error:
            log_to_file(f"Error closing database: {close_error}")
        
        log_to_file(f"Returning {len(benchmarks)} benchmarks")
        return benchmarks
        
    except Exception as e:
        error_msg = f"Error accessing database: {e}"
        log_to_file(error_msg)
        print(error_msg, file=sys.stderr)
        return []

if __name__ == "__main__":
    log_to_file("Script running in main context")
    benchmarks = get_benchmarks()
    log_to_file(f"Final benchmark count: {len(benchmarks)}")
    result = json.dumps(benchmarks)
    log_to_file(f"JSON result length: {len(result)}")
    print(result)
    log_to_file("Script completed")
