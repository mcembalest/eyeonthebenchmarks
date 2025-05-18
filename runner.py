from pathlib import Path
from time import perf_counter
import time
import PyPDF2 # For PDF text extraction
import os # For os.path.getsize
import logging

# Import model functions
from models_openai import openai_upload, openai_ask
from models_google import google_upload, google_ask

# Import file store functions
from file_store import get_openai_file_id, add_file_mapping

# Placeholder helper functions (to be implemented or moved)
def extract_text_and_page_count(pdf_path: Path) -> tuple[str, int]:
    # print(f"Placeholder: Extracting text from {pdf_path}")
    # return "dummy text"
    try:
        text = ""
        page_count = 0
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            page_count = len(reader.pages)
            for page_num in range(page_count):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
        if not text.strip() and page_count > 0: # If pages exist but no text, it's likely image-based
            # Use the module-level emit_progress for structured data
            emit_progress({"message": f"Warning: No text extracted from {pdf_path}. The PDF might be image-based or empty."})
            # Return empty string for text, but correct page_count
        emit_progress({"message": f"Successfully extracted text from {pdf_path}. Length: {len(text)}, Pages: {page_count}"})
        return text, page_count
    except Exception as e:
        emit_progress({"message": f"Error extracting text or page count from {pdf_path}: {e}"})
        raise # Re-raise the exception to be caught by run_benchmark

def token_estimate(text: str) -> int:
    """
    Estimate the number of tokens in a text for OpenAI models.
    This is a more accurate approximation based on OpenAI's tokenizer behavior.
    
    Returns:
        Estimated token count
    """
    # More sophisticated token counting uses "tiktoken" library
    # but this is a reasonable approximation for now
    
    # Calculate basic length estimates
    num_words = len(text.split())
    num_chars = len(text)
    
    # OpenAI generally averages 4 chars per token for English text
    # but we'll be conservative
    estimated_tokens = max(
        num_words * 1.3,     # Words to tokens ratio
        num_chars // 3.5     # Chars to tokens ratio
    )
    
    return int(estimated_tokens)

def simple_score(answer: str, expected: str) -> int:
    """
    Score an answer against expected response.
    
    Returns:
        1 if match, 0 if not
    """
    if not answer or not expected:
        # Use the module-level emit_progress for structured data
        emit_progress({"message": f"Warning: Empty answer or expected value in scoring."})
        return 0
    
    # Clean and normalize both strings
    answer_clean = answer.lower().strip()
    expected_clean = expected.lower().strip()
    
    # Check for exact match first
    if answer_clean == expected_clean:
        return 1
    
    # Check if expected is contained in answer
    if expected_clean in answer_clean:
        return 1
    
    # More sophisticated match could be added here
    # For now, just return 0 if no match
    return 0

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
            # Call the progress callback without excessive logging
            _emit_progress_callback(data)
        else:
            # Fallback to print if no callback is set (e.g., for direct script use/testing)
            print(data.get('message', str(data)))
    except Exception as e:
        # Even if progress reporting fails, log it but don't crash the benchmark
        error_msg = f"Error during progress reporting: {e}"
        logging.error(error_msg)
        print(error_msg)  # Fallback to print for critical errors

