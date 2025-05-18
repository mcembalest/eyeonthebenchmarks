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
from typing import Dict, Any, List, Optional, Union

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from file_store import load_benchmark_details
from cost_calculator import calculate_cost

# Set up logging to both file and stderr
log_file = Path(__file__).parent / 'logs' / 'get_benchmark_details.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.ERROR)  # Only show errors on stderr

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Remove any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Script directory for database path
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


def calculate_benchmark_cost(benchmark_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate the cost of a benchmark run based on the benchmark data.
    
    Args:
        benchmark_data: Dictionary containing benchmark run details
        
    Returns:
        Dictionary with cost breakdown
    """
    if not benchmark_data:
        return {'error': 'No benchmark data provided'}
    
    try:
        # Extract model name and token counts from benchmark data
        model_name = benchmark_data.get('model_name')
        if not model_name:
            return {'error': 'No model name in benchmark data'}
            
        # Get token counts (handle None values)
        standard_input_tokens = benchmark_data.get('total_standard_input_tokens', 0) or 0
        cached_input_tokens = benchmark_data.get('total_cached_input_tokens', 0) or 0
        output_tokens = benchmark_data.get('total_output_tokens', 0) or 0
        
        # Get search queries if any
        search_queries = benchmark_data.get('search_queries', 0) or 0
        search_context = benchmark_data.get('search_context', 'medium')
        
        # Get image generation details if any
        image_generation = None
        if 'image_generation' in benchmark_data and benchmark_data['image_generation']:
            image_generation = benchmark_data['image_generation']
        
        # Calculate costs using the centralized cost calculator
        cost_breakdown = calculate_cost(
            model_name=model_name,
            standard_input_tokens=standard_input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            search_queries=search_queries,
            search_context=search_context,
            image_generation=image_generation
        )
        
        return cost_breakdown
        
    except Exception as e:
        logger.error(f"Error calculating benchmark cost: {e}", exc_info=True)
        return {'error': str(e)}


def format_prompt_data(prompt: Dict[str, Any], default_model: str) -> Dict[str, Any]:
    """Format a single prompt's data for the response."""
    prompt_std_tokens = prompt.get('standard_input_tokens', 0) or 0
    prompt_cached_tokens = prompt.get('cached_input_tokens', 0) or 0
    prompt_output_tokens = prompt.get('output_tokens', 0) or 0
    prompt_total_input_tokens = prompt_std_tokens + prompt_cached_tokens
    prompt_total_tokens = prompt_total_input_tokens + prompt_output_tokens
    prompt_model = prompt.get('model_name', default_model)
    prompt_score = prompt.get('score')
    prompt_cost = float(prompt.get('cost', 0)) if prompt.get('cost') is not None else 0
    
    return {
        "id": prompt.get('id'),
        "prompt": prompt.get('prompt_text', ''),
        "model": prompt_model,
        "response": prompt.get('response', ''),
        "score": prompt_score,
        "standard_input_tokens": prompt_std_tokens,
        "cached_input_tokens": prompt_cached_tokens,
        "output_tokens": prompt_output_tokens,
        "total_tokens": prompt_total_tokens,
        "cost": prompt_cost,
        "latency": prompt.get('latency')
    }


def calculate_model_scores(prompts: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate average scores for each model from the prompts."""
    model_scores = {}
    
    for prompt in prompts:
        if 'model_name' in prompt and 'score' in prompt and prompt['score'] is not None:
            model = prompt['model_name']
            score = prompt['score']
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(score)
    
    # Calculate average score for each model
    return {
        model: sum(scores) / len(scores)
        for model, scores in model_scores.items()
        if scores  # Only include models with at least one score
    }


def get_benchmark_details(benchmark_id: Union[str, int]) -> Dict[str, Any]:
    """
    Fetch detailed data for a specific benchmark using file_store functions
    
    Args:
        benchmark_id: The ID of the benchmark to fetch (can be string or int)
        
    Returns:
        Dictionary with benchmark details and cost breakdown
    """
    logger.info(f"Fetching details for benchmark ID: {benchmark_id}")
    
    try:
        # Convert benchmark_id to string if it's an integer
        if isinstance(benchmark_id, int):
            benchmark_id = str(benchmark_id)
            
        # Use the file_store function to get detailed benchmark information
        benchmark_details = load_benchmark_details(benchmark_id, SCRIPT_DIR)
        
        if not benchmark_details:
            return {"error": "Benchmark not found", "status": "not_found"}

        # Extract model name and timestamp for response
        model_name = benchmark_details.get('model_name', 'unknown')
        timestamp = benchmark_details.get('timestamp')
        
        # Format timestamp if available
        formatted_timestamp = timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {timestamp}: {e}")
        
        # Process prompts if available
        prompts_data = benchmark_details.get('prompts', [])
        formatted_prompts = [
            format_prompt_data(prompt, model_name)
            for prompt in prompts_data
        ]
        
        # Calculate model scores
        model_scores = calculate_model_scores(prompts_data)
        
        # Calculate mean score if we have scores
        scores = [p['score'] for p in formatted_prompts if p.get('score') is not None]
        mean_score = sum(scores) / len(scores) if scores else None
        
        # Calculate token totals
        total_std_tokens = sum(p['standard_input_tokens'] for p in formatted_prompts)
        total_cached_tokens = sum(p['cached_input_tokens'] for p in formatted_prompts)
        total_output_tokens = sum(p['output_tokens'] for p in formatted_prompts)
        total_tokens = total_std_tokens + total_cached_tokens + total_output_tokens
        
        # Calculate total cost
        total_cost = sum(p['cost'] for p in formatted_prompts if p.get('cost') is not None)
        
        # Get latency if available
        latency = benchmark_details.get('latency')
        
        # Get file paths if available
        file_paths = benchmark_details.get('file_paths', [])
        
        # Determine the actual status based on data
        status = benchmark_details.get('status')
        if status is None:
            # If no explicit status, determine based on data
            if len(formatted_prompts) > 0 and mean_score is not None:
                status = 'completed'
            elif 'run_id' in benchmark_details:
                status = 'running'  # Has a run, but no results yet
            else:
                status = 'pending'  # No run started yet
        
        # Format the response
        formatted_details = {
            "id": benchmark_id,
            "timestamp": formatted_timestamp,
            "status": status,
            "model": model_name,
            "models": list(model_scores.keys()) or [model_name],
            "model_scores": model_scores,
            "mean_score": mean_score,
            "mean_score_percentage": f"{mean_score * 100:.1f}%" if mean_score is not None else "N/A",
            "total_items": len(formatted_prompts),
            "elapsed_seconds": latency,
            "total_standard_input_tokens": total_std_tokens,
            "total_cached_input_tokens": total_cached_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "prompts": formatted_prompts,
            "metrics": benchmark_details.get('metrics', {}),
            "file_paths": file_paths,
            "label": benchmark_details.get('label', f"Benchmark {benchmark_id}"),
            "description": benchmark_details.get('description', '')
        }
        
        # Add cost breakdown
        cost_breakdown = calculate_benchmark_cost({
            'model_name': model_name,
            'total_standard_input_tokens': total_std_tokens,
            'total_cached_input_tokens': total_cached_tokens,
            'total_output_tokens': total_output_tokens,
            'search_queries': benchmark_details.get('search_queries', 0),
            'search_context': benchmark_details.get('search_context', 'medium'),
            'image_generation': benchmark_details.get('image_generation')
        })
        
        if 'error' not in cost_breakdown:
            formatted_details['cost_breakdown'] = cost_breakdown
        else:
            logger.warning(f"Could not calculate cost breakdown: {cost_breakdown.get('error')}")
        
        return formatted_details

    except Exception as e:
        error_msg = f"Error retrieving benchmark details: {e}"
        logger.error(error_msg, exc_info=True)
        return {"error": str(e), "status": "error"}


def main():
    if len(sys.argv) < 2:
        error_msg = "Missing benchmark_id"
        logger.error(error_msg)
        print(json.dumps({"error": error_msg, "status": "error"}), file=sys.stderr)
        print("Usage: python get_benchmark_details.py <benchmark_id>", file=sys.stderr)
        return 1
    
    try:
        # Parse benchmark_id as int if possible, otherwise keep as string
        try:
            benchmark_id = int(sys.argv[1])
        except ValueError:
            benchmark_id = sys.argv[1]
        
        logger.info(f"Fetching details for benchmark ID: {benchmark_id}")
        details = get_benchmark_details(benchmark_id)
        
        if details is None:
            error_msg = f"Benchmark with ID {benchmark_id} not found"
            logger.error(error_msg)
            print(json.dumps({"error": error_msg, "status": "not_found"}), file=sys.stderr)
            return 1
            
        # Ensure we have a clean JSON output
        try:
            json_output = json.dumps(details)
            print(json_output)
            return 0
        except (TypeError, ValueError) as e:
            error_msg = f"Error encoding data to JSON: {e}"
            logger.error(error_msg, exc_info=True)
            print(json.dumps({"error": error_msg, "status": "error"}), file=sys.stderr)
            return 1
            
    except Exception as e:
        error_msg = f"Unhandled error: {e}"
        logger.error(error_msg, exc_info=True)
        print(json.dumps({"error": error_msg, "status": "error"}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
