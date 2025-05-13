import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import os
import csv
import threading

# Import the CSV exporter
from engine.exporter import export_benchmark_to_csv

# Engine components
from engine.file_store import (
    init_db as init_file_store_db,
    save_benchmark,
    save_benchmark_run,
    save_benchmark_prompt,
    load_benchmark_details,
    find_benchmark_by_files
)
# engine.runner is imported within BenchmarkWorker to allow monkeypatching

# Import the UI bridge protocol and data change types
from ui_bridge import AppUIBridge, DataChangeType


class BenchmarkWorker(threading.Thread): # Changed from QThread
    # finished = Signal(dict) # Removed Qt Signal
    # progress = Signal(str)  # Removed Qt Signal

    def __init__(self, prompts: list, pdf_path: Path, model_name: str, on_progress: callable, on_finished: callable): # Added model_name and callbacks
        super().__init__()
        self.prompts = prompts
        self.pdf_path = pdf_path
        self.model_name = model_name # Store the model name
        self.on_progress = on_progress # This is AppLogic.handle_benchmark_progress
        self.on_finished = on_finished # This is AppLogic.handle_run_finished
        self._original_emit_progress_callback = None # To store the original callback from engine.runner if any

    def run(self):
        import engine.runner # Import here for monkeypatching
        
        # Store original and set our override for engine.runner's progress emission
        # The new engine.runner has a set_emit_progress_callback function
        self._original_emit_progress_callback = getattr(engine.runner, '_emit_progress_callback', None)
        engine.runner.set_emit_progress_callback(self._emit_progress_override)
        
        try:
            # run_benchmark now returns a dict which includes pdf_path and model_name
            result = engine.runner.run_benchmark(self.prompts, self.pdf_path, self.model_name) # Pass model_name
            if self.on_finished:
                self.on_finished(result) 
        except Exception as e:
            print(f"Exception in BenchmarkWorker: {e}")
            if self.on_finished:
                # Ensure the error result structure is consistent with what handle_run_finished expects
                error_result = {
                    "error": str(e), 
                    "pdf_path": self.pdf_path, 
                    "items": len(self.prompts),
                    "mean_score": 0.0,
                    "elapsed_s": 0, # Or calculate if possible
                    "model_name": self.model_name # Include model_name in error
                }
                self.on_finished(error_result)
        finally:
            # Restore original emit_progress_callback in engine.runner
            if self._original_emit_progress_callback is not None:
                engine.runner.set_emit_progress_callback(self._original_emit_progress_callback)
            else:
                 # If there was no original, set it to None to clear our callback
                engine.runner.set_emit_progress_callback(None)

    def _emit_progress_override(self, data: dict): # Expects a dictionary now
        if self.on_progress:
            self.on_progress(data) # Pass the structured data to AppLogic.handle_benchmark_progress
        
        # If there was an original callback we were supposed to chain to (e.g. default print), 
        # we could call it here. Current engine.runner.emit_progress with None callback prints.
        # For this refactor, we assume our override is the sole handler during the benchmark run.
        # if self._original_emit_progress_callback:
        # self._original_emit_progress_callback(data)