def run_benchmark(prompts: list[dict], pdf_path: Path, model_name="gpt-4o-mini") -> dict:
    """
    Run a benchmark with prompts against a PDF using the specified model.
    
    Args:
        prompts: List of prompt dictionaries. Expected keys: 'prompt_text' and 'expected_answer'
                (will also accept 'prompt' and 'expected' for backwards compatibility)
        pdf_path: Path to the PDF file
        model_name: Name of the model to use 
        
    Returns:
        Dictionary with benchmark results
    """
    """
    prompts: [{"prompt": str, "expected": str}, ...]
    Returns: {"mean_score": float, "items": int, "elapsed_s": float, "model": str}
    """
    # Ensure pdf_path is a Path object in case a string was passed
    pdf_path = Path(pdf_path)
    t0 = perf_counter()
    total_prompts = len(prompts) if prompts else 0

    # 0. quick file/token/size/page guard (remains largely the same)
    try:
        if not pdf_path.exists(): # Check for file existence first
            # This specific error will be caught by the generic Exception handler below
            # if we simply raise FileNotFoundError here.
            # To give a specific error message like before:
            emit_progress({"message": f"Error: PDF file not found at {pdf_path}"})
            return {
                "items": 0,
                "mean_score": 0.0,
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name,
                "error": "PDF not found"
            }

        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        if file_size_mb > 32: # 32MB limit
            emit_progress({"message": f"Error: PDF file size ({file_size_mb:.2f}MB) exceeds 32MB limit."})
            return {
                "items": 0, "mean_score": 0.0, "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name, "error": "PDF too large (size > 32MB)"
            }

        # Use the modified extraction function
        text, page_count = extract_text_and_page_count(pdf_path)

        if page_count > 100: # 100 pages limit
            emit_progress({"message": f"Error: PDF page count ({page_count}) exceeds 100 pages limit."})
            return {
                "items": 0, "mean_score": 0.0, "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name, "error": "PDF too large (pages > 100)"
            }
        
        if token_estimate(text) > 100_000: # As per your spec
            emit_progress({"message": "Error: PDF estimated tokens exceed 100,000."})
            return {
                "items": 0,
                "mean_score": 0.0,
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name,
                "error": "PDF too large (tokens > 100k)"
            }
    except FileNotFoundError: # This is now redundant due to the check above, but kept for safety.
        emit_progress({"message": f"Error: PDF file not found at {pdf_path}"})
        return {
            "items": 0,
            "mean_score": 0.0,
            "elapsed_s": round(perf_counter() - t0, 2),
            "model": model_name,
            "error": "PDF not found"
        }
    except Exception as e: # Catch other extraction or pre-processing errors
        emit_progress({"message": f"Error during PDF pre-processing: {e}"})
        return {
            "items": 0,
            "mean_score": 0.0,
            "elapsed_s": round(perf_counter() - t0, 2),
            "model": model_name,
            "error": f"PDF processing failed: {e}"
        }

    # 1. Determine provider (OpenAI or Google) and upload the file
    file_id = None
    is_google_model = model_name.startswith("gemini-") or model_name == "imagen-3"
    
    try:
        if is_google_model:
            # For Google models
            emit_progress({"message": f"Preparing to use Google model: {model_name}"})
            try:
                # Google doesn't have file ID caching yet, so always upload
                emit_progress({"message": f"Uploading PDF to Google: {pdf_path.name}"})
                file_id = google_upload(pdf_path)
                emit_progress({"message": f"PDF uploaded successfully to Google. File ID: {file_id}"})
            except Exception as e:
                emit_progress({"message": f"Error during Google file upload: {e}"})
                return {
                    "items": 0,
                    "mean_score": 0.0,
                    "elapsed_s": round(perf_counter() - t0, 2),
                    "model_name": model_name,
                    "error": f"Google file upload failed: {e}"
                }
        else:
            # For OpenAI models
            emit_progress({"message": f"Preparing to use OpenAI model: {model_name}"})
            try:
                # Check if this PDF (by content hash) is already in our store
                file_id = get_openai_file_id(pdf_path)
                
                if not file_id:
                    emit_progress({"message": f"No existing OpenAI file ID found for {pdf_path.name}. Uploading..."})
                    # If not found, upload it
                    file_id = openai_upload(pdf_path)
                    # And save the new mapping to our local store
                    add_file_mapping(pdf_path, file_id)
                    emit_progress({"message": f"PDF uploaded successfully to OpenAI. File ID: {file_id} (and mapped locally)"})
                else:
                    emit_progress({"message": f"Using existing OpenAI file ID: {file_id} for {pdf_path.name}"})
            except Exception as e:
                emit_progress({"message": f"Error during OpenAI file handling (check/upload/map): {e}"})
                return {
                    "items": 0,
                    "mean_score": 0.0,
                    "elapsed_s": round(perf_counter() - t0, 2),
                    "model_name": model_name,
                    "error": f"OpenAI file operation failed: {e}"
                }
    except Exception as e:
        emit_progress({"message": f"Unexpected error during file preparation: {e}"})
        return {
            "items": 0,
            "mean_score": 0.0,
            "elapsed_s": round(perf_counter() - t0, 2),
            "model_name": model_name,
            "error": f"File preparation failed: {e}"
        }

    # 2. ask questions
    try:
        scores = []
        answers = []
        individual_prompt_data = [] # To store latency and token info per prompt
        total_standard_input_tokens_run = 0
        total_cached_input_tokens_run = 0
        total_output_tokens_run = 0

        if not prompts:
            emit_progress({"message": "Warning: No prompts provided for benchmark."})
            return {
                "items": 0,
                "mean_score": 0.0,
                "elapsed_s": round(perf_counter() - t0, 2),
                "model": model_name,
                "error": "No prompts provided"
            }

        for i, row in enumerate(prompts):
            # Support both formats: 'prompt_text'/'expected_answer' and legacy 'prompt'/'expected'
            prompt_text = row.get("prompt_text", row.get("prompt", ""))
            expected_text = row.get("expected_answer", row.get("expected", ""))
            prompt_length_chars = len(prompt_text)
            
            try:
                progress_message = f"Asking: {prompt_text[:50]}..."
                emit_progress({"current": i + 1, "total": total_prompts, "message": progress_message})
                
                prompt_t0 = perf_counter()
                if is_google_model:
                    # Use Google API for Google models
                    ans, standard_input_tokens_val, cached_input_tokens_val, output_tokens_val = google_ask(file_id, prompt_text, model_name)
                else:
                    # Use OpenAI API for OpenAI models
                    ans, standard_input_tokens_val, cached_input_tokens_val, output_tokens_val = openai_ask(file_id, prompt_text, model_name)
                prompt_t1 = perf_counter()
                individual_latency_ms = round((prompt_t1 - prompt_t0) * 1000)

                answers.append(ans)
                total_standard_input_tokens_run += standard_input_tokens_val
                total_cached_input_tokens_run += cached_input_tokens_val
                total_output_tokens_run += output_tokens_val
                
                # Score the answer
                ok = simple_score(ans, expected_text)
                scores.append(ok)
                individual_prompt_data.append({
                    "prompt_text": prompt_text,
                    "prompt_length_chars": prompt_length_chars,
                    "latency_ms": individual_latency_ms,
                    "standard_input_tokens": standard_input_tokens_val,
                    "cached_input_tokens": cached_input_tokens_val,
                    "output_tokens": output_tokens_val,
                    "model_answer": ans, # Store full answer here for prompts_data later
                    "expected_answer": expected_text,
                    "score": ok
                })
                
                # Show truncated answer and score
                ans_trunc = ans[:100] + "..." if len(ans) > 100 else ans
                emit_progress({"current": i + 1, "total": total_prompts, "message": f"Answer: {ans_trunc}. Score: {ok} (Expected: {expected_text[:50]}...)"})
            except Exception as e:
                error_msg = f"Error processing prompt '{prompt_text[:30]}...': {e}"
                emit_progress({"current": i + 1, "total": total_prompts, "message": error_msg, "is_error": True})
                scores.append(0)  # Count as a failed score
                answers.append(f"ERROR: {str(e)}") # Keep original answers list for compatibility if needed elsewhere
                individual_prompt_data.append({
                    "prompt_text": prompt_text,
                    "prompt_length_chars": prompt_length_chars,
                    "latency_ms": 0, # Error case
                    "standard_input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "model_answer": f"ERROR: {str(e)}",
                    "expected_answer": expected_text,
                    "score": 0
                })

        # 3. summarise
        mean_score_val = round(sum(scores) / len(scores), 3) if scores else 0.0
        elapsed = round(perf_counter() - t0, 2)
        total_tokens_run = total_standard_input_tokens_run + total_cached_input_tokens_run + total_output_tokens_run
        
        emit_progress({"message": f"Benchmark complete! Mean score: {mean_score_val}, Time: {elapsed}s, Total Tokens: {total_tokens_run}"})

        # Reconstruct prompts_data from individual_prompt_data to ensure all info is there
        result_prompts_data = [
            {
                "prompt_text": ipd["prompt_text"],
                "expected_answer": ipd["expected_answer"],
                "model_answer": ipd["model_answer"],
                "score": ipd["score"],
                "standard_input_tokens": ipd["standard_input_tokens"],
                "cached_input_tokens": ipd["cached_input_tokens"],
                "output_tokens": ipd["output_tokens"],
                "latency_ms": ipd["latency_ms"],
                "prompt_length_chars": ipd["prompt_length_chars"]
            } for ipd in individual_prompt_data
        ]

        return {
            "items": len(scores),
            "mean_score": mean_score_val,
            "elapsed_s": elapsed,
            "model_name": model_name,
            "prompts_data": result_prompts_data, 
            "pdf_path": str(pdf_path),
            "total_standard_input_tokens": total_standard_input_tokens_run,
            "total_cached_input_tokens": total_cached_input_tokens_run,
            "total_output_tokens": total_output_tokens_run,
            "total_tokens": total_tokens_run,
        }
    except Exception as e: # Catch-all for errors during the question asking and summarizing phase
        emit_progress({"message": f"Error during benchmark execution (asking/scoring/summarizing): {e}"})
        return {
            "items": total_prompts,
            "mean_score": 0.0,
            "elapsed_s": round(perf_counter() - t0, 2),
            "model_name": model_name,
            "error": f"Benchmark execution failed: {e}",
            "pdf_path": str(pdf_path)
        }

# Removed the old run_benchmark implementation
