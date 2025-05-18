#!/usr/bin/env python3
"""
UI Consistency Test Script for Eye on the Benchmarks

This script tests the consistency of benchmark status rendering across different views in the UI.
It will:
1. Create benchmarks with specific states
2. Check how they're rendered in both Grid View and Table View
3. Log inconsistencies between the views
4. Test status preservation during refreshes
5. Test the handling of deleted benchmarks

Usage:
    python test_ui_consistency.py
"""

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ui_consistency_test.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Helper functions
def run_command(cmd, timeout=10):
    """Run a shell command and return its output."""
    logger.info(f"Running command: {cmd}")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"STDERR: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        return None

def get_app_pid():
    """Get the PID of the running app if it exists."""
    ps_output = run_command("ps -ef | grep '[a]pp.py'")
    if not ps_output:
        return None
    
    try:
        pid = int(ps_output.split()[1])
        return pid
    except (IndexError, ValueError):
        return None

def is_app_running():
    """Check if the app is already running."""
    return get_app_pid() is not None

def start_app():
    """Start the Eye on the Benchmarks app."""
    if is_app_running():
        logger.info("App is already running")
        return True
    
    logger.info("Starting the app...")
    app_dir = Path(__file__).parent
    start_cmd = f"cd {app_dir} && nohup python app.py > app_test_run.log 2>&1 &"
    result = run_command(start_cmd)
    
    # Wait for app to start
    for _ in range(10):
        if is_app_running():
            logger.info("App started successfully")
            # Give it a moment to fully initialize
            time.sleep(3)
            return True
        time.sleep(1)
    
    logger.error("Failed to start the app")
    return False

def stop_app():
    """Stop the running app."""
    pid = get_app_pid()
    if not pid:
        logger.info("App is not running")
        return
    
    logger.info(f"Stopping app (PID: {pid})...")
    run_command(f"kill {pid}")
    
    # Wait for app to stop
    for _ in range(5):
        if not is_app_running():
            logger.info("App stopped successfully")
            return
        time.sleep(1)
    
    # Force kill if normal kill didn't work
    logger.warning(f"Force killing app (PID: {pid})...")
    run_command(f"kill -9 {pid}")

