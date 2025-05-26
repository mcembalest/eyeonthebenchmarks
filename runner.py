from pathlib import Path
from time import perf_counter
import time
import PyPDF2 # For PDF text extraction
import os # For os.path.getsize
import logging
from typing import List, Dict, Any, Optional

# Import model functions
from models_openai import openai_ask_with_files
from models_google import google_ask_with_files
from models_anthropic import anthropic_ask_with_files

# Import file store functions
from file_store import get_benchmark_files

# Import cost calculation functions
from models_openai import calculate_cost as openai_calculate_cost
from models_google import calculate_cost as google_calculate_cost
from models_anthropic import calculate_cost as anthropic_calculate_cost

def extract_text_and_page_count(pdf_path: Path) -> tuple[str, int]:
    """Extract text and page count from a PDF file."""
    try:
        text = ""
        page_count = 0
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            page_count = len(reader.pages)
            for page_num in range(page_count):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
        if not text.strip() and page_count > 0:
            emit_progress({"message": f"Warning: No text extracted from {pdf_path}. The PDF might be image-based or empty."})
        emit_progress({"message": f"Successfully extracted text from {pdf_path}. Length: {len(text)}, Pages: {page_count}"})
        return text, page_count
    except Exception as e:
        emit_progress({"message": f"Error extracting text or page count from {pdf_path}: {e}"})
        raise

# simple_score function removed as scoring is out of MVP scope

_emit_progress_callback = None

def set_emit_progress_callback(callback):
    global _emit_progress_callback
    _emit_progress_callback = callback

def emit_progress(data: dict):
    """
    Passes structured progress data to the registered callback.
    Data is a dictionary, e.g.:
    {'message': str} or {'current': int, 'total': int, 'message': str}
    """
    try:
        # Only log the message, not the full data structure
        message = data.get('message', '')
        if message:
            logging.info(f"Progress: {message}")
        
        if _emit_progress_callback:
            _emit_progress_callback(data)
        else:
            # Fallback to print if no callback is set
            print(data.get('message', str(data)))
    except Exception as e:
        error_msg = f"Error during progress reporting: {e}"
        logging.error(error_msg)
        print(error_msg)

