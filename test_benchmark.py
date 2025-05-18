#!/usr/bin/env python3
"""
Minimal test script for running a benchmark with a single prompt.
This script bypasses the UI and directly uses the engine components.
"""

import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_benchmark.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    logging.error("No OPENAI_API_KEY found in environment. Please check your .env file.")
    sys.exit(1)
logging.info(f"OPENAI_API_KEY is set (length: {len(api_key)})")

# Import engine components
try:
    # Add the project root to sys.path
    project_root = Path(__file__).parent
    sys.path.append(str(project_root))
    logging.info(f"PYTHONPATH now includes: {str(project_root)}")
    
    logging.info("Attempting to import run_benchmark from runner...")
    from runner import run_benchmark
    logging.info("Successfully imported run_benchmark")
    
    logging.info("Attempting to import set_emit_progress_callback from runner...")
    from runner import set_emit_progress_callback
    logging.info("Successfully imported set_emit_progress_callback")
    
    # Print all available modules in the current path to help debug
    import pkgutil
    logging.info("Available modules in path:")
    for module in pkgutil.iter_modules([str(project_root)]):
        logging.info(f"  - {module.name}")
    
    logging.info("Successfully imported all engine modules")
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}", exc_info=True)
    sys.exit(1)

# Define a simple progress callback
def progress_callback(data):
    """Simple callback to display progress information"""
    if isinstance(data, dict):
        message = data.get('message', 'No message')
        current = data.get('current', None)
        total = data.get('total', None)
        
        if current is not None and total is not None:
            logging.info(f"Progress: [{current}/{total}] {message}")
        else:
            logging.info(f"Status: {message}")
    else:
        logging.info(f"Progress update: {data}")

def main():
    """Run a minimal benchmark test"""
    logging.info("=== STARTING MINIMAL BENCHMARK TEST ===")
    
    # Set the progress callback
    set_emit_progress_callback(progress_callback)
    
    # Define test parameters
    model_name = "gpt-4.1-nano"  # Can be changed to any supported model
    pdf_path = Path(project_root) / "files" / "2025_Special_FiftyDaysOfGrey" / "fifty-days-of-grey.pdf"
    prompts = [
        {
            "prompt_text": "What year did this piece get written?",
            "expected_answer": "2025"
        }
    ]
    
    # Validate PDF existence
    if not pdf_path.exists():
        logging.error(f"PDF not found at path: {pdf_path}")
        sys.exit(1)
    
    logging.info(f"Using model: {model_name}")
    logging.info(f"PDF path: {pdf_path} (size: {os.path.getsize(pdf_path) / 1024:.1f} KB)")
    logging.info(f"Prompt: '{prompts[0]['prompt_text']}'")
    
    try:
        # Run the benchmark
        logging.info("Starting benchmark execution...")
        start_time = time.time()
        
        result = run_benchmark(prompts, pdf_path, model_name)
        
        elapsed = time.time() - start_time
        logging.info(f"Benchmark completed in {elapsed:.2f} seconds")
        
        # Process results
        if 'error' in result:
            logging.error(f"Benchmark error: {result['error']}")
        else:
            logging.info("=== BENCHMARK RESULTS ===")
            logging.info(f"Mean score: {result.get('mean_score', 'N/A')}")
            logging.info(f"Total items: {result.get('items', 'N/A')}")
            logging.info(f"Total tokens: {result.get('total_tokens', 'N/A')}")
            
            # Print individual prompt results
            prompts_data = result.get('prompts_data', [])
            for i, prompt_data in enumerate(prompts_data):
                logging.info(f"\n--- Prompt {i+1} Results ---")
                logging.info(f"Prompt: {prompt_data.get('prompt_text', 'N/A')}")
                logging.info(f"Expected: {prompt_data.get('expected_answer', 'N/A')}")
                logging.info(f"Actual: {prompt_data.get('actual_answer', 'N/A')}")
                logging.info(f"Score: {prompt_data.get('score', 'N/A')}")
                logging.info(f"Input tokens: {prompt_data.get('standard_input_tokens', 0)} standard, {prompt_data.get('cached_input_tokens', 0)} cached")
                logging.info(f"Output tokens: {prompt_data.get('output_tokens', 0)}")
        
    except Exception as e:
        logging.error(f"Exception during benchmark execution: {e}", exc_info=True)
    
    logging.info("=== TEST COMPLETED ===")

if __name__ == "__main__":
    main()
