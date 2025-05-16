#!/usr/bin/env python3
"""
Bridge script to get detailed benchmark information for the Electron UI.
Returns detailed benchmark data in JSON format for a specific benchmark run.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Import file_store module for database functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.file_store import load_benchmark_details

# Set up logging to a file
log_file = Path(__file__).parent / 'logs' / 'get_benchmark_details.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(filename=log_file, level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Script directory for database path
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# Define token cost constants for different models
# These are approximate costs per 1000 tokens (in USD)
MODEL_COSTS = {
    # Standard OpenAI models
    'gpt-4o': {'input': 0.005, 'output': 0.015},
    'gpt-4o-mini': {'input': 0.0015, 'output': 0.0060},
    'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
    'gpt-4': {'input': 0.03, 'output': 0.06},
    'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
    
    # Default cost for unknown models
    'default': {'input': 0.01, 'output': 0.03}
}

def calculate_cost(model_name, standard_input_tokens, cached_input_tokens, output_tokens):
    """
    Calculate the estimated cost of a benchmark run based on token usage.
    
    Args:
        model_name (str): The name of the model used
        standard_input_tokens (int): Number of standard input tokens used
        cached_input_tokens (int): Number of cached input tokens used
        output_tokens (int): Number of output tokens generated
        
    Returns:
        float: Estimated cost in USD
    """
    # Get cost rates for the model, or use default if not found
    model_rates = MODEL_COSTS.get(model_name, MODEL_COSTS['default'])
    
    # Calculate costs (converting from tokens to thousands of tokens)
    standard_input_cost = (standard_input_tokens / 1000) * model_rates['input']
    
    # Cached tokens are typically charged at a reduced rate or not at all
    # Here we're using a 50% discount for cached tokens as an example
    cached_input_cost = (cached_input_tokens / 1000) * (model_rates['input'] * 0.5)
    
    output_cost = (output_tokens / 1000) * model_rates['output']
    
    # Total cost
    total_cost = standard_input_cost + cached_input_cost + output_cost
    
    return round(total_cost, 6)  # Round to 6 decimal places

def get_benchmark_details(benchmark_id):
    """Fetch detailed data for a specific benchmark using file_store functions"""
    logging.info(f"Fetching details for benchmark ID: {benchmark_id}")
    
    try:
        # Use the file_store function to get detailed benchmark information
        benchmark_details = load_benchmark_details(benchmark_id, SCRIPT_DIR)
        
        if not benchmark_details:
            logging.error(f"No benchmark found with ID {benchmark_id}")
            return {"error": f"Benchmark ID {benchmark_id} not found", "status": "error"}
        
        logging.info(f"Successfully loaded benchmark details for ID: {benchmark_id}")
        
        # Format the data to match the expected structure for the UI
        # The file_store function already provides most of what we need, but we'll add some additional processing
        
        # Extract and format timestamp
        timestamp = benchmark_details.get('timestamp')
        formatted_timestamp = timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logging.warning(f"Failed to parse timestamp {timestamp}: {e}")
        
        # Extract run information including token counts
        run_id = benchmark_details.get('run_id')
        model_name = benchmark_details.get('model_name')
        latency = benchmark_details.get('latency')
        std_tokens = benchmark_details.get('total_standard_input_tokens', 0) or 0
        cached_tokens = benchmark_details.get('total_cached_input_tokens', 0) or 0
        output_tokens = benchmark_details.get('total_output_tokens', 0) or 0
        total_tokens = std_tokens + cached_tokens + output_tokens
        
        # Extract models (should be provided by load_benchmark_details)
        models = benchmark_details.get('model_names', [])
        if model_name and model_name not in models:
            models.append(model_name)
        
        # Get mean score from the detailed benchmark data
        mean_score = benchmark_details.get('mean_score')
        total_items = benchmark_details.get('total_items', 0)
        
        # Process prompt data which should be included in benchmark_details
        prompts_data = benchmark_details.get('prompts', [])
        prompts = []
        total_cost = 0
        model_scores = {}
        
        for prompt in prompts_data:
            # Calculate total tokens per prompt
            prompt_std_tokens = prompt.get('standard_input_tokens', 0) or 0
            prompt_cached_tokens = prompt.get('cached_input_tokens', 0) or 0
            prompt_output_tokens = prompt.get('output_tokens', 0) or 0
            prompt_total_input_tokens = prompt_std_tokens + prompt_cached_tokens
            prompt_total_tokens = prompt_total_input_tokens + prompt_output_tokens
            
            # Get the model name and score for this prompt
            prompt_model = prompt.get('model_name', model_name)
            prompt_score = prompt.get('score')
            if prompt_score is not None and prompt_model not in model_scores:
                model_scores[prompt_model] = []
            if prompt_score is not None:
                model_scores[prompt_model].append(float(prompt_score))
            
            # Calculate estimated cost for this prompt
            prompt_cost = 0
            # We could implement a cost calculation here if needed
            # Or in a real application, we might already have the cost stored with the prompt
            
            # Format prompt data for the UI
            prompt_data = {
                "id": prompt.get('id'),
                "prompt_text": prompt.get('prompt', ''),
                "expected_answer": prompt.get('answer', ''),
                "actual_answer": prompt.get('response', ''),
                "score": prompt_score,
                "score_percentage": f"{float(prompt_score) * 100:.1f}%" if prompt_score is not None else "N/A",
                "standard_input_tokens": prompt_std_tokens,
                "cached_input_tokens": prompt_cached_tokens,
                "total_input_tokens": prompt_total_input_tokens,
                "output_tokens": prompt_output_tokens,
                "total_tokens": prompt_total_tokens,
                "model_name": prompt_model,
                "latency_ms": prompt.get('latency', 0) or 0,
                "estimated_cost": prompt_cost
            }
            prompts.append(prompt_data)
        
        # Calculate average score by model
        calculated_model_scores = {}
        for model, scores in model_scores.items():
            if scores:
                calculated_model_scores[model] = sum(scores) / len(scores)
            else:
                calculated_model_scores[model] = 0
        
        # Format final benchmark details object
        formatted_details = {
            "id": benchmark_details.get('id'),
            "timestamp": formatted_timestamp,
            "status": "completed",
            "label": benchmark_details.get('label') or f"Benchmark {benchmark_details.get('id')}",
            "description": benchmark_details.get('description'),
            "models": models,
            "model_scores": calculated_model_scores,
            "mean_score": mean_score,
            "mean_score_percentage": f"{mean_score * 100:.1f}%" if mean_score is not None else "N/A",
            "total_items": total_items,
            "elapsed_seconds": latency,
            "total_standard_input_tokens": std_tokens,
            "total_cached_input_tokens": cached_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "prompts_data": prompts,
            "created_at": formatted_timestamp,
            "file_paths": benchmark_details.get('file_paths', [])
        }
        return formatted_details
        
    except Exception as e:
        error_msg = f"Error retrieving benchmark details: {e}"
        logging.error(error_msg, exc_info=True)
        print(error_msg, file=sys.stderr)
        return {"error": str(e), "status": "error"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_benchmark_details.py <benchmark_id>")
        sys.exit(1)
    
    try:
        benchmark_id = int(sys.argv[1])
    except ValueError:
        print("Error: benchmark_id must be an integer")
        sys.exit(1)
    
    try:
        details = get_benchmark_details(benchmark_id)
        print(json.dumps(details))
    except Exception as e:
        error_response = {"error": str(e), "status": "error"}
        logging.error(f"Unhandled error: {e}", exc_info=True)
        print(json.dumps(error_response))
