#!/usr/bin/env python3
"""
Bridge script to run benchmarks from the Electron UI.
Takes prompts, PDF path, and model names as arguments and runs the benchmark.
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime

# Database path - relative to the script location
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.db")

def run_benchmark(pdf_path, models, prompts):
    """
    Create a new benchmark run in the database and insert prompts.
    This is a simplified version that just creates the database entries
    without actually running the models - in a real implementation,
    this would call the actual benchmark code.
    """
    if not os.path.exists(pdf_path):
        return {"error": f"PDF file not found: {pdf_path}"}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY,
                start_time TEXT,
                end_time TEXT,
                pdf_path TEXT,
                label TEXT,
                total_standard_input_tokens INTEGER,
                total_cached_input_tokens INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_prompts (
                id INTEGER PRIMARY KEY,
                run_id INTEGER,
                prompt_text TEXT,
                expected_answer TEXT,
                actual_answer TEXT,
                score REAL,
                standard_input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                model_name TEXT,
                latency_ms INTEGER,
                FOREIGN KEY (run_id) REFERENCES benchmark_runs(id)
            )
        """)
        
        # Insert a new benchmark run
        now = datetime.now().isoformat()
        label = f"Benchmark {now}"
        
        cursor.execute("""
            INSERT INTO benchmark_runs
            (start_time, pdf_path, label, total_standard_input_tokens, total_cached_input_tokens)
            VALUES (?, ?, ?, 0, 0)
        """, (now, pdf_path, label))
        
        run_id = cursor.lastrowid
        
        # Insert prompts - in a real implementation, these would be run against the models
        total_standard_tokens = 0
        total_cached_tokens = 0
        
        for model_name in models:
            for prompt in prompts:
                prompt_text = prompt.get('prompt_text', '')
                expected_answer = prompt.get('expected_answer', '')
                
                # Simulate model output and tokens
                # In a real implementation, this would call the actual model API
                actual_answer = f"Sample response for: {prompt_text[:30]}..."
                score = 0.5  # Placeholder score
                
                # Simulate token counts - in a real implementation these would come from the API
                standard_tokens = len(prompt_text.split()) + 10
                cached_tokens = 0  # Assuming first run has no cached tokens
                output_tokens = len(actual_answer.split())
                latency = 500  # 500ms placeholder
                
                total_standard_tokens += standard_tokens
                total_cached_tokens += cached_tokens
                
                cursor.execute("""
                    INSERT INTO benchmark_prompts
                    (run_id, prompt_text, expected_answer, actual_answer, score,
                     standard_input_tokens, cached_input_tokens, output_tokens, model_name, latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, prompt_text, expected_answer, actual_answer, score,
                     standard_tokens, cached_tokens, output_tokens, model_name, latency))
        
        # Update the run with token totals
        cursor.execute("""
            UPDATE benchmark_runs
            SET total_standard_input_tokens = ?,
                total_cached_input_tokens = ?
            WHERE id = ?
        """, (total_standard_tokens, total_cached_tokens, run_id))
        
        # Mark run as completed
        end_time = datetime.now().isoformat()
        cursor.execute("""
            UPDATE benchmark_runs
            SET end_time = ?
            WHERE id = ?
        """, (end_time, run_id))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "run_id": run_id,
            "message": f"Benchmark created with {len(prompts)} prompts for {len(models)} models"
        }
        
    except Exception as e:
        print(f"Error running benchmark: {e}", file=sys.stderr)
        return {"error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a benchmark from Electron UI")
    parser.add_argument('--pdf', required=True, help="Path to PDF file")
    parser.add_argument('--models', required=True, help="Comma-separated list of model names")
    parser.add_argument('--prompts', required=True, help="JSON string containing prompts data")
    
    args = parser.parse_args()
    
    models = args.models.split(',')
    try:
        prompts = json.loads(args.prompts)
    except json.JSONDecodeError:
        print("Error: Invalid JSON format for prompts")
        sys.exit(1)
    
    result = run_benchmark(args.pdf, models, prompts)
    print(json.dumps(result))