class AppLogic:
    def __init__(self, ui_bridge: AppUIBridge):
        self.ui_bridge = ui_bridge
        self.worker: Optional[BenchmarkWorker] = None
        # Abstract job tracking: jobs can be any type of benchmark or batch job
        # Each job is tracked by a unique job_id, with status, progress, and metadata
        self.jobs = {}  # {job_id: {'status': 'unfinished'|'finished', 'progress': float, ...}}
        self._next_job_id = 0
        self._current_benchmark_id = None
        self._current_benchmark_file_paths = []
        
        # Initial setup
        self._initialize_database()
        self._ensure_directories_exist()
        self._setup_data_observers()
        
        # Start automatic refresh
        self.ui_bridge.start_auto_refresh()

    def _setup_data_observers(self):
        """Set up observers for various data changes"""
        self.ui_bridge.register_data_callback(
            DataChangeType.BENCHMARK_LIST,
            lambda _: self._refresh_benchmark_list()
        )
        self.ui_bridge.register_data_callback(
            DataChangeType.COMPOSER_DATA,
            lambda _: self._refresh_composer_data()
        )

    def _refresh_benchmark_list(self):
        """Refresh the list of benchmarks and active runs for the home page."""
        # Trigger HomePage to load/refresh its main benchmark table (grid/table views)
        # The HomePage.load_runs_from_db() method handles fetching and populating.
        self.ui_bridge.populate_home_benchmarks_table(None) # Argument is now optional/unused

        # Update active benchmarks display separately
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())

    def _refresh_composer_data(self):
        """Refresh composer page data"""
        # Any composer-specific data refresh logic here
        pass

    def _initialize_database(self):
        """Initialize the file store database"""
        try:
            init_file_store_db(Path.cwd())
        except Exception as e:
            print(f"Error initializing database: {e}")
            
    def handle_export_benchmark_csv(self, benchmark_id: int):
        """Handle a request to export a benchmark's results to CSV"""
        try:
            # Create exports directory if it doesn't exist
            exports_dir = Path.cwd() / "exports"
            os.makedirs(exports_dir, exist_ok=True)
            
            # Export the benchmark to CSV
            csv_path = export_benchmark_to_csv(benchmark_id, exports_dir)
            
            # Show success message
            self.ui_bridge.show_message("Success", "CSV Export", f"Benchmark exported to:\n{csv_path}")
            
        except Exception as e:
            error_msg = f"Error exporting benchmark to CSV: {str(e)}"
            print(error_msg)
            self.ui_bridge.show_message("Error", "CSV Export Failed", error_msg)

    def _ensure_directories_exist(self):
        files_dir = Path.cwd() / "files"
        if not files_dir.exists():
            os.makedirs(files_dir)
            print(f"Created files directory: {files_dir}")
        
        heliocentrism_dir = files_dir / "2025_Energy_heliocentrism"
        if not heliocentrism_dir.exists():
            os.makedirs(heliocentrism_dir)
            print(f"Created heliocentrism directory: {heliocentrism_dir}")
            print("IMPORTANT: Please place the 'heliocentrism-amv.pdf' file in this directory for the default benchmark.")


    def _connect_signals(self):
        # Signal connections are now handled by the UI layer (e.g., main_qt.py)
        # This method can be removed or repurposed if AppLogic needs to register internal event handlers.
        pass

    # @Slot() # Slot decorator removed
    def request_open_csv_file(self): # Renamed, as AppLogic requests, UI bridge performs
        file_path = self.ui_bridge.get_csv_file_path_via_dialog() # Use UI bridge
        if not file_path:
            return
        
        try:
            with open(file_path, newline="", encoding='utf-8') as f:
                rows = list(csv.reader(f))
            
            self.ui_bridge.populate_composer_table(rows) # Use UI bridge
            self.ui_bridge.show_composer_page() # Use UI bridge
        except Exception as e:
            self.ui_bridge.show_message("critical", "CSV Error", f"Could not open or parse CSV file: {e}")


    # @Slot(list, Path) # Slot decorator removed
    def launch_benchmark_run(self, prompts: list, pdf_to_run: Path, model_names: list):
        if not prompts:
            self.ui_bridge.show_message("warning", "No prompts", "Please enter at least one prompt.")
            return
        if not pdf_to_run:
            self.ui_bridge.show_message("warning", "No PDF", "Please select a PDF file for the benchmark.")
            return
        if not model_names:
            self.ui_bridge.show_message("warning", "No Model(s) Selected", "Please select at least one model for the benchmark.")
            return

        label = f"Benchmark {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        description = f"Benchmark with {pdf_to_run.name}"

        # We need to be able to support multiple models, so we need to break this into multiple runs (queue-based)
        # For now we're just grabbing the first model in the list to keep the interface working.
        # In a future update, we'd want to run multiple models in sequence, or even in parallel.
        model_to_run = model_names[0] # Just use the first model for now

        # Always create a new benchmark when initiated from the benchmark creation page
        # This ensures different question+answer sets using the same PDF don't overwrite each other
        benchmark_id = save_benchmark(label, description, [str(pdf_to_run)], model_name=model_to_run)

        self._current_benchmark_id = benchmark_id
        self._current_benchmark_file_paths = [pdf_to_run]

        job_id = self._next_job_id
        self._next_job_id += 1
        self.jobs[job_id] = {
            'benchmark_id': benchmark_id,
            'status': 'unfinished',
            'progress': 0.0,
            'pdf_name': pdf_to_run.name,
            'model_name': model_to_run,
            'total_prompts': len(prompts),
            'current_prompt': 0,
            'status_message': 'Initializing...'
        }
        
        # Update active benchmarks in the UI
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        self.ui_bridge.notify_data_change(DataChangeType.ACTIVE_BENCHMARKS, self.get_active_benchmarks_info())

        # Log the benchmark start in the console
        self.ui_bridge.clear_console_log()
        self.ui_bridge.update_console_log(f"[{job_id}] Running benchmark with {pdf_to_run.name}...\n")
        self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] starting with {pdf_to_run.name}")
        
        # Start the worker thread
        self.worker = BenchmarkWorker(
            prompts,
            pdf_to_run,
            model_to_run,
            on_progress=lambda progress_data: self.handle_benchmark_progress(job_id, progress_data),
            on_finished=lambda result_data: self.handle_run_finished(job_id, result_data)
        )
        self.worker.start()
        
        # Immediately go to home page after starting the benchmark
        self.ui_bridge.show_home_page()

    def handle_benchmark_progress(self, job_id: int, progress_data: dict):
        # Update job progress generically
        if job_id in self.jobs:
            self.jobs[job_id]['current_prompt'] = progress_data.get('current', 0)
            self.jobs[job_id]['status_message'] = progress_data.get('message', '')
            total = self.jobs[job_id].get('total_prompts', 1)
            current = progress_data.get('current', 0)
            self.jobs[job_id]['progress'] = float(current) / float(total) if total else 0.0
            
            # Notify UI of progress update
            self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_PROGRESS, {
                'job_id': job_id,
                'progress': self.jobs[job_id]['progress'],
                'message': progress_data.get('message', '')
            })
            
            # Update active benchmarks display
            self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
            
        self.ui_bridge.update_console_log(f"[{job_id}] {progress_data.get('message', 'Progress update...')}\n")

    def handle_run_finished(self, job_id: int, result: dict):
        print(f"[AppLogic.handle_run_finished JOB_ID: {job_id}] Received result: {result}")
        if not self.worker:
            self.ui_bridge.show_message("critical", "Worker Error", "Benchmark worker not found during finish.")
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'finished'
                self._notify_benchmark_completion(job_id, None, error="Worker not found")
            return

        if result.get("error"):
            error_message = f"Benchmark [{job_id}] failed: {result['error']}"
            self.ui_bridge.show_message("critical", "Benchmark Error", error_message)
            self.ui_bridge.update_status_bar(error_message, 5000)
            summary_for_console = {
                'error': result['error'],
                'message': error_message
            }
            self.ui_bridge.display_benchmark_summary_in_console(summary_for_console, f"Failed Run {job_id}")
            self._notify_benchmark_completion(job_id, None, error=result['error'])
        else:
            benchmark_id = self._current_benchmark_id
            model_name = result.get('model_name', 'unknown')
            report = f"Mean score: {result.get('mean_score', 'N/A')}, Items: {result.get('items', 'N/A')}, Time: {result.get('elapsed_s', 'N/A')}s"
            latency = result.get('elapsed_s', 0.0)

            # Get detailed token counts using new token structure
            total_standard_input_tokens = result.get('total_standard_input_tokens', 0)
            total_cached_input_tokens = result.get('total_cached_input_tokens', 0)
            total_output_tokens = result.get('total_output_tokens', 0)
            total_tokens_overall = result.get('total_tokens', 0)

            # Use updated save_benchmark_run signature with standard and cached input tokens
            run_id = save_benchmark_run(benchmark_id, model_name, report, latency, 
                                       total_standard_input_tokens, total_cached_input_tokens, 
                                       total_output_tokens, total_tokens_overall)

            if run_id:
                prompts_data = result.get('prompts_data', [])
                for p in prompts_data:
                    prompt = p.get('prompt_text', '')
                    answer = p.get('expected_answer', '')
                    response = p.get('actual_answer', '')
                    score = str(p.get('score', ''))
                    latency_val = p.get('latency_ms', 0.0)
                    
                    # Use detailed token breakdown
                    standard_input_tokens_prompt = p.get('standard_input_tokens', 0)
                    cached_input_tokens_prompt = p.get('cached_input_tokens', 0)
                    output_tokens_prompt = p.get('output_tokens', 0)

                    save_benchmark_prompt(run_id, prompt, answer, response, score, latency_val, 
                                         standard_input_tokens_prompt, cached_input_tokens_prompt, output_tokens_prompt)

                self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] run saved with DB ID: {run_id}", 5000)
                
                # Store summary in the result for notifications
                result['summary'] = {
                    'run_id': run_id,
                    'model_name': model_name,
                    'mean_score': result.get('mean_score', 'N/A'),
                    'items': result.get('items', 'N/A'),
                    'elapsed_s': result.get('elapsed_s', 'N/A')
                }
            else:
                self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] failed to save to database.", 5000)
                self.ui_bridge.show_message("warning", "DB Error", f"Could not save benchmark [{job_id}] results to the database.")

            # Display results in console
            summary_result_for_console = result.copy()
            self.ui_bridge.display_benchmark_summary_in_console(summary_result_for_console, f"Run {job_id} (DB ID: {run_id})")
            self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] completed.", 5000)
            
            # Notify completion with success
            self._notify_benchmark_completion(job_id, result)

        # Mark job as finished and redirect to home
        if job_id in self.jobs:
            self.jobs[job_id]['status'] = 'finished'
        self.ui_bridge.show_home_page()

    def _notify_benchmark_completion(self, job_id: int, result: Optional[dict], error: str = None) -> None:
        """Notify UI of benchmark completion"""
        # Notify benchmark completion
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_COMPLETED, {
            'job_id': job_id,
            'success': error is None,
            'error': error,
            'result': result
        })
        
        # Update active benchmarks list
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        
        # Trigger a refresh of the benchmark list
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)

    def get_active_benchmarks_info(self) -> dict:
        # Return only unfinished jobs for UI display
        return {jid: data for jid, data in self.jobs.items() if data['status'] == 'unfinished'}

    # @Slot(object) # Slot decorator removed
    def request_display_benchmark_details(self, benchmark_id): # Renamed, AppLogic requests
        if benchmark_id is None:
            self.ui_bridge.show_message("warning", "Error", "Could not retrieve benchmark ID.")
            return

        details = load_benchmark_details(benchmark_id)
        if details:
            self.ui_bridge.display_full_benchmark_details_in_console(details)
            self.ui_bridge.show_console_page()
        else:
            self.ui_bridge.show_message("warning", "Error", f"Could not load details for benchmark ID: {benchmark_id}")
            self.ui_bridge.clear_console_log()
            self.ui_bridge.update_console_log(f"Failed to load details for benchmark ID: {benchmark_id}")
            self.ui_bridge.show_console_page() # Still show console with the error

    def startup(self):
        """Called by the application runner after AppLogic is initialized."""
        self.ui_bridge.show_home_page()


    # The run method is removed as AppLogic is not controlling the app lifecycle / event loop anymore.
    # def run(self):
    #     return self.app.exec()

# The __main__ block is removed. The application will be started by a dedicated runner script (e.g., main_qt.py).
# if __name__ == "__main__":
#     logic = AppLogic() # This would need a UI bridge now
#     sys.exit(logic.run()) 