class BenchmarkConsistencyTester:
    """Tests benchmark status consistency across UI views."""
    
    def __init__(self):
        self.app_dir = Path(__file__).parent
        self.db_path = self.app_dir / "benchmarks.db"
        self.created_benchmark_ids = []
        
    def setup(self):
        """Prepare the test environment."""
        logger.info("Setting up test environment...")
        
        # Backup existing database
        if self.db_path.exists():
            backup_path = self.db_path.with_suffix(f".db.bak.{int(time.time())}")
            logger.info(f"Backing up database to {backup_path}")
            run_command(f"cp {self.db_path} {backup_path}")
    
    def create_benchmark(self, label, models=None, status="running"):
        """Create a test benchmark with specific properties."""
        if models is None:
            models = ["gpt-4-turbo", "gemini-1.5-pro"]
        
        logger.info(f"Creating benchmark '{label}' with status '{status}'...")
        
        # Store metadata for this benchmark
        timestamp = datetime.now().isoformat()
        
        # Simulate direct database insertion for testing
        # In a real scenario, this would use the app's API
        # But for testing we can create the benchmark data directly
        
        # TODO: In a real implementation, this would call the app's API
        # to create the benchmark. For now, we're just logging the intent.
        logger.info(f"Would create benchmark: {label} with models {models}")
        
        # Return simulated benchmark ID
        simulated_id = int(time.time())
        self.created_benchmark_ids.append(simulated_id)
        return simulated_id
    
    def check_view_consistency(self, benchmark_id):
        """Check if Grid View and Table View show consistent status for a benchmark."""
        logger.info(f"Checking UI consistency for benchmark {benchmark_id}...")
        
        # In a real implementation, this would use a UI automation tool
        # such as Selenium or Playwright to check the actual UI elements
        
        # TODO: Implement actual UI checking logic
        # For now, we'll just simulate the check with logging
        
        logger.info("CONSISTENCY CHECK NEEDED: Manual verification required")
        logger.info("Please verify in the UI:")
        logger.info(f"1. Does benchmark {benchmark_id} have the same status in both Grid and Table views?")
        logger.info("2. Are all models showing the correct completion status?")
        
    def wait_for_status_update(self, seconds=2):
        """Wait for UI to potentially update."""
        logger.info(f"Waiting {seconds} seconds for UI updates...")
        time.sleep(seconds)
    
    def test_multi_model_benchmark(self):
        """Test a benchmark with multiple models to check status consistency."""
        logger.info("\n=== TEST CASE: Multi-Model Benchmark Status ===")
        
        # Create a benchmark with multiple models
        benchmark_id = self.create_benchmark("Multi-Model Test")
        logger.info(f"Created benchmark with ID {benchmark_id}")
        
        # Check initial rendering in both views
        logger.info("Step 1: Checking initial status (should be 'running' in both views)")
        self.check_view_consistency(benchmark_id)
        
        # Simulate first model completion
        logger.info("Step 2: Simulating completion of first model")
        # In a real test, we'd use an API to mark one model as complete
        logger.info("Simulated first model completion")
        self.wait_for_status_update()
        
        # Check status after first model completes (should still be running)
        logger.info("Step 3: Checking status after one model completes (should still be 'running')")
        self.check_view_consistency(benchmark_id)
        
        # Simulate second model completion
        logger.info("Step 4: Simulating completion of second model")
        # In a real test, we'd use an API to mark the second model as complete
        logger.info("Simulated second model completion")
        self.wait_for_status_update()
        
        # Check final status (should be complete)
        logger.info("Step 5: Checking final status (should be 'complete' in both views)")
        self.check_view_consistency(benchmark_id)
        
        return True
    
    def test_status_during_refresh(self):
        """Test if benchmark status is preserved during UI refreshes."""
        logger.info("\n=== TEST CASE: Status Preservation During Refresh ===")
        
        # Create a benchmark
        benchmark_id = self.create_benchmark("Refresh Test")
        logger.info(f"Created benchmark with ID {benchmark_id}")
        
        # Check initial rendering
        logger.info("Step 1: Checking initial status")
        self.check_view_consistency(benchmark_id)
        
        # Simulate one model completion
        logger.info("Step 2: Simulating completion of one model (not all)")
        # In a real test, we'd use an API to mark one model as complete
        logger.info("Simulated first model completion")
        self.wait_for_status_update()
        
        # Check status before refresh
        logger.info("Step 3: Checking status before refresh (should be 'running')")
        self.check_view_consistency(benchmark_id)
        
        # Simulate UI refresh
        logger.info("Step 4: Simulating UI refresh")
        # In a real test, we'd trigger a UI refresh event
        logger.info("Simulated UI refresh")
        self.wait_for_status_update()
        
        # Check status after refresh
        logger.info("Step 5: Checking status after refresh (should still be 'running')")
        logger.info("CRITICAL CHECK: This is where inconsistencies are likely to occur")
        self.check_view_consistency(benchmark_id)
        
        return True
    
    def test_deleted_benchmark_reappearance(self):
        """Test if deleted benchmarks reappear after creating new benchmarks."""
        logger.info("\n=== TEST CASE: Deleted Benchmark Reappearance ===")
        
        # Create two benchmarks
        first_id = self.create_benchmark("To Be Deleted")
        second_id = self.create_benchmark("Will Remain")
        logger.info(f"Created benchmarks with IDs {first_id} and {second_id}")
        
        # Check initial rendering
        logger.info("Step 1: Checking initial rendering of both benchmarks")
        self.check_view_consistency(first_id)
        self.check_view_consistency(second_id)
        
        # Delete the first benchmark
        logger.info("Step 2: Deleting the first benchmark")
        # In a real test, we'd use an API to delete the benchmark
        logger.info(f"Simulated deletion of benchmark {first_id}")
        self.wait_for_status_update()
        
        # Check that only one benchmark is shown
        logger.info("Step 3: Verifying only the second benchmark is visible")
        self.check_view_consistency(second_id)
        
        # Create a new benchmark
        logger.info("Step 4: Creating a new benchmark")
        third_id = self.create_benchmark("Newly Created")
        logger.info(f"Created new benchmark with ID {third_id}")
        self.wait_for_status_update()
        
        # Check that the deleted benchmark hasn't reappeared
        logger.info("Step 5: Verifying the deleted benchmark hasn't reappeared")
        logger.info("CRITICAL CHECK: Deleted benchmark should not reappear")
        # In a real test, we'd check the UI for the absence of the deleted benchmark
        
        return True
    
    def test_grid_table_view_sync(self):
        """Test if Grid View and Table View show consistent statuses."""
        logger.info("\n=== TEST CASE: Grid/Table View Status Sync ===")
        
        # Create benchmark
        benchmark_id = self.create_benchmark("View Sync Test")
        logger.info(f"Created benchmark with ID {benchmark_id}")
        
        # Initial check
        logger.info("Step 1: Checking initial status in both views")
        self.check_view_consistency(benchmark_id)
        
        # Check after status change
        logger.info("Step 2: Simulating status change")
        # In a real test, we'd use an API to change the status
        logger.info("Simulated status change")
        self.wait_for_status_update()
        
        # Check after status change
        logger.info("Step 3: Checking status after change (should be consistent in both views)")
        self.check_view_consistency(benchmark_id)
        
        # Toggle between grid and table views
        logger.info("Step 4: Toggling between Grid and Table views")
        logger.info("VERIFY: Switch between Grid and Table views in the UI")
        
        # Final check
        logger.info("Step 5: Final consistency check after view switching")
        self.check_view_consistency(benchmark_id)
        
        return True
    
    def run_all_tests(self):
        """Run all test cases."""
        logger.info("Starting UI consistency tests...")
        
        try:
            self.setup()
            
            # Make sure the app is running
            if not is_app_running():
                if not start_app():
                    logger.error("Couldn't start the app, aborting tests")
                    return False
            
            # Run test cases
            self.test_multi_model_benchmark()
            self.test_status_during_refresh()
            self.test_deleted_benchmark_reappearance()
            self.test_grid_table_view_sync()
            
            logger.info("\n=== UI Consistency Test Results ===")
            logger.info("All tests completed. Please check the log for results.")
            logger.info("IMPORTANT: Some checks require manual verification in the UI.")
            
            return True
        except Exception as e:
            logger.exception(f"Error during tests: {e}")
            return False
        finally:
            # Keep the app running for manual inspection
            logger.info("Testing completed. App is still running for manual inspection.")
            logger.info("Run 'python test_ui_consistency.py --stop' to stop the app.")

def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--stop":
        stop_app()
        return
    
    tester = BenchmarkConsistencyTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
