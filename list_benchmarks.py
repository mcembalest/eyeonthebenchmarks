#!/usr/bin/env python3
"""
Bridge script to list benchmarks for the Electron UI.
Returns benchmark data in JSON format for the UI to render.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Import file_store module for database functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.file_store import load_all_benchmarks_with_models

# Setup logs directory
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = SCRIPT_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
LOG_FILE = LOGS_DIR / 'list_benchmarks.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Initialize log file
logging.info("Starting benchmark listing")

# Database path - relative to the script location
DB_PATH = SCRIPT_DIR / "eotm_file_store.sqlite"
logging.info(f"Using database path: {DB_PATH}")
print(f"Using database path: {DB_PATH}", file=sys.stderr)

# Note: Cost calculation now handled by file_store.py

# Note: Cost calculation function removed as this is now handled by file_store.py

def get_benchmarks():
    """Fetch benchmark data from the database using file_store module"""
    logging.info("Starting get_benchmarks function")
    
    try:
        # Use the file_store function to get all benchmarks with models and files
        db_path = SCRIPT_DIR  # Use the script directory as database path
        benchmarks_data = load_all_benchmarks_with_models(db_path)
        logging.info(f"Retrieved {len(benchmarks_data)} benchmarks from database")
        
        # Process benchmark data to match the expected format for the UI
        benchmarks = []
        for benchmark in benchmarks_data:
            # Format timestamp with error handling
            formatted_timestamp = benchmark.get('timestamp')
            if formatted_timestamp:
                try:
                    dt = datetime.fromisoformat(formatted_timestamp)
                    formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except Exception as e:
                    logging.warning(f"Failed to parse timestamp {formatted_timestamp}: {e}")
            
            # Extract file names from paths for UI display
            files = [os.path.basename(path) for path in benchmark.get('file_paths', []) if path]
            
            # Get model details and token information
            models = benchmark.get('model_names', [])
            model_results = benchmark.get('model_results', {})
            
            # Calculate totals across all models
            total_standard_tokens = 0
            total_cached_tokens = 0
            total_output_tokens = 0
            total_cost = 0
            
            # Calculate model-specific details
            model_details = {}
            for model_name, result in model_results.items():
                # Extract token information
                std_tokens = result.get('standard_input_tokens', 0)
                cached_tokens = result.get('cached_input_tokens', 0)
                output_tokens = result.get('output_tokens', 0)
                cost = result.get('cost', 0)
                if cost != 'N/A':
                    total_cost += float(cost) if isinstance(cost, (int, float, str)) else 0
                
                # Add to totals
                total_standard_tokens += std_tokens
                total_cached_tokens += cached_tokens
                total_output_tokens += output_tokens
                
                # Create model details for UI
                model_details[model_name] = {
                    "standard_input_tokens": std_tokens,
                    "cached_input_tokens": cached_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": std_tokens + cached_tokens + output_tokens,
                    "estimated_cost": cost
                }
            
            # Get aggregate score across all models
            mean_scores = [result.get('score', 0) for result in model_results.values() 
                          if result.get('score') != 'N/A']
            mean_score = sum(mean_scores) / len(mean_scores) if mean_scores else None
            
            # Use the most recent run date if available
            last_run_date = None
            for result in model_results.values():
                if 'last_run_date' in result and result['last_run_date']:
                    last_run_date = result['last_run_date']
                    break
            
            # Create the benchmark object for UI
            ui_benchmark = {
                "id": benchmark.get('id'),
                "timestamp": formatted_timestamp,
                "status": "completed" if models else "in-progress",
                "label": benchmark.get('label') or f"Benchmark {benchmark.get('id')}",
                "description": benchmark.get('description'),
                "models": models,
                "files": files,
                "mean_score": mean_score,
                "mean_score_percentage": f"{mean_score * 100:.1f}%" if mean_score is not None else "N/A",
                "prompt_count": benchmark.get('prompt_count', 0),
                "run_count": len(models),
                "total_items": benchmark.get('prompt_count', 0) or len(models),  # Prefer prompt count if available
                "elapsed_seconds": None,  # Not directly available
                "last_run_date": last_run_date,
                "total_standard_input_tokens": total_standard_tokens,
                "total_cached_input_tokens": total_cached_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_standard_tokens + total_cached_tokens + total_output_tokens,
                "total_cost_usd": round(total_cost, 4),
                "model_details": model_details
            }
            
            benchmarks.append(ui_benchmark)
        
        logging.info(f"Processed {len(benchmarks)} benchmarks for UI")
        return benchmarks
        
    except Exception as e:
        error_msg = f"Error getting benchmarks: {e}"
        logging.error(error_msg, exc_info=True)
        print(error_msg, file=sys.stderr)
        return []

if __name__ == "__main__":
    logging.info("Script running in main context")
    try:
        benchmarks = get_benchmarks()
        logging.info(f"Final benchmark count: {len(benchmarks)}")
        result = json.dumps(benchmarks)
        logging.info(f"JSON result length: {len(result)}")
        print(result)
    except Exception as e:
        error_msg = f"Unhandled error in main: {e}"
        logging.error(error_msg, exc_info=True)
        print(json.dumps({"error": error_msg}))
    finally:
        logging.info("Script completed")
