import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import os
import csv
import threading
import logging
import json # For script-based execution output
import sys
import sqlite3
import pandas as pd

# --- Basic Logger Setup ---
logger = logging.getLogger(__name__)

# Configure logging for more concise output
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s',
                    handlers=[
                        # Limit file logging to important messages only
                        logging.FileHandler("benchmark.log"),
                        # For console, ensure high visibility
                        logging.StreamHandler()
                    ])

# Set log levels for specific modules to increase visibility
logging.getLogger('runner').setLevel(logging.DEBUG)
logging.getLogger('models_openai').setLevel(logging.DEBUG)

# Import the CSV exporter
from exporter import export_benchmark_to_csv

from file_store import (
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
# Import the UI bridge protocol and data change types
from ui_bridge import AppUIBridge, DataChangeType

# --- ScriptUiBridge for command-line execution ---
class ScriptUiBridge(AppUIBridge):
    """A UI bridge that prints UI events as JSON to stdout for script-based execution."""
    def _send_event(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        # Print a blank line before JSON to ensure clean separation
        print("")
        # Format the JSON event and ensure it's on its own line
        print(json.dumps({"ui_bridge_event": event_name, "data": data or {}}))
        # Print another blank line after to further separate output
        print("")
        # Force immediate flush to prevent buffering issues
        sys.stdout.flush()

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
        super().__init__(name=f"BenchmarkWorker-{job_id}-{model_name}", daemon=True)  # Set daemon=True to prevent thread from blocking program exit
        self.job_id = job_id
        self.benchmark_id = benchmark_id
        self.prompts = prompts
        self.pdf_path = pdf_path
        self.model_name = model_name 
        self.on_progress = on_progress 
        self.on_finished = on_finished 
        self.active = True  # Single source of truth for worker state
        self._original_emit_progress_callback = None
        logging.info(f"BenchmarkWorker created: {self.name} with {len(prompts)} prompts for model {model_name}")
        
    def _validate_environment(self):
        """Validate environment variables and dependencies required for the benchmark run"""
        import os
        logging.info(f"Validating environment for model: {self.model_name}")
        
        from dotenv import load_dotenv
        load_dotenv()
        logging.info(f"Worker {self.name}: Loaded environment variables from .env file")
            
        # Check API keys based on model
        if self.model_name.startswith(("gpt-", "text-")) or "openai" in self.model_name.lower():
            # OpenAI model
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key:
                logging.error(f"Worker {self.name}: OPENAI_API_KEY environment variable is not set")
        
        elif self.model_name.startswith("gemini") or "google" in self.model_name.lower():
            # Google model
            google_key = os.environ.get('GOOGLE_API_KEY')
            if not google_key:
                logging.error(f"Worker {self.name}: GOOGLE_API_KEY environment variable is not set")
        
        # Check required packages
        required_packages = ['openai', 'tiktoken', 'PyPDF2']
        for package in required_packages:
            __import__(package)
            logging.info(f"Package {package} is available")


    def run(self):
        # Set a flag to track if we've called the completion callback
        completion_callback_called = False
        prompts_file_path = None
        
        # Add direct console output for high visibility
        print(f"\n===== BENCHMARK WORKER THREAD STARTING - {self.name} =====")
        print(f"   Model: {self.model_name}")
        print(f"   Job ID: {self.job_id}, Benchmark ID: {self.benchmark_id}")
        print(f"   PDF: {self.pdf_path}")
        print(f"   Prompts: {len(self.prompts)}")
        sys.stdout.flush()
        
        # Exit early if thread was cancelled
        if not self.active:
            logging.warning("Worker thread was cancelled before starting")
            print(f"   ❌ Worker thread was cancelled before starting")
            return
            
        # Basic validation
        print(f"   Starting basic validation checks...")
        sys.stdout.flush()
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            error_msg = f"PDF file not found: {self.pdf_path}"
            print(f"   ❌ ERROR: {error_msg}")
            sys.stdout.flush()
            
            if self.on_finished:
                self.on_finished({
                    "error": error_msg,
                    "status": "failed",
                    "job_id": self.job_id,
                    "benchmark_id": self.benchmark_id,
                    "model_name": self.model_name
                })
            return
                        
        if not self.model_name:
            error_msg = "Model name is required"
            print(f"   ❌ ERROR: {error_msg}")
            sys.stdout.flush()
            
            if self.on_finished:
                self.on_finished({
                    "error": error_msg,
                    "status": "failed",
                    "job_id": self.job_id,
                    "benchmark_id": self.benchmark_id,
                    "model_name": self.model_name
                })
            return
        
        print(f"   ✅ Basic validation passed")
        sys.stdout.flush()
        
        # Send initial progress update
        print(f"   Sending initial progress update...")
        sys.stdout.flush()
        if self.on_progress and self.active:
            self.on_progress({
                "status": "initializing",
                "message": f"Starting benchmark with model {self.model_name}",
                "progress": 0.0
            })
            print(f"   ✅ Initial progress update sent")
            sys.stdout.flush()
        else:
            print(f"   ⚠️ Warning: Progress callback not available")
            sys.stdout.flush()
        
        # Import needed modules
        import subprocess
        import json
        import tempfile
        
        # Create a temporary file for the prompts
        try:
            temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
            json.dump(self.prompts, temp_file)
            temp_file.close()
            prompts_file_path = temp_file.name
            print(f"   Wrote prompts to temporary file: {prompts_file_path}")
            sys.stdout.flush()
        except Exception as e:
            error_msg = f"Error creating temporary file: {str(e)}"
            print(f"   ❌ ERROR: {error_msg}")
            sys.stdout.flush()
            
            if self.on_finished:
                self.on_finished({
                    "error": error_msg,
                    "status": "failed",
                    "job_id": self.job_id,
                    "benchmark_id": self.benchmark_id,
                    "model_name": self.model_name
                })
            return
            
        # Path to the direct_benchmark.py script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'direct_benchmark.py')
        
        print(f"   Launching benchmark subprocess using {script_path}")
        print(f"   Running with Python interpreter: {sys.executable}")
        sys.stdout.flush()
        
        # Make sure script is executable
        if not os.access(script_path, os.X_OK):
            print(f"   Making script executable: {script_path}")
            os.chmod(script_path, 0o755)
            sys.stdout.flush()
        
        # Prepare command arguments
        cmd = [
            sys.executable,  # Use the same Python executable
            script_path,     # Path to direct_benchmark.py
            str(self.job_id),
            str(self.benchmark_id),
            prompts_file_path,  # Path to prompts JSON file
            str(self.pdf_path),
            self.model_name
        ]
    
        # Run the subprocess
        print(f"   Starting subprocess to run benchmark...")
        sys.stdout.flush()
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Process standard output lines as they arrive
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                    
                line = line.strip()
                print(f"   SUBPROCESS: {line}")
                sys.stdout.flush()
                
                # Check if line is JSON progress
                try:
                    data = json.loads(line)
                    if "ui_bridge_event" in data:
                        event_name = data["ui_bridge_event"]
                        event_data = data["data"]
                        
                        # Forward benchmark progress events
                        if event_name == "benchmark-progress" and self.on_progress:
                            self.on_progress(event_data)
                            print(f"   Forwarded progress event to UI")
                            sys.stdout.flush()
                            
                        # Forward benchmark completion events
                        if event_name == "benchmark-complete" and self.on_finished:
                            self.on_finished(event_data)
                            completion_callback_called = True
                            print(f"   Forwarded completion event to UI")
                            sys.stdout.flush()
                except json.JSONDecodeError:
                    # Not JSON, just regular output
                    pass
                except Exception as e:
                    print(f"   Error processing subprocess output: {str(e)}")
                    sys.stdout.flush()
            
            # Wait for the process to complete
            process.stdout.close()
            return_code = process.wait()
            
            # Read any remaining stderr
            stderr_output = process.stderr.read()
            process.stderr.close()
            
            if stderr_output:
                print(f"   SUBPROCESS STDERR: {stderr_output}")
                sys.stdout.flush()
            
            if return_code != 0:
                error_message = f"Benchmark subprocess exited with code {return_code}"
                print(f"   ❌ {error_message}")
                sys.stdout.flush()
                
                if self.on_finished and not completion_callback_called:
                    self.on_finished({
                        "error": error_message,
                        "status": "failed",
                        "job_id": self.job_id,
                        "benchmark_id": self.benchmark_id,
                        "model_name": self.model_name
                    })
                    completion_callback_called = True
            else:
                print(f"   ✅ Subprocess completed successfully with code {return_code}")
                sys.stdout.flush()
        except Exception as e:
            error_msg = f"Error running benchmark subprocess: {str(e)}"
            print(f"   ❌ ERROR: {error_msg}")
            sys.stdout.flush()
            
            if self.on_finished and not completion_callback_called:
                self.on_finished({
                    "error": error_msg,
                    "status": "failed",
                    "job_id": self.job_id,
                    "benchmark_id": self.benchmark_id,
                    "model_name": self.model_name
                })
                completion_callback_called = True
        
        # Clean up the temporary file
        if prompts_file_path and os.path.exists(prompts_file_path):
            try:
                print(f"   Cleaning up temporary file: {prompts_file_path}")
                os.unlink(prompts_file_path)
                sys.stdout.flush()
            except Exception as e:
                print(f"   Warning: Could not delete temporary file: {str(e)}")
                sys.stdout.flush()
        
        # Add job completion log
        logging.info(f"Thread {self.name}: Worker thread completed. Job ID: {self.job_id}, benchmark ID: {self.benchmark_id}")
        print(f"\n===== BENCHMARK WORKER THREAD COMPLETED - {self.name} =====\n")
        sys.stdout.flush()
        
        # All completion callbacks should have been handled in the subprocess processing code
        # We only need to handle the case where no callback was called yet
        if self.on_finished and self.active and not completion_callback_called:
            print(f"   Sending fallback completion callback...")
            sys.stdout.flush()
            self.on_finished({
                "status": "failed",
                "message": "Benchmark process completed but no results were returned",
                "job_id": self.job_id,
                "benchmark_id": self.benchmark_id,
                "model_name": self.model_name
            })
            print(f"   ✅ Fallback completion callback sent")
            sys.stdout.flush()
        
        # Clean up resources
        if hasattr(self, '_original_emit_progress_callback') and self._original_emit_progress_callback is not None:
            # Use the directly imported set_emit_progress_callback to restore the original callback
            from runner import set_emit_progress_callback
            set_emit_progress_callback(self._original_emit_progress_callback)
        
        # Mark thread as inactive
        self.active = False
        logging.info(f"Thread {self.name}: Finished execution")

    def _emit_progress_override(self, data: dict):
        """
        Override the default progress emitter to route through our worker's callback.
        This allows progress updates to be sent back to the main thread.
        """
        if not self.active:
            logging.warning("Worker no longer active, ignoring progress update")
            return
            
        # Log the progress update
        status = data.get('status', 'unknown')
        progress = data.get('progress', 0)
        message = data.get('message', '')
        
        logging.info(f"Thread {self.name}: Progress - {status}: {message} ({progress*100:.1f}%)")
        
        # Forward the progress update through our worker's callback
        if self.on_progress:
            # Add thread and model info to the progress data
            data.update({
                'worker_name': self.name,
                'model_name': getattr(self, 'model_name', 'unknown'),
                'benchmark_id': getattr(self, 'benchmark_id', None),
                'timestamp': datetime.now().isoformat()
            })
            self.on_progress(data)
            
            # Log the progress data at DEBUG level
            logging.debug(f"Progress update from worker {getattr(self, 'name', 'unknown')}: {data}")
            
            # Forward to the UI callback if available and worker is still active
            if hasattr(self, 'on_progress') and self.on_progress and self.active:
                self.on_progress(self.job_id, self.model_name, data)
                
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
        self._worker_cleanup_interval = 3600  # Check for inactive workers every hour
        self._last_cleanup_time = time.time()
        self.db_path = None  # Initialize db_path
        
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
        # Initialize the file store database with explicit path to ensure consistency
        db_dir = Path(__file__).parent
        logging.info(f"Using database directory: {db_dir}")
        
        # Initialize database - pass the directory, not the file path
        # Surface any errors directly to assist with debugging
        init_file_store_db(db_path=db_dir)
        
        # Verify that the database was created successfully
        db_file = db_dir / 'eotm_file_store.sqlite'
        if not db_file.exists():
            logging.error(f"Database file was not created at expected location: {db_file}")
            raise FileNotFoundError(f"Database initialization failed: {db_file} not found")
            
        logging.info(f"Database successfully initialized at: {db_file}")
        # Store DB file path for later use (e.g., CSV export)
        self.db_path = str(db_file)

    def handle_export_benchmark_csv(self, benchmark_id: int):
        exports_dir = Path.cwd() / "exports"
        os.makedirs(exports_dir, exist_ok=True)
        
        csv_path = export_benchmark_to_csv(benchmark_id, exports_dir)
        
        self.ui_bridge.show_message("Success", "CSV Export", f"Benchmark exported to:\n{csv_path}")

    def _ensure_directories_exist(self):
        files_dir = Path.cwd() / "files"
        if not files_dir.exists():
            os.makedirs(files_dir)
            print(f"Created files directory: {files_dir}")

    def _connect_signals(self):
        pass

    def request_open_csv_file(self): 
        file_path = self.ui_bridge.get_csv_file_path_via_dialog() 
        if not file_path:
            return
        
        with open(file_path, newline="", encoding='utf-8') as f:
            rows = list(csv.reader(f))
        
        self.ui_bridge.populate_composer_table(rows) 
        self.ui_bridge.show_composer_page()

    def _get_next_job_id(self):
        job_id = self._next_job_id
        self._next_job_id += 1
        return job_id
        
    def launch_benchmark_run(self, prompts: list, pdfPath: str, modelNames: list, label: str, description: Optional[str] = ""):
        """
        Launch a benchmark run with the provided prompts, PDF file, and model(s)
        
        Args:
            prompts: List of prompt dictionaries with 'prompt_text' and 'expected_answer' keys
            pdfPath: Path to the PDF file to run the benchmark against
            modelNames: List of model names to use for this benchmark
            label: User-provided name for this benchmark
            description: Optional description for this benchmark
            
        Returns:
            dict: Information about the launched job including job_id and benchmark_id
            
        Raises:
            ValueError: If any input validation fails
            FileNotFoundError: If the PDF file is not found
            RuntimeError: If there's an error creating the benchmark in the database
        """
        logger = logging.getLogger(__name__)
        logger.info(f"Launching benchmark run with {len(prompts)} prompts, PDF: {pdfPath}, models: {modelNames}")
        
        # Validate inputs
        if not prompts or not isinstance(prompts, list):
            error_msg = "No prompts provided or invalid format (expected list of prompts)"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "Invalid Input", error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "validation_error"
            }
            
        # Validate each prompt has required fields
        for i, prompt in enumerate(prompts):
            if not isinstance(prompt, dict) or 'prompt_text' not in prompt:
                error_msg = f"Prompt at index {i} is missing required 'prompt_text' field"
                logger.error(error_msg)
                self.ui_bridge.show_message("error", "Invalid Prompt", error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "error_type": "validation_error"
                }
        
        # Convert to Path and validate
        pdf_to_run = Path(pdfPath).resolve() if pdfPath else None
            
        if not pdf_to_run:
            error_msg = "No PDF file selected"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "No PDF Selected", error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "validation_error"
            }
            
        if not pdf_to_run.exists():
            error_msg = f"PDF file not found: {pdf_to_run}"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "PDF not found", error_msg)
            raise FileNotFoundError(error_msg)
            
        if not modelNames:
            error_msg = "No models selected"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "No Models Selected", error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "validation_error"
            }
        
        # Check for OpenAI API key since most benchmarks use it
        # Load from .env file if present
        from dotenv import load_dotenv
        load_dotenv()
        logging.info("Loaded environment variables from .env file")
        
        openai_key = os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            error_msg = "OPENAI_API_KEY environment variable is not set. Required for running benchmarks."
            logging.error(error_msg)
            self.ui_bridge.show_message("error", "API Key Missing", 
                                      "OpenAI API key is not configured. Please add it to your .env file or set the OPENAI_API_KEY environment variable.")
            return {
                "status": "error",
                "message": "OpenAI API key is missing"
            }
        
        # Convert string path to Path object
        pdf_to_run = Path(pdfPath)
            
        # Validate inputs
        if not prompts:
            self.ui_bridge.show_message("warning", "No prompts", "Please enter at least one prompt.")
            return {
                "status": "error",
                "message": "No prompts provided"
            }
            
        if not pdf_to_run:
            self.ui_bridge.show_message("warning", "No PDF", "Please select a PDF file for the benchmark.")
            return {
                "status": "error",
                "message": "No PDF file selected"
            }
            
        if not modelNames:
            self.ui_bridge.show_message("warning", "No models", "Please select at least one model.")
            return {
                "status": "error",
                "message": "No models selected"
            }
        
        # Ensure PDF file exists
        if not pdf_to_run.exists():
            error_msg = f"PDF file not found: {pdf_to_run}"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "PDF not found", error_msg)
            return {
                "status": "error",
                "message": error_msg
            }

        # First create the benchmark in the database
        logger.info(f"Creating benchmark record with label: {label}, description: {description}")
        
        # Use consistent database path - same as in _initialize_database
        db_dir = Path(__file__).parent
        db_path = db_dir / 'eotm_file_store.sqlite'
        logger.info(f"Using database at: {db_path} for saving benchmark")
        
        # Ensure database directory exists
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database if it doesn't exist
        from file_store import init_db
        init_db(db_dir)
        
        # Save the benchmark to get an ID - let errors propagate naturally
        from file_store import save_benchmark
        benchmark_id = save_benchmark(
            label=label,
            description=description or "",
            file_paths=[str(pdf_to_run)],
            db_path=db_dir
        )
        
        if not benchmark_id:
            error_msg = "Failed to create benchmark record in database"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        logger.info(f"Successfully created benchmark with ID: {benchmark_id}")
        
        # Set the current benchmark ID
        self._current_benchmark_id = benchmark_id
        self._current_benchmark_file_paths = [str(pdf_to_run)]
        
        logger.info(f"Successfully created benchmark with ID: {benchmark_id}")

        # Now create the job for tracking purposes
        job_id = self._get_next_job_id()
        
        # Initialize the job tracking structure
        self.jobs[job_id] = {
            'status': 'starting',
            'label': label,
            'description': description,
            'pdf_path': str(pdf_to_run),
            'benchmark_id': benchmark_id,
            'total_models': len(modelNames),
            'completed_models': 0,
            'prompts_count': len(prompts),
            'start_time': datetime.now().isoformat(),
            'models_details': {model_name: {'status': 'pending', 'start_time': None, 'end_time': None} for model_name in modelNames}
        }
        
        # Notify UI about the new job
        self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id]) 
        logger.info(f"Job {job_id} created for benchmark '{label}' (ID: {benchmark_id}) with {len(modelNames)} models.")
        
        # Register all models in the database right away so they show up in the UI
        # This ensures models appear in listings even before any results are saved
        from file_store import update_benchmark_model
        for model_name in modelNames:
            update_benchmark_model(benchmark_id, model_name, db_dir)
            logger.info(f"Registered model {model_name} in database for benchmark {benchmark_id}")
        
        # Start a worker thread for each model
        for model_name in modelNames:
            logger.info(f"Starting worker for model: {model_name}")
            
            # Register model in the database right away so it shows up in the UI
            # This ensures models appear in listings even before any results are saved
            from file_store import update_benchmark_model
            update_benchmark_model(benchmark_id, model_name, db_dir)
            logger.info(f"Registered model {model_name} in database for benchmark {benchmark_id}")
            
            # Create callbacks with proper context
            def create_finished_callback(jid, mname):
                return lambda result: self.handle_run_finished(result, job_id=jid, model_name_for_run=mname)
                
            def create_progress_callback(jid, mname):
                return lambda progress_data: self.handle_benchmark_progress(jid, mname, progress_data)
            
            # Create worker with callbacks
            worker = BenchmarkWorker(
                job_id=job_id,
                benchmark_id=benchmark_id,
                prompts=prompts,
                pdf_path=pdf_to_run,
                model_name=model_name, 
                on_progress=create_progress_callback(job_id, model_name),
                on_finished=create_finished_callback(job_id, model_name)
            )
            
            # Store worker using job_id and model_name as composite key
            worker_key = f"{job_id}_{model_name}"
            self.workers[worker_key] = worker
            
            # Start the worker thread
            worker.start()
        
        # Ensure clean output separation with a blank line
        print("")
        sys.stdout.flush()
        
        # Return success response with job and benchmark info
        result = {
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "message": "Benchmark run(s) initiated.",
            "status": "success",
            "num_models": len(modelNames),
            "num_prompts": len(prompts),
            "label": label
        }
        # Log the result for debugging purposes
        logging.info(f"Returning result: {result}")
        sys.stdout.flush()
        return result
                    
    def handle_export_benchmark_csv(self, benchmark_id: int, filename: str) -> dict:
        """
        Handle the export of benchmark results to a CSV file
        
        Args:
            benchmark_id: ID of the benchmark to export
            filename: Path where the CSV file should be saved
            
        Returns:
            dict: Status and details of the export operation
            
        Raises:
            ValueError: If the benchmark is not found in the database
            Exception: For any other errors during export
        """
        logging.info(f"Exporting benchmark {benchmark_id} to {filename}")
        
        # Get the benchmark results from the database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Get the most recent run for this benchmark
            cursor.execute("""
                SELECT id, model_name, created_at,
                       total_standard_input_tokens, total_cached_input_tokens,
                       total_output_tokens, total_tokens, latency, report
                FROM benchmark_runs
                WHERE benchmark_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (benchmark_id,))
             
            benchmark = cursor.fetchone()
            if not benchmark:
                error_msg = f"Benchmark with ID {benchmark_id} not found"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
            # Derive run ID for prompts
            run_id = benchmark[0]
            
            # Get all prompt results dynamically to match DB schema
            cursor.execute("""
                SELECT * FROM benchmark_prompts
                WHERE benchmark_run_id = ?
                ORDER BY id
            """, (run_id,))
            rows = cursor.fetchall()
            # Construct DataFrame using actual column names
            cols = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(rows, columns=cols)
            # Normalize prompt/answer columns to standard names
            rename_map = {}
            if 'prompt' in df.columns:
                rename_map['prompt'] = 'prompt_text'
            elif 'prompt_preview' in df.columns:
                rename_map['prompt_preview'] = 'prompt_text'
            if 'answer' in df.columns:
                rename_map['answer'] = 'expected_answer'
            elif 'answer_preview' in df.columns:
                rename_map['answer_preview'] = 'expected_answer'
            if 'response' in df.columns:
                rename_map['response'] = 'actual_answer'
            # Apply renaming
            df.rename(columns=rename_map, inplace=True)
            # Only keep relevant columns in order
            cols_order = ['prompt_text', 'expected_answer', 'actual_answer', 'score', 'latency',
                          'standard_input_tokens', 'cached_input_tokens', 'output_tokens']
            cols_to_export = [c for c in cols_order if c in df.columns]
            df = df[cols_to_export]
             
            # Ensure the directory exists (skip if saving to current dir)
            dirpath = os.path.dirname(filename)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
             
            # Save to CSV
            df.to_csv(filename, index=False)
            logging.info(f"Successfully exported {len(df)} prompt results to {filename}")
             
            # Return summary info
            return {
                'status': 'success',
                'filename': filename,
                'benchmark_id': benchmark_id,
                'num_prompts': len(df),
                'model_name': benchmark[1],
                'created_at': benchmark[2]
            }

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
        logging.info(f"===== HANDLE_RUN_FINISHED CALLED =====")
        logging.info(f"Job ID: {job_id}, Model: {model_name_for_run}, Worker key: {worker_key}")
        
        # First, log detailed information about the result
        if isinstance(result, dict):
            logging.info(f"Result is a dictionary with keys: {list(result.keys())}")
            if 'mean_score' in result:
                logging.info(f"Mean score: {result['mean_score']}")
            if 'items' in result:
                logging.info(f"Items processed: {result['items']}")
            if 'error' in result:
                logging.error(f"Error in result: {result['error']}")
        else:
            logging.warning(f"Result is not a dictionary but a {type(result).__name__}")
        
        # Register that this function was called for this job/model combination
        logging.info(f"Registering completion for job {job_id}, model {model_name_for_run}")
        
        # Always mark the worker as completed in the job record, regardless of success/failure
        if job_id in self.jobs and model_name_for_run in self.jobs[job_id]['models_details']:
            # Update end time
            self.jobs[job_id]['models_details'][model_name_for_run]['end_time'] = datetime.now().isoformat()
            logging.info(f"Updated end time for job {job_id}, model {model_name_for_run}")
        
        # Check if the result contains an error
        if result and result.get('error'):
            error_msg = f"Error in benchmark run for model {model_name_for_run}: {result.get('error')}"
            logging.error(error_msg)
            self.ui_bridge.show_message("error", "Benchmark Error", error_msg)
            
            # Still process the error so it's recorded properly
            if job_id in self.jobs:
                self.jobs[job_id]['models_details'][model_name_for_run]['status'] = 'error'
                self.jobs[job_id]['models_details'][model_name_for_run]['error'] = error_msg
                self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id])
                logging.info(f"Updated job status for error condition")
        
        # If worker key isn't in the workers dictionary, log but continue processing
        # (the worker might have been removed but we still want to process its result)
        if worker_key not in self.workers:
            warning_msg = f"Worker not found for job {job_id}, model {model_name_for_run} - it may have been removed already"
            logging.warning(warning_msg)

        # Get the job details
        if job_id not in self.jobs:
            error_msg = f"Job {job_id} not found in jobs dictionary"
            logging.error(error_msg)
            return
            
        job = self.jobs[job_id]
        benchmark_id = job.get('benchmark_id')
        logging.info(f"Processing completed benchmark run for benchmark_id={benchmark_id}, job_id={job_id}, model={model_name_for_run}")
        
        # Ensure the result is valid
        if not result:
            error_msg = f"Empty result returned for job {job_id}, model {model_name_for_run}"
            logging.error(error_msg)
            if job_id in self.jobs:
                self.jobs[job_id]['models_details'][model_name_for_run]['status'] = 'error'
                self.jobs[job_id]['models_details'][model_name_for_run]['error'] = error_msg
                self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id])
            return
        
        # Update the model status in the job
        if model_name_for_run in job['models_details']:
            logging.info(f"Updating status for model {model_name_for_run} in job {job_id}")
            # Set status based on whether there was an error
            job['models_details'][model_name_for_run]['status'] = 'complete' if not result.get('error') else 'error'
            
            # Count completed models (only those with 'complete' status)
            job['completed_models'] = sum(1 for m in job['models_details'].values() if m.get('status') == 'complete')
            logging.info(f"Job {job_id} has {job['completed_models']} of {job['total_models']} models completed successfully")
                
            # Update the overall job status
            if job['completed_models'] >= job['total_models']:
                job['status'] = 'complete'
                logging.info(f"All models for job {job_id} are now complete!")
                
            # Update the UI with the progress - this is critical for the UI to show updates
            self.ui_bridge.notify_benchmark_progress(job_id, job)
            logging.info(f"Sent UI update notification for job {job_id}")

            # Handle error case first - if the result has an error field
            if result.get("error"):
                error_message = f"Benchmark [{job_id}] failed for model {model_name_for_run}: {result['error']}"
                logging.error(error_message)
                self.ui_bridge.show_message("error", "Benchmark Error", error_message)
                
                # Update the job status to error
                job['status'] = 'error'
                job['error'] = result['error']
                
                # Notify the UI about the error
                self.ui_bridge.notify_benchmark_progress(job_id, job)
                self._notify_benchmark_completion(job_id, None, error=result['error'])
                logging.info(f"Notified UI of benchmark error for job {job_id}")
                return  # Exit early as there's no successful result to process
            
            # Success case - process the successful result
            # Double check we have a benchmark ID
            if not benchmark_id:
                error_message = f"Benchmark ID not found for job {job_id}"
                logging.error(error_message)
                self.ui_bridge.show_message("error", "Database Error", error_message)
                self._notify_benchmark_completion(job_id, None, error=error_message)
                return
                
            # Get the model name from the result if available, fall back to the one passed to run
            model_name = result.get('model_name', result.get('model', model_name_for_run))
            logging.info(f"Using model_name={model_name} for saving results")
                
            # Create a report summary
            report = f"Mean score: {result.get('mean_score', 'N/A')}, Items: {result.get('items', 'N/A')}, Time: {result.get('elapsed_s', 'N/A')}s"
            logging.info(f"Benchmark summary: {report}")
            latency = result.get('elapsed_s', 0.0)

            total_standard_input_tokens = result.get('total_standard_input_tokens', 0)
            total_cached_input_tokens = result.get('total_cached_input_tokens', 0)
            total_output_tokens = result.get('total_output_tokens', 0)

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

        # Get consistent database directory path
        db_dir = Path(__file__).parent
        details = load_benchmark_details(benchmark_id, db_path=db_dir)
        if details:
            self.ui_bridge.display_full_benchmark_details_in_console(details)
            self.ui_bridge.show_console_page()
        else:
            self.ui_bridge.show_message("warning", "Error", f"Could not load details for benchmark ID: {benchmark_id}")
            self.ui_bridge.clear_console_log()
            self.ui_bridge.update_console_log(f"Failed to load details for benchmark ID: {benchmark_id}")
            self.ui_bridge.show_console_page() 

    def _cleanup_inactive_workers(self):
        """Cleanup inactive worker threads to prevent memory leaks"""
        current_time = time.time()
        # Only run cleanup periodically
        if current_time - self._last_cleanup_time < self._worker_cleanup_interval:
            return
            
        self._last_cleanup_time = current_time
        logging.info("Performing cleanup of inactive workers")
        
        # Keep track of worker keys to remove
        workers_to_remove = []
        
        # Check each worker
        for worker_key, worker in self.workers.items():
            if not worker.is_alive() or not worker.active:
                logging.info(f"Cleaning up inactive worker: {worker_key} (alive={worker.is_alive()}, active={worker.active})")
                workers_to_remove.append(worker_key)
        
        # Remove inactive workers from the dictionary
        for key in workers_to_remove:
            logging.info(f"Removing worker {key} from workers dictionary")
            del self.workers[key]
        
        # Print a summary of the cleanup
        logging.info(f"Worker cleanup complete. Removed {len(workers_to_remove)} workers. {len(self.workers)} still active.")

    def startup(self):
        """Initialize the application"""
        # Clean up any inactive workers from previous sessions

    def handle_delete_benchmark(self, benchmark_id: int) -> dict:
        """Delete a benchmark and all its associated data.
        
        Args:
            benchmark_id: The ID of the benchmark to delete
            
        Returns:
            dict: A response with at least a 'success' field indicating whether the operation succeeded
        """
        logger.info(f"Attempting to delete benchmark with ID: {benchmark_id}")
        db_path = Path(__file__).parent 
        success = delete_benchmark(benchmark_id, db_path=db_path)
        if success:
            logger.info(f"Successfully deleted benchmark ID: {benchmark_id}")
            self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None) 
            self.ui_bridge.show_message("info", "Benchmark Deleted", f"Benchmark ID {benchmark_id} was successfully deleted.")
            return {"success": True, "message": f"Benchmark ID {benchmark_id} was successfully deleted."}
        else:
            error_msg = f"Failed to delete benchmark ID: {benchmark_id} via file_store"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "Delete Failed", f"Could not delete benchmark ID {benchmark_id}.")
            return {"success": False, "error": error_msg}

    def handle_update_benchmark_details(self, benchmark_id: int, new_label: Optional[str] = None, new_description: Optional[str] = None) -> dict:
        """Update the label and/or description of a benchmark.
        
        Args:
            benchmark_id: The ID of the benchmark to update
            new_label: The new label for the benchmark (optional)
            new_description: The new description for the benchmark (optional)
            
        Returns:
            dict: A response with at least a 'success' field indicating whether the operation succeeded
        """
        logger.info(f"Attempting to update details for benchmark ID: {benchmark_id}. New label: '{new_label}', New description: '{new_description}'")
        if new_label is None and new_description is None:
            self.ui_bridge.show_message("warning", "No Changes", "No new name or description provided.")
            return {"success": False, "error": "No new name or description provided."}

        db_path = Path(__file__).parent 
        success = update_benchmark_details(benchmark_id, label=new_label, description=new_description, db_path=db_path)
        if success:
            logger.info(f"Successfully updated details for benchmark ID: {benchmark_id}")
            self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
            self.ui_bridge.show_message("info", "Benchmark Updated", f"Benchmark ID {benchmark_id} was successfully updated.")
            return {"success": True, "message": f"Benchmark ID {benchmark_id} was successfully updated."}
        else:
            error_msg = f"Failed to update details for benchmark ID: {benchmark_id} via file_store"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "Update Failed", f"Could not update benchmark ID {benchmark_id}.")
            return {"success": False, "error": error_msg}

    def get_active_benchmarks_info(self) -> List[Dict[str, Any]]:
        return {jid: data for jid, data in self.jobs.items() if data['status'] == 'unfinished'}
        
    def list_benchmarks(self) -> List[Dict[str, Any]]:
        """Get a list of all benchmarks from the database."""
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
    except (AttributeError, TypeError) as e:
        print(json.dumps({"python_error": str(e)}))
        sys.exit(1)