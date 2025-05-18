#!/usr/bin/env python3
"""
Bridge script to run benchmarks from the Electron UI.
Takes prompts, PDF path, and model names as arguments and runs the benchmark.
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from pathlib import Path

from file_store import (
    save_benchmark, 
    save_benchmark_run, 
    save_benchmark_prompt,
    add_benchmark_file,
    get_openai_file_id,
    add_file_mapping
)
from models_openai import openai_upload, openai_ask, AVAILABLE_MODELS

# Set up logging using Python's logging module
import logging

# Create logs directory if it doesn't exist
LOGS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
LOG_FILE = LOGS_DIR / 'run_benchmark.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Also maintain the original log_to_file function for backward compatibility
def log_to_file(message):
    """Write debug message to log file and also log using Python's logging module"""
    logging.info(message)
    # Also keep a direct file write for immediate flushing
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

# Clear log file on start
with open(LOG_FILE, 'w') as f:
    f.write(f"{datetime.now()}: Starting benchmark creation\n")
logging.info("Starting benchmark creation")

def run_benchmark(pdf_path, models, prompts):
    """
    Create a new benchmark run in the database and run the provided prompts against
    the selected OpenAI models using the PDF as context.
    
    Args:
        pdf_path (str): Path to the PDF file to use as context
        models (list): List of model names to run the benchmark with
        prompts (list): List of prompt dictionaries with at least 'prompt_text' key
        
    Returns:
        dict: Result of the benchmark run with details on scores, tokens, etc.
    """
    log_to_file(f"Starting benchmark run with PDF: {pdf_path}, Models: {models}, Prompts count: {len(prompts)}")
    
    if not os.path.exists(pdf_path):
        log_to_file(f"Error: PDF file not found: {pdf_path}")
        return {"error": f"PDF file not found: {pdf_path}"}
    
    # Validate all models are OpenAI models
    for model in models:
        if model not in AVAILABLE_MODELS:
            error_msg = f"Model {model} is not an available OpenAI model. Available models: {', '.join(AVAILABLE_MODELS)}"
            log_to_file(error_msg)
            return {"error": error_msg}
    
    # Validate prompts structure
    if not all(isinstance(p, dict) and 'prompt_text' in p for p in prompts):
        error_msg = "Invalid prompts structure. Each prompt must be a dictionary with at least 'prompt_text' key."
        log_to_file(error_msg)
        return {"error": error_msg}
    
    try:
        # Current working directory as Path object
        cwd = Path.cwd()
        log_to_file(f"Current working directory: {cwd}")
        
        # Create a timestamp for labeling
        now = datetime.now().isoformat()
        pdf_filename = os.path.basename(pdf_path)
        label = f"{pdf_filename} Benchmark - {now[:10]}"
        description = f"Benchmark created on {now} with {len(prompts)} prompts for {', '.join(models)} models."
        
        log_to_file(f"Creating benchmark with label: {label}")
        
        # Create a new benchmark using the file_store module
        benchmark_id = save_benchmark(
            label=label, 
            description=description, 
            file_paths=[pdf_path],
            db_path=cwd
        )
        
        log_to_file(f"Created benchmark with ID: {benchmark_id}")
        
        # Check if we already have the file uploaded to OpenAI
        pdf_path_obj = Path(pdf_path)
        openai_file_id = get_openai_file_id(pdf_path_obj, cwd)
        
        # If not already uploaded, upload it
        if not openai_file_id:
            log_to_file(f"Uploading PDF {pdf_path} to OpenAI...")
            openai_file_id = openai_upload(pdf_path_obj)
            log_to_file(f"PDF uploaded with file ID: {openai_file_id}")
            
            # Save the mapping for future use
            add_file_mapping(pdf_path_obj, openai_file_id, cwd)
        else:
            log_to_file(f"Using existing OpenAI file ID: {openai_file_id} for {pdf_path}")
        
        # Store model-specific benchmark runs
        run_ids = []
        for model_name in models:
            log_to_file(f"Processing model: {model_name}")
            
            # Initialize token counters
            total_standard_tokens = 0
            total_cached_tokens = 0
            total_output_tokens = 0
            
            # Start time for this model's run
            start_time = datetime.now()
            prompt_results = []
            
            # Run each prompt against the model
            for prompt in prompts:
                # Skip empty prompts
                prompt_text = prompt.get('prompt_text', '').strip()
                if not prompt_text:
                    continue
                    
                expected_answer = prompt.get('expected_answer', '')
                log_to_file(f"Running prompt: '{prompt_text[:50]}...' against model {model_name}")
                
                # Call the actual model API using our models_openai module
                prompt_start_time = time.time()
                try:
                    # Progress update - similar to app.py progress notification
                    # Use prompt index from the loop instead of undefined 'i'
                    prompt_index = prompts.index(prompt)
                    progress_info = {
                        "current": prompt_index + 1,
                        "total": len(prompts),
                        "message": f"Processing prompt {prompt_index+1}/{len(prompts)} with model {model_name}"
                    }
                    log_to_file(f"Progress: {progress_info['message']}")
                    
                    # Call OpenAI API with the prompt and PDF file ID
                    answer, std_tokens, cached_tokens, out_tokens = openai_ask(
                        file_id=openai_file_id,
                        prompt_text=prompt_text,
                        model_name=model_name
                    )
                    
                    prompt_end_time = time.time()
                    latency = prompt_end_time - prompt_start_time
                    
                        # Calculate score (0.0 to 1.0) based on content matching
                    # Enhanced scoring logic based on app.py implementation
                    if expected_answer and answer:
                        # Normalize text for comparison
                        expected_lower = expected_answer.lower().strip()
                        answer_lower = answer.lower().strip()
                        
                        # Exact match gets highest score
                        if expected_lower == answer_lower:
                            score = "1.0"
                        # If the expected answer is found in the response
                        elif expected_lower in answer_lower:
                            # Longer matches score higher than shorter ones
                            match_ratio = len(expected_lower) / max(len(answer_lower), 1)
                            # Score between 0.5 and 0.9 based on match length
                            score = str(min(0.9, max(0.5, 0.5 + match_ratio * 0.4)))
                        # If the response is found in the expected answer
                        elif answer_lower in expected_lower and len(answer_lower) > 5:  # Avoid tiny matches
                            match_ratio = len(answer_lower) / max(len(expected_lower), 1)
                            # Score between 0.3 and 0.7 based on match length
                            score = str(min(0.7, max(0.3, 0.3 + match_ratio * 0.4)))
                        # Word-level matching
                        else:
                            # Check for word overlap
                            expected_words = set(expected_lower.split())
                            answer_words = set(answer_lower.split())
                            if expected_words and answer_words:  # Avoid empty sets
                                common_words = expected_words.intersection(answer_words)
                                # Calculate overlap ratio
                                overlap_ratio = len(common_words) / max(len(expected_words), len(answer_words))
                                # Score between 0.0 and 0.4 based on word overlap
                                score = str(min(0.4, max(0.0, overlap_ratio * 0.4)))
                            else:
                                score = "0.0"
                    else:
                        score = "0.0"  # No expected answer or no answer
                    
                    # Store the prompt result
                    prompt_results.append({
                        "prompt": prompt_text,
                        "expected": expected_answer,
                        "answer": answer,
                        "score": score,
                        "latency": latency,
                        "standard_tokens": std_tokens,
                        "cached_tokens": cached_tokens,
                        "output_tokens": out_tokens
                    })
                    
                    # Accumulate tokens for the run totals
                    total_standard_tokens += std_tokens
                    total_cached_tokens += cached_tokens
                    total_output_tokens += out_tokens
                    
                    log_to_file(f"Completed prompt. Score: {score}, Latency: {latency:.2f}s")
                    
                except Exception as prompt_error:
                    error_msg = f"Error processing prompt with model {model_name}: {str(prompt_error)}"
                    log_to_file(error_msg)
                    
                    # Create a placeholder result for the failed prompt
                    prompt_results.append({
                        "prompt": prompt_text,
                        "expected": expected_answer,
                        "answer": f"ERROR: {str(prompt_error)}",
                        "score": "0.0",
                        "latency": 0.0,
                        "standard_tokens": 0,
                        "cached_tokens": 0,
                        "output_tokens": 0
                    })
            
                # Calculate total time and mean score
            end_time = datetime.now()
            elapsed_seconds = (end_time - start_time).total_seconds()
            
            # Calculate mean score
            if prompt_results:
                # Convert scores to float and ensure proper handling of any non-numeric scores
                scores = []
                for p in prompt_results:
                    try:
                        score_val = float(p["score"])
                        scores.append(score_val)
                    except (ValueError, TypeError):
                        # Handle case where score might not be numeric
                        log_to_file(f"Warning: Non-numeric score: {p['score']}")
                        # Use a default value
                        scores.append(0.0)
                
                # Calculate mean with proper error handling
                try:        
                    mean_score = sum(scores) / len(scores) if scores else 0.0
                except Exception as e:
                    log_to_file(f"Error calculating mean score: {e}")
                    mean_score = 0.0
            else:
                mean_score = 0.0
                
            # Final progress update for this model
            log_to_file(f"Completed all prompts for model {model_name}. Mean score: {mean_score:.2f}")
            
            # Create a detailed JSON report similar to the one in app.py
            report = json.dumps({
                "elapsed_seconds": elapsed_seconds,
                "prompt_count": len(prompt_results),
                "model": model_name,
                "mean_score": mean_score,
                "token_breakdown": {
                    "standard_input": total_standard_tokens,
                    "cached_input": total_cached_tokens,
                    "output": total_output_tokens,
                    "total": total_standard_tokens + total_cached_tokens + total_output_tokens
                }
            })
            
            # Calculate total tokens
            total_tokens = total_standard_tokens + total_cached_tokens + total_output_tokens
            
            # Save the benchmark run
            run_id = save_benchmark_run(
                benchmark_id=benchmark_id,
                model_name=model_name,
                report=report,
                latency=elapsed_seconds,
                total_standard_input_tokens=total_standard_tokens,
                total_cached_input_tokens=total_cached_tokens,
                total_output_tokens=total_output_tokens,
                total_tokens=total_tokens,
                db_path=cwd
            )
            
            log_to_file(f"Created benchmark run with ID: {run_id} for model: {model_name}")
            run_ids.append(run_id)
            
            # Save individual prompt results
            for prompt_result in prompt_results:
                save_benchmark_prompt(
                    benchmark_run_id=run_id,
                    prompt=prompt_result["prompt"],
                    answer=prompt_result["expected"],
                    response=prompt_result["answer"],
                    score=prompt_result["score"],
                    latency=prompt_result["latency"],
                    standard_input_tokens=prompt_result["standard_tokens"],
                    cached_input_tokens=prompt_result["cached_tokens"],
                    output_tokens=prompt_result["output_tokens"],
                    db_path=cwd
                )
                
                log_to_file(f"Saved prompt result for run ID: {run_id}")
        
        # Create detailed response with benchmark data similar to app.py result structure
        return {
            "status": "success",
            "benchmark_id": benchmark_id,
            "run_ids": run_ids,
            "message": f"Benchmark created with {len(prompts)} prompts for {len(models)} models",
            "label": label,
            "description": description,
            "pdf_path": pdf_path,
            "models": models,
            "prompt_count": len(prompts),
            # Fix the mean_scores calculation to use the actual mean_score calculated for this model
            "mean_scores": {model_name: mean_score},
            "elapsed_seconds": elapsed_seconds,
            "token_info": {
                "total_standard_input_tokens": total_standard_tokens,
                "total_cached_input_tokens": total_cached_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_standard_tokens + total_cached_tokens + total_output_tokens
            }
        }
        
    except Exception as e:
        error_msg = f"Error running benchmark: {str(e)}"
        log_to_file(error_msg)
        print(error_msg, file=sys.stderr)
        return {"error": error_msg}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a benchmark from Electron UI")
    parser.add_argument('--pdf', required=True, help="Path to PDF file")
    parser.add_argument('--models', required=True, help="Comma-separated list of model names")
    parser.add_argument('--prompts', required=True, help="JSON string containing prompts data")
    
    args = parser.parse_args()
    
    log_to_file(f"Command line arguments: PDF={args.pdf}, Models={args.models}, Prompts size={len(args.prompts)}")
    
    models = args.models.split(',')
    try:
        prompts = json.loads(args.prompts)
        log_to_file(f"Successfully parsed prompts JSON with {len(prompts)} prompts")
    except json.JSONDecodeError as e:
        error_msg = f"Error: Invalid JSON format for prompts: {str(e)}"
        log_to_file(error_msg)
        print(error_msg)
        sys.exit(1)
    
    result = run_benchmark(args.pdf, models, prompts)
    log_to_file(f"Benchmark run completed with result: {json.dumps(result)}")
    print(json.dumps(result))
