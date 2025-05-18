#!/usr/bin/env python3
"""
Test script that runs a benchmark using the AppLogic class directly.
This more closely mimics how the UI triggers benchmarks.
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
        logging.FileHandler("test_app_benchmark.log"),
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
    logging.info("Successfully imported app modules")
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}", exc_info=True)
    sys.exit(1)

# Create a simple UI bridge implementation
class TestUIBridge(AppUIBridge):
    """Simple implementation of AppUIBridge for testing"""
    
    def __init__(self):
        self.messages = []
        self.progress_updates = []
    
    def show_message(self, level, title, message):
        log_message = f"UI Message [{level}] {title}: {message}"
        logging.info(log_message)
        self.messages.append({"level": level, "title": title, "message": message})
    
    def notify_benchmark_progress(self, job_id, job_data):
        log_message = f"Benchmark Progress [Job {job_id}]: {job_data}"
        logging.info(log_message)
        self.progress_updates.append({"job_id": job_id, "data": job_data})
    
    def notify_data_change(self, change_type, data):
        logging.info(f"Data Change: {change_type}")
    
    def start_auto_refresh(self):
        logging.info("Auto-refresh started")
    
    def stop_auto_refresh(self):
        logging.info("Auto-refresh stopped")
    
    def populate_home_benchmarks_table(self, benchmarks_data=None):
        logging.info(f"Populate benchmarks table with {len(benchmarks_data) if benchmarks_data else 0} items")

def main():
    """Run a benchmark test using the AppLogic class"""
    logging.info("=== STARTING APP BENCHMARK TEST ===")
    
    # Create the UI bridge and AppLogic
    ui_bridge = TestUIBridge()
    app_logic = AppLogic(ui_bridge=ui_bridge)
    
    # Define test parameters
    pdf_path = Path(project_root) / "files" / "2025_Special_FiftyDaysOfGrey" / "fifty-days-of-grey.pdf"
    prompts = [
        {
            "prompt_text": "What year did this piece get written?",
            "expected_answer": "2025"
        }
    ]
    model_names = ["gpt-4.1-nano"]
    label = "Test Benchmark"
    description = "Automated test of the benchmark system"
    
    # Validate PDF existence
    if not pdf_path.exists():
        logging.error(f"PDF not found at path: {pdf_path}")
        sys.exit(1)
    
    logging.info(f"Using models: {model_names}")
    logging.info(f"PDF path: {pdf_path} (size: {os.path.getsize(pdf_path) / 1024:.1f} KB)")
    logging.info(f"Prompts: {json.dumps(prompts, indent=2)}")
    
    try:
        # Launch the benchmark
        logging.info("Launching benchmark through AppLogic...")
        result = app_logic.launch_benchmark_run(prompts, str(pdf_path), model_names, label, description)
        
        logging.info(f"Launch result: {result}")
        
        # Wait for the benchmark to complete (or timeout)
        max_wait_time = 60  # seconds
        start_time = time.time()
        
        logging.info(f"Waiting up to {max_wait_time} seconds for benchmark completion...")
        
        while time.time() - start_time < max_wait_time:
            # Check progress updates
            if ui_bridge.progress_updates:
                latest_update = ui_bridge.progress_updates[-1]
                job_data = latest_update.get("data", {})
                
                models_details = job_data.get("models_details", {})
                if model_names[0] in models_details:
                    model_status = models_details[model_names[0]].get("status")
                    
                    if model_status in ["completed", "error"]:
                        logging.info(f"Benchmark completed with status: {model_status}")
                        break
            
            # Print some status
            if len(ui_bridge.progress_updates) > 0:
                latest = ui_bridge.progress_updates[-1]
                logging.info(f"Latest progress update: {latest}")
            
            # Sleep to avoid busy waiting
            time.sleep(1)
        
        elapsed = time.time() - start_time
        
        if elapsed >= max_wait_time:
            logging.warning("Benchmark did not complete within the timeout period")
        
        logging.info(f"Final UI messages: {ui_bridge.messages}")
        logging.info(f"Total progress updates: {len(ui_bridge.progress_updates)}")
        
    except Exception as e:
        logging.error(f"Exception during benchmark execution: {e}", exc_info=True)
    
    logging.info("=== TEST COMPLETED ===")

if __name__ == "__main__":
    main()
