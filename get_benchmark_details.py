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
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eotm_file_store.sqlite")

def get_benchmark_details(benchmark_id):
    """Fetch detailed data for a specific benchmark"""
    if not os.path.exists(DB_PATH):
        return {"error": "Database not found"}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # First, get the benchmark info
        cursor.execute("""
            SELECT 
                id,
                timestamp,
                label,
                description
            FROM 
                benchmarks
            WHERE 
                id = ?
        """, (benchmark_id,))
        
        benchmark = cursor.fetchone()
        if not benchmark:
            return {"error": f"Benchmark ID {benchmark_id} not found"}
            
        # Now query the associated benchmark run details
        cursor.execute("""
            SELECT 
                br.id, 
                br.created_at, 
                br.model_name,
                br.report,
                br.latency,
                br.total_standard_input_tokens,
                br.total_cached_input_tokens,
                br.total_output_tokens
            FROM 
                benchmark_runs br
            WHERE 
                br.benchmark_id = ?
        """, (benchmark_id,))
        
        run = cursor.fetchone()
        if not run:
            return {"error": f"Benchmark ID {benchmark_id} not found"}
        
        # Get models used in this run
        cursor.execute("""
            SELECT DISTINCT model_name 
            FROM benchmark_runs 
            WHERE benchmark_id = ?
        """, (benchmark_id,))
        models = [row[0] for row in cursor.fetchall()]
        
        # We don't have elapsed time data in this schema
        elapsed_seconds = None
        
        # Get score data - now we need to get prompts across all runs for this benchmark
        cursor.execute("""
            SELECT AVG(CAST(bp.score AS REAL)), COUNT(*) 
            FROM benchmark_prompts bp
            JOIN benchmark_runs br ON bp.benchmark_run_id = br.id
            WHERE br.benchmark_id = ? AND bp.score IS NOT NULL
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
        
        # Get detailed prompt data for all runs of this benchmark
        cursor.execute("""
            SELECT 
                bp.id,
                bp.prompt,
                bp.answer,
                bp.response,
                bp.score,
                bp.standard_input_tokens,
                bp.cached_input_tokens,
                bp.output_tokens,
                bp.latency,
                br.model_name
            FROM 
                benchmark_prompts bp
            JOIN
                benchmark_runs br ON bp.benchmark_run_id = br.id
            WHERE 
                br.benchmark_id = ?
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
                "prompt_text": prompt_row["prompt"],
                "expected_answer": prompt_row["answer"],
                "actual_answer": prompt_row["response"],
                "score": prompt_row["score"],
                "standard_input_tokens": prompt_row["standard_input_tokens"],
                "cached_input_tokens": prompt_row["cached_input_tokens"],
                "total_input_tokens": prompt_total_tokens,
                "output_tokens": prompt_row["output_tokens"],
                "model_name": prompt_row["model_name"],
                "latency_ms": prompt_row["latency"]
            }
            prompts.append(prompt_data)
        
        # Format timestamp
        timestamp = benchmark["timestamp"]
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        # Sum up token counts from all runs
        cursor.execute("""
            SELECT 
                SUM(total_standard_input_tokens), 
                SUM(total_cached_input_tokens),
                SUM(total_output_tokens)
            FROM 
                benchmark_runs 
            WHERE 
                benchmark_id = ?
        """, (benchmark_id,))
        token_sums = cursor.fetchone()
        
        total_std_tokens = token_sums[0] if token_sums and token_sums[0] is not None else 0
        total_cached_tokens = token_sums[1] if token_sums and token_sums[1] is not None else 0
        total_output_tokens = token_sums[2] if token_sums and token_sums[2] is not None else 0
        total_tokens = total_std_tokens + total_cached_tokens + total_output_tokens
        
        benchmark_details = {
            "id": benchmark["id"],
            "timestamp": timestamp,
            "status": "completed",
            "label": benchmark["label"] or f"Benchmark {benchmark['id']}",
            "description": benchmark["description"],
            "models": models,
            "mean_score": mean_score,
            "total_items": total_items,
            "elapsed_seconds": elapsed_seconds,
            "total_standard_input_tokens": total_std_tokens,
            "total_cached_input_tokens": total_cached_tokens,
            "total_output_tokens": total_output_tokens,
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
