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

# Database path - relative to the script location
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.db")

def get_benchmarks():
    """Fetch benchmark data from the database"""
    if not os.path.exists(DB_PATH):
        return []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Query benchmark runs
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
            ORDER BY 
                br.start_time DESC
        """)
        
        runs = cursor.fetchall()
        benchmarks = []
        
        for run in runs:
            run_id, start_time, end_time, pdf_path, label, std_tokens, cached_tokens = run
            
            # Get models used in this run
            cursor.execute("""
                SELECT DISTINCT model_name 
                FROM benchmark_prompts 
                WHERE run_id = ?
            """, (run_id,))
            models = [row[0] for row in cursor.fetchall()]
            
            # Calculate elapsed time
            elapsed_seconds = None
            if start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    end_dt = datetime.fromisoformat(end_time)
                    elapsed_seconds = (end_dt - start_dt).total_seconds()
                except:
                    pass
            
            # Get score data
            cursor.execute("""
                SELECT AVG(score), COUNT(*) 
                FROM benchmark_prompts 
                WHERE run_id = ? AND score IS NOT NULL
            """, (run_id,))
            score_data = cursor.fetchone()
            mean_score = score_data[0] if score_data and score_data[0] is not None else None
            total_items = score_data[1] if score_data else 0
            
            # Handle file names
            files = []
            if pdf_path:
                files.append(os.path.basename(pdf_path))
            
            # Calculate total tokens (standard + cached)
            total_tokens = 0
            if std_tokens is not None:
                total_tokens += std_tokens
            if cached_tokens is not None:
                total_tokens += cached_tokens
            
            # Format timestamp
            timestamp = start_time
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            benchmark = {
                "id": run_id,
                "timestamp": timestamp,
                "status": "completed" if end_time else "in-progress",
                "label": label or f"Benchmark {run_id}",
                "models": models,
                "files": files,
                "mean_score": mean_score,
                "total_items": total_items,
                "elapsed_seconds": elapsed_seconds,
                "total_tokens": total_tokens,
            }
            
            benchmarks.append(benchmark)
        
        conn.close()
        return benchmarks
        
    except Exception as e:
        print(f"Error accessing database: {e}", file=sys.stderr)
        return []

if __name__ == "__main__":
    benchmarks = get_benchmarks()
    print(json.dumps(benchmarks))