def run_benchmark_with_files(prompts: List[Dict], file_paths: List[Path], model_name: str = "gpt-4o-mini", 
                         db_path: Path = Path.cwd(), on_prompt_complete=None, 
                         web_search_enabled: bool = False) -> Dict[str, Any]:
    """
    Run a benchmark with prompts (questions only) against multiple files using the specified model.
    
    Args:
        prompts: List of prompt dictionaries, each with 'prompt_text' (the question) and optional 'web_search' (bool).
        file_paths: List of paths to files to include in the benchmark.
        model_name: Name of the model to use.
        db_path: Path to the database directory.
        on_prompt_complete: Optional callback function called after each prompt completes.
                           Called with (prompt_index, prompt_result_dict)
        web_search_enabled: Whether to enable web search for this benchmark (global setting).
        
    Returns:
        Dictionary with benchmark results (responses, latency, token counts).
    """
    t0 = perf_counter()
    total_prompts = len(prompts) if prompts else 0
    
    emit_progress({"message": f"Starting benchmark with {len(file_paths)} files and {total_prompts} prompts"})
    if web_search_enabled:
        emit_progress({"message": "Web search is enabled for this benchmark"})
    
    # Validate files
    for file_path in file_paths:
        if not file_path.exists():
            emit_progress({"message": f"Error: File not found at {file_path}"})
            return {
                "items": 0,
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name,
                "error": f"File not found: {file_path}"
            }
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 32:
            emit_progress({"message": f"Error: File {file_path.name} size ({file_size_mb:.2f}MB) exceeds 32MB limit."})
            return {
                "items": 0, 
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name, 
                "error": f"File too large: {file_path.name} (size > 32MB)"
            }

    # Determine provider based on model name
    if model_name.startswith("gemini-") or model_name == "imagen-3":
        provider = "google"
    elif model_name.startswith("claude-"):
        provider = "anthropic"
    else:
        provider = "openai"
    
    emit_progress({"message": f"Using {provider} provider for model: {model_name}"})

    # Run prompts
    try:
        individual_prompt_data = []
        total_standard_input_tokens_run = 0
        total_cached_input_tokens_run = 0
        total_output_tokens_run = 0
        total_cost_run = 0.0

        if not prompts:
            emit_progress({"message": "Warning: No prompts provided for benchmark."})
            return {
                "items": 0,
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name,
                "error": "No prompts provided"
            }

        for i, prompt_item in enumerate(prompts):
            prompt_text = prompt_item.get("prompt_text", "") # Ensure we get a string
            
            # Determine if web search should be used for this prompt
            prompt_web_search = prompt_item.get("web_search", True) # Default to True if not specified
            use_web_search = web_search_enabled and prompt_web_search
            
            if not prompt_text:
                emit_progress({"current": i + 1, "total": total_prompts, "message": "Skipping empty prompt.", "is_warning": True})
                individual_prompt_data.append({
                    "prompt_text": "EMPTY_PROMPT_SKIPPED",
                    "prompt_length_chars": 0,
                    "latency_ms": 0,
                    "standard_input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "model_answer": "ERROR: Empty prompt provided",
                    "input_cost": 0.0,
                    "cached_cost": 0.0,
                    "output_cost": 0.0,
                    "total_cost": 0.0,
                    "web_search_used": False,
                    "web_search_sources": ""
                })
                continue # Skip to next prompt
                
            prompt_length_chars = len(prompt_text)
            
            try:
                progress_message = f"Asking: {prompt_text[:50]}..."
                if use_web_search:
                    progress_message += " (with web search)"
                emit_progress({"current": i + 1, "total": total_prompts, "message": progress_message})
                
                prompt_t0 = perf_counter()
                
                if provider == "google":
                    ans, standard_input_tokens_val, cached_input_tokens_val, output_tokens_val, actual_web_search_used, web_search_sources = google_ask_with_files(
                        file_paths, prompt_text, model_name, db_path, use_web_search
                    )
                elif provider == "anthropic":
                    ans, standard_input_tokens_val, cached_input_tokens_val, output_tokens_val, actual_web_search_used, web_search_sources = anthropic_ask_with_files(
                        file_paths, prompt_text, model_name, db_path, use_web_search
                    )
                else:  # openai
                    ans, standard_input_tokens_val, cached_input_tokens_val, output_tokens_val, actual_web_search_used, web_search_sources = openai_ask_with_files(
                        file_paths, prompt_text, model_name, db_path, use_web_search
                    )
                
                prompt_t1 = perf_counter()
                individual_latency_ms = round((prompt_t1 - prompt_t0) * 1000)

                # Calculate cost for this prompt
                cost_info = {"error": "Unknown provider"}
                if provider == "openai":
                    cost_info = openai_calculate_cost(
                        model_name=model_name,
                        standard_input_tokens=standard_input_tokens_val,
                        cached_input_tokens=cached_input_tokens_val,
                        output_tokens=output_tokens_val
                    )
                elif provider == "google":
                    cost_info = google_calculate_cost(
                        model_name=model_name,
                        standard_input_tokens=standard_input_tokens_val,
                        cached_input_tokens=cached_input_tokens_val,
                        output_tokens=output_tokens_val
                    )
                elif provider == "anthropic":
                    cost_info = anthropic_calculate_cost(
                        model_name=model_name,
                        standard_input_tokens=standard_input_tokens_val,
                        cache_write_tokens=0,  # TODO: Extract from response if available
                        cache_read_tokens=cached_input_tokens_val,
                        output_tokens=output_tokens_val
                    )

                # Extract cost information
                input_cost = cost_info.get("input_cost", 0.0)
                cached_cost = cost_info.get("cached_cost", 0.0) or cost_info.get("cache_read_cost", 0.0)
                output_cost = cost_info.get("output_cost", 0.0)
                prompt_total_cost = cost_info.get("total_cost", 0.0)

                total_standard_input_tokens_run += standard_input_tokens_val
                total_cached_input_tokens_run += cached_input_tokens_val
                total_output_tokens_run += output_tokens_val
                total_cost_run += prompt_total_cost
                
                individual_prompt_data.append({
                    "prompt_text": prompt_text,
                    "prompt_length_chars": prompt_length_chars,
                    "latency_ms": individual_latency_ms,
                    "standard_input_tokens": standard_input_tokens_val,
                    "cached_input_tokens": cached_input_tokens_val,
                    "output_tokens": output_tokens_val,
                    "model_answer": ans,
                    "input_cost": input_cost,
                    "cached_cost": cached_cost,
                    "output_cost": output_cost,
                    "total_cost": prompt_total_cost,
                    "web_search_used": actual_web_search_used,
                    "web_search_sources": web_search_sources
                })
                
                ans_trunc = ans[:100] + "..." if len(ans) > 100 else ans
                cost_msg = f" (Cost: ${prompt_total_cost:.6f})" if prompt_total_cost > 0 else ""
                emit_progress({"current": i + 1, "total": total_prompts, "message": f"Answer: {ans_trunc}{cost_msg}"})
                
                if on_prompt_complete:
                    on_prompt_complete(i, {
                        "prompt_text": prompt_text,
                        "prompt_length_chars": prompt_length_chars,
                        "latency_ms": individual_latency_ms,
                        "standard_input_tokens": standard_input_tokens_val,
                        "cached_input_tokens": cached_input_tokens_val,
                        "output_tokens": output_tokens_val,
                        "model_answer": ans,
                        "input_cost": input_cost,
                        "cached_cost": cached_cost,
                        "output_cost": output_cost,
                        "total_cost": prompt_total_cost,
                        "web_search_used": actual_web_search_used,
                        "web_search_sources": web_search_sources
                    })
                
            except Exception as e:
                error_msg = f"Error processing prompt '{prompt_text[:30]}...': {e}"
                emit_progress({"current": i + 1, "total": total_prompts, "message": error_msg, "is_error": True})
                
                # Check if this was a web search related error
                error_str = str(e).lower()
                web_search_error = "web_search" in error_str or "web search" in error_str or "tool" in error_str
                
                if web_search_error and use_web_search:
                    emit_progress({"current": i + 1, "total": total_prompts, "message": f"Web search failed for this prompt. Error: {str(e)}", "is_warning": True})
                
                individual_prompt_data.append({
                    "prompt_text": prompt_text,
                    "prompt_length_chars": prompt_length_chars,
                    "latency_ms": 0,
                    "standard_input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "model_answer": f"ERROR: {str(e)}",
                    "input_cost": 0.0,
                    "cached_cost": 0.0,
                    "output_cost": 0.0,
                    "total_cost": 0.0,
                    "web_search_used": False,  # Always False on error
                    "web_search_sources": ""
                })

        # Summarize results
        elapsed = round(perf_counter() - t0, 2)
        total_tokens_run = total_standard_input_tokens_run + total_cached_input_tokens_run + total_output_tokens_run
        
        emit_progress({"message": f"Benchmark complete! Time: {elapsed}s, Total Tokens: {total_tokens_run}, Total Cost: ${total_cost_run:.6f}"})

        # Prepare prompts_data for database (now includes cost info)
        result_prompts_data = [
            {
                "prompt": ipd["prompt_text"],
                "response": ipd["model_answer"],
                "latency": ipd["latency_ms"],
                "standard_input_tokens": ipd["standard_input_tokens"],
                "cached_input_tokens": ipd["cached_input_tokens"],
                "output_tokens": ipd["output_tokens"],
                "input_cost": ipd["input_cost"],
                "cached_cost": ipd["cached_cost"],
                "output_cost": ipd["output_cost"],
                "total_cost": ipd["total_cost"],
                "web_search_used": ipd["web_search_used"],
                "web_search_sources": ipd["web_search_sources"]
            } for ipd in individual_prompt_data
        ]

        return {
            "items": len(individual_prompt_data), # Number of prompts processed
            "elapsed_s": elapsed,
            "model_name": model_name,
            "provider": provider,
            "prompts_data": result_prompts_data, 
            "file_paths": [str(fp) for fp in file_paths],
            "total_standard_input_tokens": total_standard_input_tokens_run,
            "total_cached_input_tokens": total_cached_input_tokens_run,
            "total_output_tokens": total_output_tokens_run,
            "total_tokens": total_tokens_run,
            "total_cost": total_cost_run
            # "mean_score" removed as scoring is out of scope
        }
        
    except Exception as e:
        emit_progress({"message": f"Error during benchmark execution: {e}"})
        return {
            "items": total_prompts,
            "elapsed_s": round(perf_counter() - t0, 2),
            "model_name": model_name,
            "provider": provider,
            "error": f"Benchmark execution failed: {e}",
            "file_paths": [str(fp) for fp in file_paths]
            # "mean_score" removed
        }

