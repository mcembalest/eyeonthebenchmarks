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

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
print(f"Added {project_root} to Python path")
sys.stdout.flush()

from dotenv import load_dotenv
load_dotenv()

from runner import run_benchmark_from_db, set_emit_progress_callback
from file_store import (save_benchmark_run, save_benchmark_prompt_atomic, 
                        update_benchmark_run, update_worker_heartbeat, 
                        mark_prompt_failed)

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

def run_direct_benchmark_from_db(job_id, benchmark_id, prompts, model_name, web_search_enabled=False):
    """
    Run a benchmark using files from the database
    """
    t0 = time.time()
    
    try:
        if model_name.startswith("gemini-"):
            provider = "google"
        elif model_name.startswith("claude-"):
            provider = "anthropic"
        else:
            provider = "openai"
        
        # Create the run record with initial values (will be updated when complete)
        run_id = save_benchmark_run(
            benchmark_id=benchmark_id,
            model_name=model_name,
            provider=provider,
            report="", 
            latency=0.0,
            total_standard_input_tokens=0,
            total_cached_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            total_input_cost=0.0,
            total_cached_cost=0.0,
            total_output_cost=0.0,
            total_cost=0.0
        )
        
        if not run_id:
            error_msg = f"Failed to create benchmark run record for model {model_name}"
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
        
        print(f"Created benchmark run record with ID: {run_id}")
        sys.stdout.flush()
        
        # Create a callback to save individual prompts as they complete
        def on_prompt_complete(prompt_index, prompt_result):
            try:
                print(f"Saving prompt {prompt_index + 1} result to database...")
                sys.stdout.flush()
                
                # Update worker heartbeat to show activity
                update_worker_heartbeat(run_id)
                
                # Check if this is a single prompt rerun (passed via environment or special parameter)
                import os
                single_prompt_id = os.environ.get('SINGLE_PROMPT_RERUN_ID')
                
                if single_prompt_id:
                    # Update existing prompt instead of creating new one
                    print(f"Updating existing prompt {single_prompt_id} with rerun results...")
                    from file_store import update_prompt_result
                    success = update_prompt_result(
                        prompt_id=int(single_prompt_id),
                        response=prompt_result["model_answer"],
                        latency=prompt_result["latency_ms"],
                        standard_input_tokens=prompt_result["standard_input_tokens"],
                        cached_input_tokens=prompt_result["cached_input_tokens"],
                        output_tokens=prompt_result["output_tokens"],
                        thinking_tokens=prompt_result.get("thinking_tokens", 0),
                        reasoning_tokens=prompt_result.get("reasoning_tokens", 0),
                        input_cost=prompt_result["input_cost"],
                        cached_cost=prompt_result["cached_cost"],
                        output_cost=prompt_result["output_cost"],
                        thinking_cost=prompt_result.get("thinking_cost", 0.0),
                        reasoning_cost=prompt_result.get("reasoning_cost", 0.0),
                        total_cost=prompt_result["total_cost"],
                        web_search_used=prompt_result.get("web_search_used", False),
                        web_search_sources=prompt_result.get("web_search_sources", ""),
                        truncation_info=prompt_result.get("truncation_info", "")
                    )
                    if success:
                        print(f"✅ Updated existing prompt {single_prompt_id}")
                        prompt_id = int(single_prompt_id)
                    else:
                        print(f"❌ Failed to update existing prompt {single_prompt_id}")
                        prompt_id = None
                else:
                    # Normal operation - save new prompt
                    prompt_id = save_benchmark_prompt_atomic(
                        benchmark_run_id=run_id,
                        prompt=prompt_result["prompt_text"],
                        response=prompt_result["model_answer"],
                        latency=prompt_result["latency_ms"],
                        standard_input_tokens=prompt_result["standard_input_tokens"],
                        cached_input_tokens=prompt_result["cached_input_tokens"],
                        output_tokens=prompt_result["output_tokens"],
                        thinking_tokens=prompt_result.get("thinking_tokens", 0),
                        reasoning_tokens=prompt_result.get("reasoning_tokens", 0),
                        input_cost=prompt_result["input_cost"],
                        cached_cost=prompt_result["cached_cost"],
                        output_cost=prompt_result["output_cost"],
                        thinking_cost=prompt_result.get("thinking_cost", 0.0),
                        reasoning_cost=prompt_result.get("reasoning_cost", 0.0),
                        total_cost=prompt_result["total_cost"],
                        web_search_used=prompt_result.get("web_search_used", False),
                        web_search_sources=prompt_result.get("web_search_sources", ""),
                        truncation_info=prompt_result.get("truncation_info", "")
                    )
                
                if prompt_id:
                    print(f"✅ Saved prompt {prompt_index + 1} with ID: {prompt_id}")
                    
                    # Emit progress update with prompt completion
                    emit_progress({
                        "job_id": job_id,
                        "benchmark_id": benchmark_id,
                        "model_name": model_name,
                        "status": "prompt_complete",
                        "prompt_index": prompt_index,
                        "total_prompts": len(prompts),
                        "message": f"Completed prompt {prompt_index + 1}/{len(prompts)}"
                    })
                else:
                    print(f"❌ Failed to save prompt {prompt_index + 1}")
                    
                sys.stdout.flush()
                
            except Exception as e:
                print(f"❌ Error saving prompt {prompt_index + 1}: {str(e)}")
                sys.stdout.flush()
                # Try to mark the prompt as failed
                try:
                    mark_prompt_failed(
                        benchmark_run_id=run_id,
                        prompt=prompt_result.get("prompt_text", f"Prompt {prompt_index + 1}"),
                        error_message=str(e)
                    )
                except Exception as mark_error:
                    print(f"Failed to mark prompt as failed: {mark_error}")
                    sys.stdout.flush()
        
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
        
        # Start heartbeat thread
        import threading
        heartbeat_stop = threading.Event()
        
        def heartbeat_worker():
            """Send periodic heartbeat updates"""
            while not heartbeat_stop.is_set():
                try:
                    update_worker_heartbeat(run_id)
                except Exception as e:
                    print(f"Failed to update heartbeat: {e}")
                # Wait 30 seconds before next heartbeat
                heartbeat_stop.wait(30)
        
        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()
        
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
        result = run_benchmark_from_db(prompts, benchmark_id, model_name, on_prompt_complete=on_prompt_complete, web_search_enabled=web_search_enabled)
        
        # Stop heartbeat thread
        heartbeat_stop.set()
        duration = time.time() - t0
        print(f"\n✅ BENCHMARK COMPLETED IN {duration:.2f} SECONDS")
        sys.stdout.flush()
        
        # Update the benchmark run record with final totals
        if result and not result.get("error"):
            print(f"Updating benchmark run {run_id} with final totals...")
            sys.stdout.flush()
            
            try:
                # Update the run record with final values
                success = update_benchmark_run(
                    run_id=run_id,
                    latency=result.get("elapsed_s", 0.0) * 1000,  # Convert to ms
                    total_standard_input_tokens=result.get("total_standard_input_tokens", 0),
                    total_cached_input_tokens=result.get("total_cached_input_tokens", 0),
                    total_output_tokens=result.get("total_output_tokens", 0),
                    total_tokens=result.get("total_tokens", 0),
                    total_input_cost=result.get("total_input_cost", 0.0),
                    total_cached_cost=result.get("total_cached_cost", 0.0),
                    total_output_cost=result.get("total_output_cost", 0.0),
                    total_cost=result.get("total_cost", 0.0)
                )
                
                if success:
                    print(f"✅ Updated benchmark run {run_id} with final totals")
                else:
                    print(f"❌ Failed to update benchmark run {run_id} with final totals")
                    
            except Exception as e:
                print(f"❌ Error updating benchmark run totals: {str(e)}")
                
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
    
    if len(sys.argv) < 5:
        print(f"ERROR: Usage: python {sys.argv[0]} <job_id> <benchmark_id> <prompts_file> <model_name> [web_search_enabled]")
        sys.exit(1)
    
    try:
        job_id = int(sys.argv[1])
        benchmark_id = int(sys.argv[2])
        prompts_file = sys.argv[3]
        model_name = sys.argv[4]
        
        # Check for web search parameter
        web_search_enabled = False
        if len(sys.argv) > 5:
            web_search_enabled = sys.argv[5].lower() == 'true'
        
        # Load prompts list
        with open(prompts_file, 'r') as f:
            prompts = json.load(f)
        
        # Run the database-based benchmark
        run_direct_benchmark_from_db(job_id, benchmark_id, prompts, model_name, web_search_enabled)
        
    except Exception as e:
        print(f"ERROR: Invalid arguments: {e}")
        sys.exit(1)