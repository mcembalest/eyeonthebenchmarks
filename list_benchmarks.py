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
import sqlite3

# Import file_store module for database functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from file_store import load_all_benchmarks_with_models

# Setup logs directory
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = SCRIPT_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
LOG_FILE = LOGS_DIR / 'list_benchmarks.log'
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler(sys.stderr)
                    ])

# Initialize log file
logging.info("Starting benchmark listing")

# Use script directory (not the file path) for database operations
# The database file will be automatically located by the file_store module
DB_DIR = SCRIPT_DIR
logging.info(f"Using database directory: {DB_DIR}")

def get_benchmarks():
    """Fetch benchmark data from the database using file_store module"""
    logging.info("Starting get_benchmarks function")
    
    try:
        db_dir = Path(__file__).parent  # Get the directory of this script
        conn = sqlite3.connect(db_dir / 'eotm_file_store.sqlite')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.id, b.created_at, b.label, b.description FROM benchmarks b
            ORDER BY b.created_at DESC
        ''')
        benchmark_rows = [dict(row) for row in cursor.fetchall()]
        
        # List to store processed benchmarks for UI
        processed_benchmarks = []

        # Process each benchmark
        for benchmark in benchmark_rows:
            # Convert timestamp to ISO format string
            try:
                timestamp = benchmark.pop('created_at')
                formatted_timestamp = datetime.fromisoformat(timestamp).isoformat() if timestamp else None
            except (ValueError, TypeError):
                formatted_timestamp = None
                
            benchmark_id = benchmark['id']
            
            # Get file paths
            cursor.execute('''
                SELECT file_path FROM benchmark_files WHERE benchmark_id = ?
            ''', (benchmark_id,))
            files = [row['file_path'] for row in cursor.fetchall()]

            # Get model names from runs table (completed runs) 
            cursor.execute('''
                SELECT DISTINCT model_name FROM benchmark_runs WHERE benchmark_id = ?
            ''', (benchmark_id,))
            completed_models = [row['model_name'] for row in cursor.fetchall()]
            
            # Also check for in-progress models in prompts table that haven't completed yet
            cursor.execute('''
                SELECT DISTINCT model_name FROM benchmark_prompts WHERE benchmark_id = ?
                AND model_name NOT IN (SELECT DISTINCT model_name FROM benchmark_runs WHERE benchmark_id = ?)
            ''', (benchmark_id, benchmark_id))
            in_progress_models = [row['model_name'] for row in cursor.fetchall()]
            
            # Combine completed and in-progress models
            models = completed_models + in_progress_models

            # Create model_results dictionary for UI consumption
            model_results = {}
            model_details = {}
            
            # Track token counts
            total_standard_tokens = 0
            total_cached_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            
            # Process completed models first
            for model_name in completed_models:
                cursor.execute('''
                    SELECT id, mean_score, total_items, elapsed_seconds,
                           standard_input_tokens, cached_input_tokens, output_tokens
                    FROM benchmark_runs 
                    WHERE benchmark_id = ? AND model_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (benchmark_id, model_name))
                run = cursor.fetchone()
                if run:
                    run_dict = dict(run)
                    run_id = run_dict.pop('id')
                    
                    # Get token counts - handle nulls/None values with default 0
                    standard_tokens = int(run_dict.get('standard_input_tokens') or 0)
                    cached_tokens = int(run_dict.get('cached_input_tokens') or 0)
                    output_tokens = int(run_dict.get('output_tokens') or 0)
                    tokens_subtotal = standard_tokens + cached_tokens + output_tokens
                    
                    # Add to totals
                    total_standard_tokens += standard_tokens
                    total_cached_tokens += cached_tokens
                    total_output_tokens += output_tokens
                    
                    model_results[model_name] = {
                        'run_id': run_id,
                        'status': 'complete',
                        'score': run_dict['mean_score'],
                        'total_items': run_dict['total_items'],
                        'elapsed_seconds': run_dict['elapsed_seconds'],
                        'standard_input_tokens': standard_tokens,
                        'cached_input_tokens': cached_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': tokens_subtotal
                    }
                    
                    # Simplified cost calculation (can be enhanced)
                    model_cost = (standard_tokens / 1000 * 0.01) + (output_tokens / 1000 * 0.03)
                    total_cost += model_cost
                    
                    # Store model details for UI
                    model_details[model_name] = {
                        'status': 'complete',
                        'tokens': tokens_subtotal,
                        'cost': '${:.4f}'.format(model_cost)
                    }
            
            # Add in-progress models with status='running'
            for model_name in in_progress_models:
                # Count how many prompts have been processed for this model
                cursor.execute('''
                    SELECT COUNT(*) as prompt_count FROM benchmark_prompts
                    WHERE benchmark_id = ? AND model_name = ?
                ''', (benchmark_id, model_name))
                prompt_count = cursor.fetchone()['prompt_count']
                
                model_results[model_name] = {
                    'run_id': None,
                    'status': 'running' if prompt_count > 0 else 'pending',
                    'score': None,
                    'total_items': prompt_count,
                    'elapsed_seconds': None,
                    'standard_input_tokens': 0,
                    'cached_input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0,
                    'progress': min(1.0, prompt_count / 10.0) if prompt_count > 0 else 0  # Assume ~10 prompts
                }
                
                # Store model details for UI
                model_details[model_name] = {
                    'status': 'running' if prompt_count > 0 else 'pending',
                    'tokens': 0,
                    'cost': '$0.00'
                }
            
            # Calculate mean score across all models
            mean_scores = [float(result.get('score', 0)) for result in model_results.values() 
                          if result.get('score') not in ('N/A', None)]
            mean_score = sum(mean_scores) / len(mean_scores) if mean_scores else None
            
            # Create the benchmark object for UI with detailed token breakdowns
            ui_benchmark = {
                "id": benchmark.get('id'),
                "timestamp": formatted_timestamp,
                "status": "completed" if models else "in-progress",
                "label": benchmark.get('label') or f"Benchmark {benchmark.get('id')}",
                "description": benchmark.get('description', ''),
                "files": files,
                "models": models,
                "mean_score": '{:.2f}'.format(mean_score) if mean_score is not None else 'N/A',
                # Include detailed token counts with labels for UI display
                "total_tokens": total_standard_tokens + total_cached_tokens + total_output_tokens,
                "standard_input_tokens": total_standard_tokens,
                "cached_input_tokens": total_cached_tokens,
                "output_tokens": total_output_tokens,
                # Format cost with consistent decimal places
                "estimated_cost": '${:.4f}'.format(total_cost) if total_cost else 'N/A',
                "model_details": model_details
            }
            
            processed_benchmarks.append(ui_benchmark)
        
        conn.close()
        logging.info(f"Processed {len(processed_benchmarks)} benchmarks for UI")
        return processed_benchmarks
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print(f"Database error: {e}")
        return []

if __name__ == "__main__":
    logging.info("Script running in main context")
    try:
        benchmarks = get_benchmarks()
        print(json.dumps(benchmarks))
        logging.info("Successfully printed benchmark data")
        sys.exit(0)
    except Exception as e:
        error_msg = f"Error running script: {e}"
        logging.error(error_msg, exc_info=True)
        print(json.dumps({"error": error_msg}))
        sys.exit(1)
    finally:
        logging.info("Script completed")