def run_benchmark_from_db(prompts: List[Dict], benchmark_id: int, model_name: str = "gpt-4o-mini", 
                       db_path: Path = Path.cwd(), on_prompt_complete=None,
                       web_search_enabled: bool = False) -> Dict[str, Any]:
    """
    Run a benchmark using files from the database (questions only).
    
    Args:
        prompts: List of prompt dictionaries, each with 'prompt_text' and optional 'web_search' (bool).
        benchmark_id: ID of the benchmark in the database.
        model_name: Name of the model to use.
        db_path: Path to the database directory.
        on_prompt_complete: Optional callback function called after each prompt completes.
        web_search_enabled: Whether to enable web search for this benchmark (global setting).
        
    Returns:
        Dictionary with benchmark results.
    """
    # Get files associated with this benchmark
    files_info = get_benchmark_files(benchmark_id, db_path)
    
    # Convert file info to paths
    db_file_paths = [Path(file_info['file_path']) for file_info in files_info]
    
    emit_progress({"message": f"Running benchmark {benchmark_id} with {len(db_file_paths)} files from DB"})
    if web_search_enabled:
        emit_progress({"message": "Web search is enabled for this benchmark"})
    
    return run_benchmark_with_files(prompts, db_file_paths, model_name, db_path, on_prompt_complete, web_search_enabled)
