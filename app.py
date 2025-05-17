import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import os
import csv
import threading
import logging
import json # For script-based execution output

# --- Basic Logger Setup ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import the CSV exporter
from engine.exporter import export_benchmark_to_csv

# Engine components
from engine.file_store import (
    init_db as init_file_store_db,
    save_benchmark,
    save_benchmark_run,
    save_benchmark_prompt,
    load_benchmark_details,
    find_benchmark_by_files,
    delete_benchmark,
    update_benchmark_details,
    load_all_benchmarks_with_models
)
# Import engine modules at the top level to avoid threading issues
import engine.runner
from engine import models_openai, models_google

# Import the UI bridge protocol and data change types
from ui_bridge import AppUIBridge, DataChangeType

# --- ScriptUiBridge for command-line execution ---
class ScriptUiBridge(AppUIBridge):
    """A UI bridge that prints UI events as JSON to stdout for script-based execution."""
    def _send_event(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        print(json.dumps({"ui_bridge_event": event_name, "data": data or {}}))

    def show_message(self, level: str, title: str, message: str):
        self._send_event('show_message', {"level": level, "title": title, "message": message})

    def populate_composer_table(self, rows: list):
        # For script execution, this might not be directly useful unless the calling script handles it.
        # self._send_event('populate_composer_table', {"rows": rows})
        pass # Or log that it was called

    def show_composer_page(self):
        # self._send_event('show_composer_page', {})
        pass

    def get_csv_file_path_via_dialog(self) -> Optional[str]:
        # Cannot open dialogs in script mode. This should not be called by methods invoked via script.
        # If it is, it indicates a logic error or a method not suitable for script invocation.
        logging.warning("ScriptUiBridge: get_csv_file_path_via_dialog called, returning None.")
        return None

    def notify_benchmark_progress(self, job_id: int, progress_data: Dict[str, Any]):
        self._send_event('benchmark-progress', {"job_id": job_id, **progress_data})

    def notify_benchmark_complete(self, job_id: int, result_summary: Dict[str, Any]):
        self._send_event('benchmark-complete', {"job_id": job_id, **result_summary})

    def notify_active_benchmarks_updated(self, active_benchmarks: List[Dict[str, Any]]):
        self._send_event('active_benchmarks_updated', {"active_benchmarks": active_benchmarks})

    def populate_home_benchmarks_table(self, benchmarks_data: Optional[List[Dict[str, Any]]]):
        # This typically triggers a full refresh in the UI, which might be signaled differently.
        # For now, signal that a refresh is needed.
        self._send_event('refresh_benchmark_list_needed', {})

    def register_data_callback(self, data_type: DataChangeType, callback: callable):
        # Callbacks are typically for direct UI interaction, less relevant for script mode.
        pass

    def start_auto_refresh(self):
        # Auto-refresh is a UI concern, not applicable to script mode.
        pass

    def stop_auto_refresh(self):
        pass


class BenchmarkWorker(threading.Thread): 
    def __init__(self, job_id, benchmark_id, prompts, pdf_path, model_name, on_progress=None, on_finished=None): 
        super().__init__(name=f"BenchmarkWorker-{job_id}-{model_name}")  # Set daemon=True to prevent thread from blocking program exit
        self.active = True
        self.job_id = job_id
        self.benchmark_id = benchmark_id
        self.prompts = prompts
        self.pdf_path = pdf_path
        self.model_name = model_name 
        self.on_progress = on_progress 
        self.on_finished = on_finished 
        logging.info(f"BenchmarkWorker created: {self.getName()} with {len(prompts)} prompts for model {model_name}") 
        self._original_emit_progress_callback = None
        self.active = True

    def run(self):
        logging.info(f"Thread {self.getName()} starting execution")
        # Store the original callback
        self._original_emit_progress_callback = getattr(engine.runner, '_emit_progress_callback', None)
        engine.runner.set_emit_progress_callback(self._emit_progress_override)
        
        try:
            if not self.active:
                logging.warning("Worker thread was cancelled before starting")
                return
                
            logging.info(f"Thread {self.getName()}: active={self.active}, benchmark_id={self.benchmark_id}")
                
            # Pre-initialize any modules we'll need to avoid import during shutdown
            import traceback
            from engine import runner
            
            logging.info(f"BenchmarkWorker: Starting run_benchmark with model {self.model_name}, PDF: {self.pdf_path}, prompts count: {len(self.prompts)}")
            
            # Check for OpenAI API key, using dotenv to load from .env file if available
            import os
            try:
                from dotenv import load_dotenv
                # Load .env file from project root
                load_dotenv()
                logging.info("Loaded environment variables from .env file")
            except ImportError:
                logging.warning("dotenv module not available, skipping .env loading")
            except Exception as e:
                logging.warning(f"Error loading .env file: {e}")
                
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key:
                logging.error("OPENAI_API_KEY environment variable is not set (checked environment and .env file). Cannot run benchmark.")
                error_result = {
                    "error": "OpenAI API key is not configured. Please add it to your .env file or set the OPENAI_API_KEY environment variable.",
                    "pdf_path": str(self.pdf_path),
                    "items": 0,
                    "mean_score": 0.0,
                    "elapsed_s": 0,
                    "model_name": self.model_name
                }
                if self.on_finished and self.active:
                    self.on_finished(error_result)
                return
            
            # Dump Python sys.path to debug module import issues
            import sys
            logging.info(f"Thread {self.getName()}: Python sys.path = {sys.path}")
            
            # Try to run the benchmark
            try:
                logging.info(f"Thread {self.getName()}: About to call run_benchmark with model {self.model_name}")
                result = engine.runner.run_benchmark(self.prompts, self.pdf_path, self.model_name)
                logging.info(f"Thread {self.getName()}: run_benchmark completed successfully: {result}")
                if self.on_finished and self.active:
                    logging.info(f"Thread {self.getName()}: Calling on_finished callback with result")
                    self.on_finished(result)
                else:
                    logging.warning(f"Thread {self.getName()}: Not calling on_finished. active={self.active}, has_callback={self.on_finished is not None}")
            except Exception as e:
                # Catch any exceptions from run_benchmark
                logging.error(f"Exception in run_benchmark: {e}\n{traceback.format_exc()}")
                error_result = {
                    "error": str(e),
                    "pdf_path": str(self.pdf_path),
                    "items": 0,
                    "mean_score": 0.0,
                    "elapsed_s": 0,
                    "model_name": self.model_name
                }
                if self.on_finished and self.active:
                    self.on_finished(error_result)
        except Exception as e:
            logging.error(f"Exception in BenchmarkWorker: {e}\n{traceback.format_exc()}")
            if self.on_finished and self.active:
                error_result = {
                    "error": str(e), 
                    "pdf_path": str(self.pdf_path), 
                    "items": len(self.prompts),
                    "mean_score": 0.0,
                    "elapsed_s": 0, 
                    "model_name": self.model_name 
                }
                self.on_finished(error_result)
        finally:
            # Make sure we restore the original callback
            try:
                if self._original_emit_progress_callback is not None:
                    engine.runner.set_emit_progress_callback(self._original_emit_progress_callback)
                else:
                    engine.runner.set_emit_progress_callback(None)
            except Exception as e:
                logging.warning(f"Error restoring original callback: {e}")
            
            # Mark thread as inactive
            self.active = False

    def _emit_progress_override(self, data: dict): 
        logging.info(f"Thread {self.getName()}: Progress update: {data}")
        if self.on_progress and self.active and isinstance(data, dict):
            data['job_id'] = self.job_id
            data['benchmark_id'] = self.benchmark_id
            logging.info(f"Thread {self.getName()}: Calling on_progress callback")
            self.on_progress(data)
        else:
            logging.warning(f"Thread {self.getName()}: Not calling on_progress. active={self.active}, has_callback={self.on_progress is not None}, is_dict={isinstance(data, dict)}")
        if self._original_emit_progress_callback:
            self._original_emit_progress_callback(data)


class AppLogic:
    def __init__(self, ui_bridge: AppUIBridge):
        self.ui_bridge = ui_bridge
        self.workers = {}  # Dictionary to store workers by job_id and model_name
        self.jobs = {}     # Dictionary to store job information 
        self._next_job_id = 0
        self._current_benchmark_id = None
        self._current_benchmark_file_paths = []
        
        self._initialize_database()
        self._ensure_directories_exist()
        self._setup_data_observers()
        
        self.ui_bridge.start_auto_refresh()

    def _setup_data_observers(self):
        self.ui_bridge.register_data_callback(
            DataChangeType.BENCHMARK_LIST,
            lambda _: self._refresh_benchmark_list()
        )
        self.ui_bridge.register_data_callback(
            DataChangeType.COMPOSER_DATA,
            lambda _: self._refresh_composer_data()
        )

    def _refresh_benchmark_list(self):
        self.ui_bridge.populate_home_benchmarks_table(None) 
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())

    def _refresh_composer_data(self):
        pass

    def _initialize_database(self):
        try:
            init_file_store_db(Path.cwd())
        except Exception as e:
            print(f"Error initializing database: {e}")
            
    def handle_export_benchmark_csv(self, benchmark_id: int):
        try:
            exports_dir = Path.cwd() / "exports"
            os.makedirs(exports_dir, exist_ok=True)
            
            csv_path = export_benchmark_to_csv(benchmark_id, exports_dir)
            
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
        pass

    def request_open_csv_file(self): 
        file_path = self.ui_bridge.get_csv_file_path_via_dialog() 
        if not file_path:
            return
        
        try:
            with open(file_path, newline="", encoding='utf-8') as f:
                rows = list(csv.reader(f))
            
            self.ui_bridge.populate_composer_table(rows) 
            self.ui_bridge.show_composer_page() 
        except Exception as e:
            self.ui_bridge.show_message("critical", "CSV Error", f"Could not open or parse CSV file: {e}")

    def _get_next_job_id(self):
        job_id = self._next_job_id
        self._next_job_id += 1
        return job_id
        
    def launch_benchmark_run(self, prompts: list, pdfPath: str, modelNames: list, label: str, description: Optional[str] = "") -> dict:
        """
        Launch a benchmark run with the provided prompts, PDF file, and model(s)
        
        Args:
            prompts: List of prompt dictionaries with 'prompt_text' and 'expected_answer' keys
            pdfPath: Path to the PDF file to run the benchmark against
            modelNames: List of model names to use for this benchmark
            label: User-provided name for this benchmark
            description: Optional description for this benchmark
            
        Returns:
            dict: Information about the launched job including job_id
        """
        logging.info(f"===== LAUNCHING NEW BENCHMARK RUN =====")
        logging.info(f"Attempting to launch benchmark run with {len(prompts)} prompts, PDF: {pdfPath}, models: {modelNames}, label: {label}")
        # List all active threads to help with debugging
        active_threads = threading.enumerate()
        logging.info(f"Active threads before launch: {[t.getName() for t in active_threads]} (total: {len(active_threads)})")
        # Dump all environment variables for API key debugging
        import os
        env_vars = {k: v[:10] + '...' if k.lower().endswith('key') and v else v for k, v in os.environ.items()}
        logging.info(f"Environment variables: {env_vars}")
        
        # Convert string path to Path object
        pdf_to_run = Path(pdfPath)
            
        # Validate inputs
        if not prompts:
            self.ui_bridge.show_message("warning", "No prompts", "Please enter at least one prompt.")
            return
        if not pdf_to_run:
            self.ui_bridge.show_message("warning", "No PDF", "Please select a PDF file for the benchmark.")
            return
        if not modelNames:
            self.ui_bridge.show_message("warning", "No models", "Please select at least one model.")
            return
        
        # Ensure PDF file exists
        if not pdf_to_run.exists():
            error_msg = f"PDF file not found: {pdf_to_run}"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "PDF not found", error_msg)
            return

        # First create the benchmark in the database
        logger.info(f"Creating benchmark record with label: {label}, description: {description}")
        try:
            # Save the benchmark to get an ID
            benchmark_id = save_benchmark(label, description, file_paths=[str(pdf_to_run)])
            if not benchmark_id:
                error_msg = "Failed to create benchmark record in database"
                logger.error(error_msg)
                self.ui_bridge.show_message("error", "Database Error", error_msg)
                return
                
            # Set the current benchmark ID
            self._current_benchmark_id = benchmark_id
            self._current_benchmark_file_paths = [str(pdf_to_run)]
            
            logger.info(f"Successfully created benchmark with ID: {benchmark_id}")
        except Exception as e:
            error_msg = f"Error creating benchmark record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.ui_bridge.show_message("error", "Database Error", error_msg)
            return

        # Now create the job for tracking purposes
        job_id = self._get_next_job_id()
        self.jobs[job_id] = {
            'status': 'starting',
            'label': label,
            'description': description,
            'pdf_path': str(pdf_to_run),
            'benchmark_id': benchmark_id,  # Store the benchmark_id in the job
            'total_models': len(modelNames),
            'completed_models': 0,
            'prompts_count': len(prompts),
            'models_details': {model_name: {'status': 'pending'} for model_name in modelNames}
        }
        self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id]) 

        logger.info(f"Job {job_id} created for benchmark '{label}' (ID: {benchmark_id}) with {len(modelNames)} models.")

        for model_name in modelNames:
            on_finished_with_context = lambda result, jid=job_id, mname=model_name: self.handle_run_finished(result, job_id=jid, model_name_for_run=mname)
            on_progress_with_context = lambda progress_data, jid=job_id, mname=model_name: self.handle_benchmark_progress(jid, mname, progress_data)

            try:
                # Create a new worker and store it in the workers dictionary
                worker = BenchmarkWorker(
                    job_id=job_id,
                    benchmark_id=benchmark_id,
                    prompts=prompts,
                    pdf_path=pdf_to_run,
                    model_name=model_name, 
                    on_progress=on_progress_with_context, 
                    on_finished=on_finished_with_context  
                )
                
                # Store worker using job_id and model_name as composite key
                worker_key = f"{job_id}_{model_name}"
                self.workers[worker_key] = worker
                
                # Start the worker thread
                worker.start()
                logger.info(f"Started BenchmarkWorker for job {job_id}, model {model_name}")
            except Exception as e:
                error_msg = f"Error starting benchmark worker: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.ui_bridge.show_message("error", "Worker Error", error_msg)

        return {
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "message": "Benchmark run(s) initiated.",
            "status": "success",
            "num_models": len(modelNames),
            "num_prompts": len(prompts),
            "label": label
        }

    def handle_benchmark_progress(self, job_id: int, model_name: str, progress_data: dict):
        if job_id in self.jobs:
            self.jobs[job_id]['models_details'][model_name]['status'] = 'running'
            self.jobs[job_id]['models_details'][model_name]['progress'] = progress_data.get('progress', 0.0)
            self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id]) 

    def handle_run_finished(self, result: dict, job_id: int, model_name_for_run: str):
        worker_key = f"{job_id}_{model_name_for_run}"
        logging.info(f"handle_run_finished called for job_id={job_id}, model={model_name_for_run}, result={result}")
        
        try:
            # Check if we can find the worker
            if worker_key not in self.workers:
                error_msg = f"Worker not found for job {job_id}, model {model_name_for_run}"
                logging.error(error_msg)
                self.ui_bridge.show_message("warning", "Worker Error", error_msg)
                if job_id in self.jobs:
                    self.jobs[job_id]['status'] = 'error'
                    self._notify_benchmark_completion(job_id, None, error=error_msg)
                return

            # Get the job details
            if job_id not in self.jobs:
                error_msg = f"Job {job_id} not found"
                logging.error(error_msg)
                return
                
            job = self.jobs[job_id]
            benchmark_id = job.get('benchmark_id')
            logging.info(f"Processing completed benchmark run for benchmark_id={benchmark_id}, job_id={job_id}, model={model_name_for_run}")
            
            # Update the model status in the job
            if model_name_for_run in job['models_details']:
                job['models_details'][model_name_for_run]['status'] = 'complete' if not result.get('error') else 'error'
                job['completed_models'] = sum(1 for m in job['models_details'].values() if m.get('status') == 'complete')
                
                # Update the overall job status
                if job['completed_models'] >= job['total_models']:
                    job['status'] = 'complete'
                
                # Update the UI with the progress
                self.ui_bridge.notify_benchmark_progress(job_id, job)
{{ ... }}
                if not benchmark_id:
                    error_message = f"Benchmark ID not found for job {job_id}"
                    logger.error(error_message)
                    self.ui_bridge.show_message("error", "Database Error", error_message)
                    self._notify_benchmark_completion(job_id, None, error=error_message)
            if result.get("error"):
                error_message = f"Benchmark [{job_id}] failed: {result['error']}"
                logging.error(error_message)
                self.ui_bridge.show_message("error", "Benchmark Error", error_message)
                
                # Update the job status to error
                job['status'] = 'error'
                job['error'] = result['error']
                
                # Notify the UI about the error
                self.ui_bridge.notify_benchmark_progress(job_id, job)
                self._notify_benchmark_completion(job_id, None, error=result['error'])
            else:
                # Get benchmark_id from job
                if not benchmark_id:
                    error_message = f"Benchmark ID not found for job {job_id}"
                    logging.error(error_message)
                    self.ui_bridge.show_message("error", "Database Error", error_message)
                    self._notify_benchmark_completion(job_id, None, error=error_message)
                    return
                
                # Get the model name from the result if available, fall back to the one passed to run
                model_name = result.get('model_name', result.get('model', model_name_for_run))
                logging.info(f"Using model_name={model_name} for saving results")
                report = f"Mean score: {result.get('mean_score', 'N/A')}, Items: {result.get('items', 'N/A')}, Time: {result.get('elapsed_s', 'N/A')}s"
                latency = result.get('elapsed_s', 0.0)

                total_standard_input_tokens = result.get('total_standard_input_tokens', 0)
                total_cached_input_tokens = result.get('total_cached_input_tokens', 0)
                total_output_tokens = result.get('total_output_tokens', 0)
{{ ... }}
                total_tokens_overall = result.get('total_tokens', 0)

                # Save the benchmark run to the database
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
                        
                        standard_input_tokens_prompt = p.get('standard_input_tokens', 0)
                        cached_input_tokens_prompt = p.get('cached_input_tokens', 0)
                        output_tokens_prompt = p.get('output_tokens', 0)

                        save_benchmark_prompt(run_id, prompt, answer, response, score, latency_val, 
                                             standard_input_tokens_prompt, cached_input_tokens_prompt, output_tokens_prompt)

                    self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] run saved with DB ID: {run_id}", 5000)
                    
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

                summary_result_for_console = result.copy()
                self.ui_bridge.display_benchmark_summary_in_console(summary_result_for_console, f"Run {job_id} (DB ID: {run_id if 'run_id' in locals() else 'N/A'})")
                self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] completed.", 5000)
                
                self._notify_benchmark_completion(job_id, result)

        except Exception as e:
            logger.error(f"Error in handle_run_finished: {e}", exc_info=True)
            self.ui_bridge.show_message("error", "Error", f"An error occurred while processing benchmark result: {e}")
            
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'error'
                self._notify_benchmark_completion(job_id, None, error=str(e))
            
        finally:
            # Clean up regardless of success or failure
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'finished'
            
        # Clean up the worker reference
        worker_key = f"{job_id}_{model_name_for_run}"
        if worker_key in self.workers:
            # Set worker to inactive to prevent any further callbacks
            if self.workers[worker_key].active:
                self.workers[worker_key].active = False
            # Remove from workers dictionary
            del self.workers[worker_key]
            logger.info(f"Cleaned up worker for job {job_id}, model {model_name_for_run}")

    def _notify_benchmark_completion(self, job_id: int, result: Optional[dict], error: str = None) -> None:
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_COMPLETED, {
            'job_id': job_id,
            'success': error is None,
            'error': error,
            'result': result
        })
        
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)

    def get_active_benchmarks_info(self) -> dict:
        return {jid: data for jid, data in self.jobs.items() if data['status'] == 'unfinished'}

    def request_display_benchmark_details(self, benchmark_id): 
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
            self.ui_bridge.show_console_page() 

    def startup(self):
        self.ui_bridge.show_home_page()

    def handle_delete_benchmark(self, benchmark_id: int):
        logger.info(f"Attempting to delete benchmark with ID: {benchmark_id}")
        try:
            db_path = Path(__file__).parent 
            success = delete_benchmark(benchmark_id, db_path=db_path)
            if success:
                logger.info(f"Successfully deleted benchmark ID: {benchmark_id}")
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None) 
                self.ui_bridge.show_message("info", "Benchmark Deleted", f"Benchmark ID {benchmark_id} was successfully deleted.")
            else:
                logger.error(f"Failed to delete benchmark ID: {benchmark_id} from file_store")
                self.ui_bridge.show_message("error", "Delete Failed", f"Could not delete benchmark ID {benchmark_id}.")
        except Exception as e:
            logger.error(f"Exception during benchmark deletion for ID {benchmark_id}: {e}", exc_info=True)
            self.ui_bridge.show_message("error", "Delete Error", f"An error occurred while deleting benchmark ID {benchmark_id}: {e}")

    def handle_update_benchmark_details(self, benchmark_id: int, new_label: Optional[str] = None, new_description: Optional[str] = None):
        logger.info(f"Attempting to update details for benchmark ID: {benchmark_id}. New label: '{new_label}', New description: '{new_description}'")
        if new_label is None and new_description is None:
            self.ui_bridge.show_message("warning", "No Changes", "No new name or description provided.")
            return

        try:
            db_path = Path(__file__).parent 
            success = update_benchmark_details(benchmark_id, label=new_label, description=new_description, db_path=db_path)
            if success:
                logger.info(f"Successfully updated details for benchmark ID: {benchmark_id}")
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
                self.ui_bridge.show_message("info", "Benchmark Updated", f"Benchmark ID {benchmark_id} was successfully updated.")
            else:
                logger.error(f"Failed to update details for benchmark ID: {benchmark_id} via file_store")
                self.ui_bridge.show_message("error", "Update Failed", f"Could not update benchmark ID {benchmark_id}.")
        except Exception as e:
            logger.error(f"Exception during benchmark update for ID {benchmark_id}: {e}", exc_info=True)
            self.ui_bridge.show_message("error", "Update Error", f"An error occurred while updating benchmark ID {benchmark_id}: {e}")

    def get_active_benchmarks_info(self) -> List[Dict[str, Any]]:
        return {jid: data for jid, data in self.jobs.items() if data['status'] == 'unfinished'}
        
    def list_benchmarks(self) -> List[Dict[str, Any]]:
        """Get a list of all benchmarks from the database."""
        try:
            # Get all benchmarks from the database
            db_path = Path(__file__).parent
            benchmarks = load_all_benchmarks_with_models(db_path=db_path)
            
            # Add any active benchmarks that might not be in the database yet
            active_benchmarks = self.get_active_benchmarks_info()
            active_ids = set(active_benchmarks.keys())
            
            # Combine database benchmarks with active benchmarks
            result = []
            for benchmark in benchmarks:
                if benchmark['id'] not in active_ids:
                    result.append(benchmark)
            
            # Add active benchmarks
            for job_id, job_info in active_benchmarks.items():
                result.append({
                    'id': job_id,
                    'label': job_info.get('label', f'Benchmark {job_id}'),
                    'description': job_info.get('description', ''),
                    'models': job_info.get('models', []),
                    'status': 'running',
                    'timestamp': job_info.get('timestamp', datetime.now().isoformat())
                })
            
            return result
        except Exception as e:
            logger.error(f"Error listing benchmarks: {e}", exc_info=True)
            return []


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(json.dumps({"python_error": "Usage: python app.py <method_name> <json_kwargs>"}))
        sys.exit(1)

    method_name = sys.argv[1]
    try:
        kwargs_json = sys.argv[2]
        kwargs = json.loads(kwargs_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"python_error": f"Invalid JSON arguments: {e}"}))
        sys.exit(1)

    script_ui_bridge = ScriptUiBridge()
    app_logic = AppLogic(ui_bridge=script_ui_bridge)

    try:
        method_to_call = getattr(app_logic, method_name)
        result = method_to_call(**kwargs)
        if result is None:
            print(json.dumps({"success": True, "method": method_name}))
        elif isinstance(result, dict):
            print(json.dumps(result))
        else:
            print(json.dumps({"result": result}))
            
    except AttributeError:
        print(json.dumps({"python_error": f"AppLogic has no method named '{method_name}'"}))
        sys.exit(1)
    except TypeError as e:
        print(json.dumps({"python_error": f"Argument error for method '{method_name}': {e}"}))
        sys.exit(1)
    except Exception as e:
        import traceback
        print(json.dumps({"python_error": f"Error executing {method_name}: {e}\n{traceback.format_exc()}"}))
        sys.exit(1)