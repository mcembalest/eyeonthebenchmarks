"""
Test script that runs a benchmark with multiple models simultaneously.
This tests both OpenAI and Google models to verify cross-provider compatibility.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_multimodel_benchmark.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Add the project root to sys.path if needed
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import the AppLogic and UI bridge
try:
    from app import AppLogic
    from ui_bridge import AppUIBridge, DataChangeType
    from dotenv import load_dotenv
    logging.info("Successfully imported app modules")
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}", exc_info=True)
    sys.exit(1)

# Ensure environment variables are loaded
load_dotenv()
if not os.environ.get("OPENAI_API_KEY"):
    logging.error("OPENAI_API_KEY not set in environment or .env file")
    sys.exit(1)
    
if not os.environ.get("GOOGLE_API_KEY"):
    logging.error("GOOGLE_API_KEY not set in environment or .env file")
    sys.exit(1)

# Create a UI bridge implementation that tracks model completions
class MultiModelTestUIBridge(AppUIBridge):
    """Implementation of AppUIBridge that tracks all model completions"""
    
    def __init__(self):
        self.messages = []
        self.progress_updates = []
        self.model_statuses = {}
        self.completed_models = set()
        self.errored_models = set()
        
    def show_message(self, level, title, message):
        log_message = f"UI Message [{level}] {title}: {message}"
        logging.info(log_message)
        self.messages.append({"level": level, "title": title, "message": message})
    
    def notify_benchmark_progress(self, job_id, job_data):
        self.progress_updates.append({"job_id": job_id, "data": job_data})
        
        # First check direct model status updates (used by Google model)
        model_name = job_data.get("model_name")
        status = job_data.get("status")
        
        if model_name and status:
            logging.info(f"Direct model update - {model_name}: {status}")
            
            # Store status
            self.model_statuses[model_name] = status
            
            # Track completion
            if status == "complete":
                logging.info(f"Model {model_name} COMPLETED")
                self.completed_models.add(model_name)
            elif status == "error":
                logging.info(f"Model {model_name} ERRORED")
                self.errored_models.add(model_name)
        
        # Also check models_details for OpenAI model status
        models_details = job_data.get("models_details", {})
        for model_name, details in models_details.items():
            status = details.get("status")
            if status != self.model_statuses.get(model_name):
                logging.info(f"Model details update - {model_name}: {status}")
                
            self.model_statuses[model_name] = status
            
            if status == "completed" or status == "complete":
                logging.info(f"Model {model_name} COMPLETED")
                self.completed_models.add(model_name)
            elif status == "error":
                logging.info(f"Model {model_name} ERRORED")
                self.errored_models.add(model_name)
    
    def notify_data_change(self, change_type, data):
        logging.info(f"Data Change: {change_type}")
    
    def are_all_models_finished(self, model_names):
        """Check if all models have completed or errored"""
        for model in model_names:
            if model not in self.completed_models and model not in self.errored_models:
                return False
        return True

def main():
    """Run a multi-model benchmark test"""
    logging.info("=== STARTING MULTI-MODEL BENCHMARK TEST ===")
    
    # Create the UI bridge and AppLogic
    ui_bridge = MultiModelTestUIBridge()
    app_logic = AppLogic(ui_bridge=ui_bridge)
    
    # Define test parameters
    pdf_path = Path(project_root) / "files" / "2025_Special_FiftyDaysOfGrey" / "fifty-days-of-grey.pdf"
    
    # If test PDF doesn't exist, create a simple one
    if not pdf_path.exists():
        logging.info(f"Test PDF not found. Creating a simple test PDF at {pdf_path}")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write a simple text file for testing
        with open(pdf_path, "w") as f:
            f.write("This is a test document from 2025.\n")
            f.write("It was written to test multi-model benchmarking capabilities.\n")
            f.write("This document is called Fifty Days of Grey and was written in 2025.")
    
    # Test prompts
    prompts = [
        {
            "prompt_text": "What year was this document written?",
            "expected_answer": "2025"
        },
        {
            "prompt_text": "What is the name of this document?",
            "expected_answer": "Fifty Days of Grey"
        }
    ]
    
    # We'll test with one OpenAI model and one Google model
    model_names = ["gpt-4.1-nano", "gemini-2.5-flash-preview-04-17"]
    label = "Multi-Model Test"
    description = "Testing parallel execution of OpenAI and Google models"
    
    # Log test parameters
    logging.info(f"Using models: {model_names}")
    logging.info(f"PDF path: {pdf_path} (size: {os.path.getsize(pdf_path) / 1024:.1f} KB)")
    logging.info(f"Prompts: {json.dumps(prompts, indent=2)}")
    
    try:
        # Launch the benchmark
        logging.info("Launching benchmark with multiple models...")
        result = app_logic.launch_benchmark_run(prompts, str(pdf_path), model_names, label, description)
        
        logging.info(f"Launch result: {result}")
        benchmark_id = result.get("benchmark_id")
        job_id = result.get("job_id")
        
        if benchmark_id is None or job_id is None:
            logging.error("Failed to get benchmark_id or job_id from launch result")
            sys.exit(1)
            
        logging.info(f"Successfully started benchmark ID {benchmark_id} with job ID {job_id}")
        
        # Wait for all models to complete (or timeout)
        max_wait_time = 120  # seconds (longer timeout for multiple models)
        start_time = time.time()
        
        logging.info(f"Waiting up to {max_wait_time} seconds for all models to complete...")
        
        while time.time() - start_time < max_wait_time:
            # Check if all models have finished
            if ui_bridge.are_all_models_finished(model_names):
                logging.info("All models have finished processing!")
                break
                
            # Wait before checking again
            time.sleep(1)
        else:
            # Timeout occurred
            logging.warning(f"Timeout after {max_wait_time} seconds")
            
        # Report final status for each model
        logging.info("=== FINAL MODEL STATUSES ===")
        for model in model_names:
            status = "completed" if model in ui_bridge.completed_models else \
                     "error" if model in ui_bridge.errored_models else \
                     "unknown"
            logging.info(f"{model}: {status}")
            
        # Verify success criteria
        if len(ui_bridge.completed_models) == len(model_names):
            logging.info("SUCCESS: All models completed successfully!")
            return True
        else:
            logging.warning(f"PARTIAL SUCCESS: {len(ui_bridge.completed_models)} of {len(model_names)} models completed")
            return False
            
    except Exception as e:
        logging.error(f"Error during multi-model benchmark test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
