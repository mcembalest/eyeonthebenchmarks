#!/usr/bin/env python3
"""
Direct benchmark execution script - designed to run benchmarks directly with minimal dependencies.
This is a simplified version that can be called as a separate process from app.py
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
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

def run_direct_benchmark(job_id, benchmark_id, prompts, pdf_path, model_name):
    """
    Run a benchmark directly without complex importing
    """
    t0 = time.time()
    pdf_path_obj = Path(pdf_path) if pdf_path else None
    
    try:
        # Add the current directory to sys.path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        print(f"Added {project_root} to Python path")
        sys.stdout.flush()
        
        # Verify the PDF exists and is readable if provided
        if pdf_path_obj:
            if not pdf_path_obj.exists():
                error_msg = f"PDF file not found: {pdf_path}"
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
                
            print(f"PDF file found: {pdf_path} (Size: {pdf_path_obj.stat().st_size / 1024:.1f} KB)")
        else:
            print("No PDF file provided - running benchmark without document context")
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check if we have the API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            print(f"OPENAI_API_KEY is set (length: {len(api_key)})")
            print(f"API key starts with: {api_key[:5]}... ends with: ...{api_key[-3:]}")
            sys.stdout.flush()
        else:
            error_msg = "OPENAI_API_KEY is not set!"
            print(f"ERROR: {error_msg}")
            print("Looking for .env file...")
            env_path = os.path.join(project_root, '.env')
            if os.path.exists(env_path):
                print(f".env file exists at {env_path}")
                with open(env_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        print(f"Found content in .env file (length: {len(content)})")
                        try:
                            # Re-try loading with explicit path
                            load_dotenv(env_path)
                            print("Re-loaded environment variables from explicit path")
                            api_key = os.environ.get('OPENAI_API_KEY')
                            if api_key:
                                print(f"SUCCESS: API key loaded now (length: {len(api_key)})")
                            else:
                                print("ERROR: Still could not load API key!")
                        except Exception as e:
                            print(f"Error loading .env file: {e}")
                    else:
                        print("ERROR: .env file exists but is empty!")
            else:
                print(f"ERROR: No .env file found at {env_path}")
                
            # Stop if no API key after attempts to load it
            if not os.environ.get('OPENAI_API_KEY'):
                error_msg = "Failed to load OpenAI API key from environment or .env file"
                emit_progress({
                    "job_id": job_id,
                    "benchmark_id": benchmark_id,
                    "model_name": model_name,
                    "status": "error",
                    "message": error_msg
                })
                return {"success": False, "error": error_msg}
        
        sys.stdout.flush()
        
        # List available modules
        import pkgutil
        print("Available modules in path:")
        modules = list(pkgutil.iter_modules([str(project_root)]))
        for module in modules:
            print(f"  - {module.name}")
        sys.stdout.flush()
        
        # Import the run_benchmark function directly
        print("Importing run_benchmark from runner module...")
        sys.stdout.flush()
        
        try:
            from runner import run_benchmark, set_emit_progress_callback
            print("Successfully imported run_benchmark function")
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
        if pdf_path_obj:
            print(f"Starting benchmark with model {model_name} on {pdf_path}")
        else:
            print(f"Starting benchmark with model {model_name} without document context")
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
        
        # Run the actual benchmark
        print(f"\n🔄 STARTING OPENAI API CALL WITH MODEL {model_name}...")
        sys.stdout.flush()
        result = run_benchmark(prompts, pdf_path, model_name)
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
    # Expecting args: job_id, benchmark_id, prompts_file_path, pdf_path, model_name
    if len(sys.argv) != 6:
        print(f"ERROR: Usage: python {sys.argv[0]} <job_id> <benchmark_id> <prompts_file> <pdf_path> <model_name>")
        sys.exit(1)
    try:
        job_id = int(sys.argv[1])
        benchmark_id = int(sys.argv[2])
        prompts_file = sys.argv[3]
        pdf_path = sys.argv[4]
        model_name = sys.argv[5]
    except Exception as e:
        print(f"ERROR: Invalid arguments: {e}")
        sys.exit(1)
    # Load prompts list
    try:
        with open(prompts_file, 'r') as f:
            prompts = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load prompts file: {e}")
        sys.exit(1)
    # Run the direct benchmark
    run_direct_benchmark(job_id, benchmark_id, prompts, pdf_path, model_name)
