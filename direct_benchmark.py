#!/usr/bin/env python3
"""
Direct benchmark execution script - designed to run benchmarks directly with minimal dependencies.
This script runs benchmarks using the new multi-provider, multi-file database system.
"""

import os
import sys
import json
import logging
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def emit_progress(data: dict):
    """
    Simple progress reporter that outputs JSON to stdout
    """
    # Output progress as JSON for the parent process
    print(json.dumps({
        "ui_bridge_event": "benchmark-progress", 
        "data": data
    }))
    sys.stdout.flush()

def emit_completion(data: dict):
    """
    Simple completion reporter that outputs JSON to stdout
    """
    # Output completion as JSON for the parent process
    print(json.dumps({
        "ui_bridge_event": "benchmark-complete", 
        "data": data
    }))
    sys.stdout.flush()

def run_direct_benchmark_from_db(job_id, benchmark_id, prompts, model_name):
    """
    Run a benchmark using files from the database
    """
    t0 = time.time()
    
    try:
        # Add the current directory to sys.path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        print(f"Added {project_root} to Python path")
        sys.stdout.flush()
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check if we have the required API keys
        openai_key = os.environ.get('OPENAI_API_KEY')
        google_key = os.environ.get('GOOGLE_API_KEY')
        
        if openai_key:
            print(f"OPENAI_API_KEY is set (length: {len(openai_key)})")
        if google_key:
            print(f"GOOGLE_API_KEY is set (length: {len(google_key)})")
        
        if not openai_key and not google_key:
            error_msg = "Neither OPENAI_API_KEY nor GOOGLE_API_KEY is set!"
            print(f"ERROR: {error_msg}")
            emit_progress({
                "job_id": job_id,
                "benchmark_id": benchmark_id,
                "model_name": model_name,
                "status": "error",
                "message": error_msg
            })
            return {"success": False, "error": error_msg}
        
        sys.stdout.flush()
        
        # Import the run_benchmark function directly
        print("Importing run_benchmark_from_db from runner module...")
        sys.stdout.flush()
        
        try:
            from runner import run_benchmark_from_db, set_emit_progress_callback
            print("Successfully imported run_benchmark_from_db function")
            sys.stdout.flush()
        except ImportError as e:
            error_msg = f"Failed to import required modules: {str(e)}"
            print(f"ERROR: {error_msg}")
            sys.stdout.flush()
            emit_progress({
                "job_id": job_id,
                "benchmark_id": benchmark_id,
                "model_name": model_name,
                "status": "error",
                "message": error_msg
            })
            return {"success": False, "error": error_msg}
        
        # Set up a custom progress callback
        def progress_callback(progress_data):
            emit_progress({
                "job_id": job_id,
                "benchmark_id": benchmark_id,
                "model_name": model_name,
                "status": "progress",
                **progress_data
            })
        
        # Set the progress callback
        set_emit_progress_callback(progress_callback)
        
        # Log start of benchmark
        print(f"Starting benchmark {benchmark_id} with model {model_name}")
        print(f"Number of prompts: {len(prompts)}")
        sys.stdout.flush()
        
        # Report initial progress
        emit_progress({
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "model_name": model_name,
            "status": "running",
            "message": f"Starting benchmark with model {model_name}"
        })
        
        # Run the actual benchmark using database files
        print(f"\n🔄 STARTING BENCHMARK WITH MODEL {model_name}...")
        sys.stdout.flush()
        result = run_benchmark_from_db(prompts, benchmark_id, model_name)
        duration = time.time() - t0
        print(f"\n✅ BENCHMARK COMPLETED IN {duration:.2f} SECONDS")
        sys.stdout.flush()
        
        # Add additional information to result
        result["job_id"] = job_id
        result["benchmark_id"] = benchmark_id
        result["model_name"] = model_name
        result["duration_seconds"] = duration
        result["status"] = "complete"
        
        # Report completion to parent process
        emit_completion({
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "model_name": model_name,
            "status": "complete",
            **result
        })
        sys.stdout.flush()

        # Return the result as JSON
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {str(e)}")
        print(error_details)
        sys.stdout.flush()
        
        # Report error
        emit_completion({
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "model_name": model_name,
            "status": "failed",
            "error": str(e),
            "error_details": error_details
        })
        
        return {
            "success": False,
            "error": str(e),
            "error_details": error_details
        }

# Entry point for subprocess execution
if __name__ == "__main__":
    import sys, json
    
    if len(sys.argv) != 5:
        print(f"ERROR: Usage: python {sys.argv[0]} <job_id> <benchmark_id> <prompts_file> <model_name>")
        sys.exit(1)
    
    try:
        job_id = int(sys.argv[1])
        benchmark_id = int(sys.argv[2])
        prompts_file = sys.argv[3]
        model_name = sys.argv[4]
        
        # Load prompts list
        with open(prompts_file, 'r') as f:
            prompts = json.load(f)
        
        # Run the database-based benchmark
        run_direct_benchmark_from_db(job_id, benchmark_id, prompts, model_name)
        
    except Exception as e:
        print(f"ERROR: Invalid arguments: {e}")
        sys.exit(1)