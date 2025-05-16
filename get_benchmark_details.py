#!/usr/bin/env python3
"""
Bridge script to get detailed benchmark information for the Electron UI.
Returns detailed benchmark data in JSON format for a specific benchmark run.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Database path - relative to the script location
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.db")

def get_benchmark_details(benchmark_id):
    """Fetch detailed data for a specific benchmark run"""
    if not os.path.exists(DB_PATH):
        return {"error": "Database not found"}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Query benchmark run details
        cursor.execute("""
            SELECT 
                br.id, 
                br.start_time, 
                br.end_time,
                br.pdf_path,
                br.label,
                br.total_standard_input_tokens,
                br.total_cached_input_tokens
            FROM 
                benchmark_runs br
            WHERE 
                br.id = ?
        """, (benchmark_id,))
        
        run = cursor.fetchone()
        if not run:
            return {"error": f"Benchmark ID {benchmark_id} not found"}
        
        # Get models used in this run
        cursor.execute("""
            SELECT DISTINCT model_name 
            FROM benchmark_prompts 
            WHERE run_id = ?
        """, (benchmark_id,))
        models = [row[0] for row in cursor.fetchall()]
        
        # Calculate elapsed time
        elapsed_seconds = None
        if run["start_time"] and run["end_time"]:
            try:
                start_dt = datetime.fromisoformat(run["start_time"])
                end_dt = datetime.fromisoformat(run["end_time"])
                elapsed_seconds = (end_dt - start_dt).total_seconds()
            except:
                pass
        
        # Get score data
        cursor.execute("""
            SELECT AVG(score), COUNT(*) 
            FROM benchmark_prompts 
            WHERE run_id = ? AND score IS NOT NULL
        """, (benchmark_id,))
        score_data = cursor.fetchone()
        mean_score = score_data[0] if score_data and score_data[0] is not None else None
        total_items = score_data[1] if score_data else 0
        
        # Calculate total tokens (standard + cached)
        total_tokens = 0
        if run["total_standard_input_tokens"] is not None:
            total_tokens += run["total_standard_input_tokens"]
        if run["total_cached_input_tokens"] is not None:
            total_tokens += run["total_cached_input_tokens"]
        
        # Get detailed prompt data
        cursor.execute("""
            SELECT 
                bp.id,
                bp.prompt_text,
                bp.expected_answer,
                bp.actual_answer,
                bp.score,
                bp.standard_input_tokens,
                bp.cached_input_tokens,
                bp.output_tokens,
                bp.model_name,
                bp.latency_ms
            FROM 
                benchmark_prompts bp
            WHERE 
                bp.run_id = ?
            ORDER BY 
                bp.id
        """, (benchmark_id,))
        
        prompts = []
        for prompt_row in cursor.fetchall():
            # Calculate total tokens per prompt (standard + cached)
            prompt_total_tokens = 0
            if prompt_row["standard_input_tokens"] is not None:
                prompt_total_tokens += prompt_row["standard_input_tokens"]
            if prompt_row["cached_input_tokens"] is not None:
                prompt_total_tokens += prompt_row["cached_input_tokens"]
            
            prompt_data = {
                "id": prompt_row["id"],
                "prompt_text": prompt_row["prompt_text"],
                "expected_answer": prompt_row["expected_answer"],
                "actual_answer": prompt_row["actual_answer"],
                "score": prompt_row["score"],
                "standard_input_tokens": prompt_row["standard_input_tokens"],
                "cached_input_tokens": prompt_row["cached_input_tokens"],
                "total_input_tokens": prompt_total_tokens,
                "output_tokens": prompt_row["output_tokens"],
                "model_name": prompt_row["model_name"],
                "latency_ms": prompt_row["latency_ms"]
            }
            prompts.append(prompt_data)
        
        # Format timestamp
        timestamp = run["start_time"]
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        benchmark_details = {
            "id": run["id"],
            "timestamp": timestamp,
            "status": "completed" if run["end_time"] else "in-progress",
            "label": run["label"] or f"Benchmark {run['id']}",
            "pdf_path": run["pdf_path"],
            "models": models,
            "mean_score": mean_score,
            "total_items": total_items,
            "elapsed_seconds": elapsed_seconds,
            "total_standard_input_tokens": run["total_standard_input_tokens"],
            "total_cached_input_tokens": run["total_cached_input_tokens"],
            "total_tokens": total_tokens,
            "prompts_data": prompts
        }
        
        conn.close()
        return benchmark_details
        
    except Exception as e:
        print(f"Error accessing database: {e}", file=sys.stderr)
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_benchmark_details.py <benchmark_id>")
        sys.exit(1)
    
    try:
        benchmark_id = int(sys.argv[1])
    except ValueError:
        print("Error: benchmark_id must be an integer")
        sys.exit(1)
    
    details = get_benchmark_details(benchmark_id)
    print(json.dumps(details))
