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

# Increase CSV field size limit to handle large web search data
csv.field_size_limit(500000)  # 500KB limit for large web search data

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
# logging.getLogger('runner').setLevel(logging.DEBUG)
logging.getLogger('models_openai').setLevel(logging.DEBUG)

# Import the CSV exporter
# from exporter import export_benchmark_to_csv

from file_store import (
    init_db as init_file_store_db,
    save_benchmark,
    save_benchmark_run,
    save_benchmark_prompt_atomic,
    load_benchmark_details,
    find_benchmark_by_files,
    delete_benchmark,
    update_benchmark_details,
    load_all_benchmarks_with_models,
    create_prompt_set,
    get_all_prompt_sets,
    get_prompt_set,
    update_prompt_set,
    delete_prompt_set,
    get_next_prompt_set_number,
    register_file,
    get_all_files,
    get_file_details,
    delete_file
)
# Import the UI bridge protocol and data change types
from ui_bridge import AppUIBridge, DataChangeType
from token_validator import validate_token_limits, format_token_validation_message

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
    def __init__(self, job_id, benchmark_id, prompts, pdf_paths, model_name, on_progress=None, on_finished=None, web_search_enabled=False): 
        super().__init__(name=f"BenchmarkWorker-{job_id}-{model_name}", daemon=True)  # Set daemon=True to prevent thread from blocking program exit
        self.job_id = job_id
        self.benchmark_id = benchmark_id
        self.prompts = prompts
        self.pdf_paths = pdf_paths
        self.model_name = model_name
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.web_search_enabled = web_search_enabled
        self.active = True  # Single source of truth for worker state
        self._original_emit_progress_callback = None
        
        print(f"BenchmarkWorker initialized with job_id={job_id}, benchmark_id={benchmark_id}, model={model_name}, web_search_enabled={web_search_enabled}")
        sys.stdout.flush()
        logging.info(f"BenchmarkWorker created: {self.name} with {len(prompts)} prompts for model {model_name}")
     

    def run(self):
        # Set a flag to track if we've called the completion callback
        completion_callback_called = False
        prompts_file_path = None
        
        # Add direct console output for high visibility
        print(f"\n===== BENCHMARK WORKER THREAD STARTING - {self.name} =====")
        print(f"   Model: {self.model_name}")
        print(f"   Job ID: {self.job_id}, Benchmark ID: {self.benchmark_id}")
        print(f"   PDFs: {self.pdf_paths}")
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
        
        # Validate PDF paths if any were provided
        if self.pdf_paths:
            for pdf_path in self.pdf_paths:
                if not os.path.exists(pdf_path):
                    error_msg = f"PDF file not found: {pdf_path}"
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
            self.model_name,
            str(self.web_search_enabled).lower()  # Pass web_search_enabled as string 'true'/'false'
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
        
        # # Clean up resources
        # if hasattr(self, '_original_emit_progress_callback') and self._original_emit_progress_callback is not None:
        #     # Use the directly imported set_emit_progress_callback to restore the original callback
        #     from runner import set_emit_progress_callback
        #     set_emit_progress_callback(self._original_emit_progress_callback)
        
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
        db_file = db_dir / 'eotb_file_store.sqlite'
        if not db_file.exists():
            logging.error(f"Database file was not created at expected location: {db_file}")
            raise FileNotFoundError(f"Database initialization failed: {db_file} not found")
            
        logging.info(f"Database successfully initialized at: {db_file}")
        # Store DB file path for later use (e.g., CSV export)
        self.db_path = str(db_file)

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
        
    def launch_benchmark_run(self, prompts: list, pdfPaths: list, modelNames: list, label: str, description: Optional[str] = "", webSearchEnabled: bool = False):
        """
        Launch a benchmark run with the provided prompts, PDF files, and model(s)
        
        Args:
            prompts: List of prompt dictionaries with 'prompt_text' keys
            pdfPaths: List of paths to PDF files to run the benchmark against
            modelNames: List of model names to use for this benchmark
            label: User-provided name for this benchmark
            description: Optional description for this benchmark
            webSearchEnabled: Whether to enable web search for this benchmark
            
        Returns:
            dict: Information about the launched job including job_id and benchmark_id
            
        Raises:
            ValueError: If any input validation fails
            FileNotFoundError: If any PDF file is not found
            RuntimeError: If there's an error creating the benchmark in the database
        """
        logger = logging.getLogger(__name__)
        logger.info(f"Launching benchmark run with {len(prompts)} prompts, PDFs: {pdfPaths}, models: {modelNames}")
        
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
        
        # Convert to Path objects and validate if PDFs are provided
        pdfs_to_run = []
        if pdfPaths and isinstance(pdfPaths, list):
            for pdfPath in pdfPaths:
                if pdfPath and str(pdfPath).strip():  # Only process if pdfPath is not empty
                    pdf_path = Path(pdfPath).resolve()
                    if not pdf_path.exists():
                        error_msg = f"PDF file not found: {pdf_path}"
                        logger.error(error_msg)
                        self.ui_bridge.show_message("error", "PDF not found", error_msg)
                        raise FileNotFoundError(error_msg)
                    pdfs_to_run.append(pdf_path)
            
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
        
        # Convert string path to Path object if provided
        pdf_to_run = Path(pdfPaths[0]) if pdfPaths and str(pdfPaths[0]).strip() else None
            
        # Validate inputs
        if not prompts:
            self.ui_bridge.show_message("warning", "No prompts", "Please enter at least one prompt.")
            return {
                "status": "error",
                "message": "No prompts provided"
            }
            
        # PDF is now optional, so we only validate if one was provided
        if pdf_to_run and not pdf_to_run.exists():
            error_msg = f"PDF file not found: {pdf_to_run}"
            logger.error(error_msg)
            self.ui_bridge.show_message("error", "PDF not found", error_msg)
            return {
                "status": "error",
                "message": error_msg
            }
            
        if not modelNames:
            self.ui_bridge.show_message("warning", "No models", "Please select at least one model.")
            return {
                "status": "error",
                "message": "No models selected"
            }
        
        # PDF validation already done above

        # First create the benchmark in the database
        logger.info(f"Creating benchmark record with label: {label}, description: {description}")
        
        # Use consistent database path - same as in _initialize_database
        db_dir = Path(__file__).parent
        db_path = db_dir / 'eotb_file_store.sqlite'
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
            file_paths=[str(pdf_path) for pdf_path in pdfs_to_run],
            intended_models=modelNames,  # Store the intended models
            use_web_search=webSearchEnabled,  # Pass web search flag
            db_path=db_dir
        )
        
        if not benchmark_id:
            error_msg = "Failed to create benchmark record in database"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        logger.info(f"Successfully created benchmark with ID: {benchmark_id}")
        
        # Set the current benchmark ID
        self._current_benchmark_id = benchmark_id
        self._current_benchmark_file_paths = [str(pdf_path) for pdf_path in pdfs_to_run]
        
        logger.info(f"Successfully created benchmark with ID: {benchmark_id}")

        # Now create the job for tracking purposes
        job_id = self._get_next_job_id()
        
        # Initialize the job tracking structure
        self.jobs[job_id] = {
            'status': 'starting',
            'label': label,
            'description': description,
            'pdf_paths': self._current_benchmark_file_paths,
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
                pdf_paths=pdfs_to_run,
                model_name=model_name, 
                on_progress=create_progress_callback(job_id, model_name),
                on_finished=create_finished_callback(job_id, model_name),
                web_search_enabled=webSearchEnabled
            )
            
            # Store worker using job_id and model_name as composite key
            worker_key = f"{job_id}_{model_name}"
            self.workers[worker_key] = worker
            
            # Start the worker thread
            worker.start()
        
        # Ensure clean output separation with a blank line
        print("")
        sys.stdout.flush()
        
        # Construct the benchmark item for optimistic UI update
        launched_benchmark_item = {
            'id': benchmark_id,
            'label': label,
            'description': description,
            'model_names': modelNames, # This is the list of model names
            'status': 'running', # Optimistically set to running
            'timestamp': self.jobs[job_id]['start_time'], # Already in isoformat
            'file_paths': self._current_benchmark_file_paths # The PDF paths used for the launch
            # Add any other fields the frontend expects for a benchmark list item
        }

        # Return success response with job and benchmark info, including the item
        result = {
            "job_id": job_id,
            "benchmark_id": benchmark_id,
            "message": "Benchmark run(s) initiated.",
            "status": "success",
            "num_models": len(modelNames),
            "num_prompts": len(prompts),
            "label": label,
            "launched_benchmark_item": launched_benchmark_item # Add the new item here
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
            
            # First check if the benchmark exists and get file information
            cursor.execute("""
                SELECT b.id, b.label, b.description, 
                       GROUP_CONCAT(f.original_filename, '; ') as file_names,
                       COUNT(f.id) as file_count
                FROM benchmarks b
                LEFT JOIN benchmark_files bf ON b.id = bf.benchmark_id
                LEFT JOIN files f ON bf.file_id = f.id
                WHERE b.id = ?
                GROUP BY b.id
            """, (benchmark_id,))
            
            benchmark_info = cursor.fetchone()
            if not benchmark_info:
                error_msg = f"Benchmark with ID {benchmark_id} not found"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
            benchmark_label = benchmark_info[1] or f"Benchmark {benchmark_id}"
            file_names = benchmark_info[3] or "No files"
            file_count = benchmark_info[4] or 0
            
            # Get all runs for this benchmark (different models)
            cursor.execute("""
                SELECT id, model_name, provider, created_at
                FROM benchmark_runs
                WHERE benchmark_id = ?
                ORDER BY model_name, created_at DESC
            """, (benchmark_id,))
            
            runs = cursor.fetchall()
            if not runs:
                error_msg = f"No runs found for benchmark with ID {benchmark_id}"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
            # Create a map of model_name -> newest run_id
            run_ids_by_model = {}
            for run_id, model_name, provider, created_at in runs:
                if model_name not in run_ids_by_model:
                    run_ids_by_model[model_name] = {
                        'run_id': run_id,
                        'provider': provider,
                        'created_at': created_at
                    }
            
            # Collect all prompt data into a single DataFrame
            all_prompts_data = []
            model_names = []
            
            for model_name, run_info in run_ids_by_model.items():
                model_names.append(model_name)
                run_id = run_info['run_id']
                provider = run_info['provider']
                
                # Get prompt data for this run
                cursor.execute("""
                    SELECT *
                    FROM benchmark_prompts
                    WHERE benchmark_run_id = ?
                    ORDER BY id
                """, (run_id,))
                
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description]
                
                if rows:
                    # Process each row to add model name and standardize column names
                    for row in rows:
                        row_dict = dict(zip(cols, row))
                        
                        # Add benchmark metadata
                        row_dict['benchmark_name'] = benchmark_label
                        row_dict['model_name'] = model_name
                        row_dict['provider'] = provider
                        row_dict['files_used'] = file_names
                        row_dict['file_count'] = file_count
                        
                        # Add formatted model display name
                        if model_name.endswith('-thinking'):
                            base_model = model_name.replace('-thinking', '')
                            row_dict['model_display_name'] = f"{base_model} (+ Thinking)"
                        else:
                            row_dict['model_display_name'] = model_name
                        
                        # Standardize column names for CSV export
                        if 'prompt' in row_dict:
                            row_dict['prompt_text'] = row_dict.pop('prompt')
                        elif 'prompt_preview' in row_dict:
                            row_dict['prompt_text'] = row_dict.pop('prompt_preview')
                            
                        if 'response' in row_dict:
                            row_dict['model_answer'] = row_dict.pop('response')
                            
                        # Ensure all token columns exist (for older databases)
                        row_dict['thinking_tokens'] = row_dict.get('thinking_tokens', 0) or 0
                        row_dict['reasoning_tokens'] = row_dict.get('reasoning_tokens', 0) or 0
                        row_dict['thinking_cost'] = row_dict.get('thinking_cost', 0.0) or 0.0
                        row_dict['reasoning_cost'] = row_dict.get('reasoning_cost', 0.0) or 0.0
                            
                        all_prompts_data.append(row_dict)
            
            # Convert to DataFrame
            if not all_prompts_data:
                error_msg = f"No prompt data found for benchmark with ID {benchmark_id}"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            df = pd.DataFrame(all_prompts_data)
            logging.info(f"DataFrame columns before filtering: {list(df.columns)}")
            
            # Define comprehensive column order including thinking/reasoning tokens and file info
            cols_order = [
                # Metadata
                'benchmark_name', 'model_name', 'provider', 'files_used', 'file_count',
                # Content
                'prompt_text', 'model_answer', 'latency',
                # Token breakdown
                'standard_input_tokens', 'cached_input_tokens', 'output_tokens',
                'thinking_tokens', 'reasoning_tokens',
                # Cost breakdown  
                'input_cost', 'cached_cost', 'output_cost', 
                'thinking_cost', 'reasoning_cost', 'total_cost',
                # Web search
                'web_search_used', 'web_search_sources',
                # New formatted model display name
                'model_display_name'
            ]
            
            # Only keep relevant columns in order
            cols_to_export = [c for c in cols_order if c in df.columns]
            logging.info(f"Columns to export: {cols_to_export}")
            df = df[cols_to_export]
            
            # Convert web_search_used from 1/0 to True/False for better readability
            if 'web_search_used' in df.columns:
                df['web_search_used'] = df['web_search_used'].map({1: 'True', 0: 'False', '1': 'True', '0': 'False'})
             
            # Ensure the directory exists (skip if saving to current dir)
            dirpath = os.path.dirname(filename)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
             
            # Save to CSV
            df.to_csv(filename, index=False)
            logging.info(f"Successfully exported {len(df)} prompt results for {len(model_names)} models to {filename}")
             
            # Return summary info
            return {
                'status': 'success',
                'filename': filename,
                'benchmark_id': benchmark_id,
                'benchmark_name': benchmark_label,
                'files_used': file_names,
                'file_count': file_count,
                'num_prompts': len(df) // len(model_names) if len(model_names) > 0 else 0,
                'model_names': model_names,
                'num_models': len(model_names)
            }

    def handle_benchmark_progress(self, job_id: int, model_name: str, progress_data: dict):
        if job_id in self.jobs:
            self.jobs[job_id]['models_details'][model_name]['status'] = 'running'
            self.jobs[job_id]['models_details'][model_name]['progress'] = progress_data.get('progress', 0.0)
            
            # Handle prompt completion events for real-time updates
            if progress_data.get('status') == 'prompt_complete':
                # A prompt has completed - trigger a UI refresh for the benchmark details
                benchmark_id = self.jobs[job_id].get('benchmark_id')
                if benchmark_id:
                    logging.info(f"Prompt {progress_data.get('prompt_index', 0) + 1} completed for model {model_name} in benchmark {benchmark_id}")
                    
                    # Notify the UI that benchmark data has changed
                    self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_DETAILS, {
                        'benchmark_id': benchmark_id,
                        'job_id': job_id,
                        'model_name': model_name,
                        'prompt_completed': True,
                        'prompt_index': progress_data.get('prompt_index', 0),
                        'total_prompts': progress_data.get('total_prompts', 0)
                    })
                    
                    # Also update the progress counter
                    completed_prompts = progress_data.get('prompt_index', 0) + 1
                    total_prompts = progress_data.get('total_prompts', 1)
                    progress_percentage = (completed_prompts / total_prompts) * 100
                    self.jobs[job_id]['models_details'][model_name]['progress'] = progress_percentage
                    
                    logging.info(f"Updated progress for {model_name}: {completed_prompts}/{total_prompts} prompts ({progress_percentage:.1f}%)")
            
            # REMOVED: This line was causing infinite loop by re-emitting progress events
            # self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id])

    def handle_run_finished(self, result: dict, job_id: int, model_name_for_run: str):
        worker_key = f"{job_id}_{model_name_for_run}"
        logging.info(f"===== HANDLE_RUN_FINISHED CALLED =====")
        logging.info(f"Job ID: {job_id}, Model: {model_name_for_run}, Worker key: {worker_key}")
        
        # First, log detailed information about the result
        if isinstance(result, dict):
            logging.info(f"Result is a dictionary with keys: {list(result.keys())}")
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
                # Update benchmark status in database when all models are complete
                from file_store import update_benchmark_status
                update_benchmark_status(benchmark_id, 'complete')
                
                # Only notify about benchmark completion when ALL models have finished
                # We'll save the notification until the end of this method for single-model benchmarks
                if job['total_models'] > 1:
                    self._notify_benchmark_completion(job_id, result)
            else:
                # Job is still in progress with some models pending
                logging.info(f"Job {job_id} is still in progress: {job['completed_models']}/{job['total_models']} models done")
            
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
            report = f"Items: {result.get('items', 'N/A')}, Time: {result.get('elapsed_s', 'N/A')}s"
            logging.info(f"Benchmark summary: {report}")
            # Convert latency from seconds to milliseconds for database storage consistency
            latency = (result.get('elapsed_s', 0.0) * 1000)  # Convert seconds to milliseconds

            total_standard_input_tokens = result.get('total_standard_input_tokens', 0)
            total_cached_input_tokens = result.get('total_cached_input_tokens', 0)
            total_output_tokens = result.get('total_output_tokens', 0)
            total_cost = result.get('total_cost', 0.0)
            provider = result.get('provider', 'unknown')

            total_tokens_overall = result.get('total_tokens', 0)

            # Save the benchmark run to the database with cost tracking
            run_id = save_benchmark_run(
                benchmark_id=benchmark_id, 
                model_name=model_name, 
                provider=provider,
                report=report, 
                latency=latency,
                total_standard_input_tokens=total_standard_input_tokens, 
                total_cached_input_tokens=total_cached_input_tokens, 
                total_output_tokens=total_output_tokens, 
                total_tokens=total_tokens_overall,
                total_input_cost=0.0,  # Will be calculated from individual prompts
                total_cached_cost=0.0,  # Will be calculated from individual prompts
                total_output_cost=0.0,  # Will be calculated from individual prompts
                total_cost=total_cost
            )

            if run_id:
                prompts_data = result.get('prompts_data', [])
                for p in prompts_data:
                    prompt = p.get('prompt', '')  # Updated key name from runner.py
                    response = p.get('response', '')  # Updated key name from runner.py
                    latency_val = p.get('latency', 0.0)  # Updated key name from runner.py
                    
                    standard_input_tokens_prompt = p.get('standard_input_tokens', 0)
                    cached_input_tokens_prompt = p.get('cached_input_tokens', 0)
                    output_tokens_prompt = p.get('output_tokens', 0)
                    thinking_tokens_prompt = p.get('thinking_tokens', 0)
                    reasoning_tokens_prompt = p.get('reasoning_tokens', 0)
                    
                    # Extract cost data from prompt results
                    input_cost = p.get('input_cost', 0.0)
                    cached_cost = p.get('cached_cost', 0.0)
                    output_cost = p.get('output_cost', 0.0)
                    thinking_cost = p.get('thinking_cost', 0.0)
                    reasoning_cost = p.get('reasoning_cost', 0.0)
                    total_cost_prompt = p.get('total_cost', 0.0)
                    web_search_used = p.get('web_search_used', False)
                    web_search_sources = p.get('web_search_sources', '')

                    # Use the atomic save function to update progress tracking
                    save_benchmark_prompt_atomic(
                        benchmark_run_id=run_id, 
                        prompt=prompt, 
                        response=response, 
                        latency=latency_val,
                        standard_input_tokens=standard_input_tokens_prompt, 
                        cached_input_tokens=cached_input_tokens_prompt, 
                        output_tokens=output_tokens_prompt,
                        thinking_tokens=thinking_tokens_prompt,
                        reasoning_tokens=reasoning_tokens_prompt,
                        input_cost=input_cost,
                        cached_cost=cached_cost,
                        output_cost=output_cost,
                        thinking_cost=thinking_cost,
                        reasoning_cost=reasoning_cost,
                        total_cost=total_cost_prompt,
                        web_search_used=web_search_used,
                        web_search_sources=web_search_sources
                    )

                self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] run saved with DB ID: {run_id if 'run_id' in locals() else 'N/A'})")
                
                result['summary'] = {
                    'run_id': run_id,
                    'model_name': model_name,
                    'items': result.get('items', 'N/A'),
                    'elapsed_s': result.get('elapsed_s', 'N/A')
                }
            else:
                self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] failed to save to database.", 5000)
                self.ui_bridge.show_message("warning", "DB Error", f"Could not save benchmark [{job_id}] results to the database.")

            summary_result_for_console = result.copy()
            self.ui_bridge.display_benchmark_summary_in_console(summary_result_for_console, f"Run {job_id} (DB ID: {run_id if 'run_id' in locals() else 'N/A'})")
            self.ui_bridge.update_status_bar(f"Benchmark [{job_id}] completed.", 5000)
            
            # Only notify about completion if this is a single-model benchmark
            # or if this wasn't already handled by the all-models-complete condition above
            if job['total_models'] == 1 or job['completed_models'] < job['total_models']:
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
        # Determine if this is a final completion (all models done) or just a single model completion
        all_models_complete = False
        if job_id in self.jobs:
            job = self.jobs[job_id]
            all_models_complete = job.get('completed_models', 0) >= job.get('total_models', 0)
            logging.info(f"Notifying benchmark completion for job {job_id}. All models complete: {all_models_complete}")
        
        # Include the additional flags in the completion notification
        completion_data = {
            'job_id': job_id,
            'success': error is None,
            'error': error,
            'result': result,
            # Add new flags for frontend to determine completion state
            'all_models_complete': all_models_complete,
            'final_completion': all_models_complete
        }
        
        # If we have a benchmark_id in the result, include it in the notification
        if result and 'benchmark_id' in result:
            completion_data['benchmark_id'] = result['benchmark_id']
        elif job_id in self.jobs and 'benchmark_id' in self.jobs[job_id]:
            completion_data['benchmark_id'] = self.jobs[job_id]['benchmark_id']
        
        # If we have model_name in the result, include it in the notification
        if result and 'model_name' in result:
            completion_data['model_name'] = result['model_name']
        
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_COMPLETED, completion_data)
        
        self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)

    def get_active_benchmarks_info(self) -> Dict[str, Any]:
        return {jid: data for jid, data in self.jobs.items() if data['status'] not in ['complete', 'finished', 'error', 'deleted']}

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
        try:
            logger.info(f"Attempting to delete benchmark with ID: {benchmark_id}")
            db_path = Path(__file__).parent 
            
            # Keep track of deleted benchmark IDs to avoid reloading them during list operations
            if not hasattr(self, '_deleted_benchmark_ids'):
                self._deleted_benchmark_ids = set()
                
            # Record this benchmark as deleted
            self._deleted_benchmark_ids.add(benchmark_id)
            logging.info(f"Added benchmark ID {benchmark_id} to deleted benchmarks tracking list")
            
            # Perform the actual deletion
            success = delete_benchmark(benchmark_id, db_path=db_path)
            
            if success:
                logger.info(f"Successfully deleted benchmark ID: {benchmark_id}")
                
                # Remove this benchmark from any active jobs to prevent it from showing in updates
                jobs_to_update = []
                for job_id, job_data in self.jobs.items():
                    if job_data.get('benchmark_id') == benchmark_id:
                        job_data['status'] = 'deleted'  # Mark the job as deleted
                        jobs_to_update.append(job_id)
                        logger.info(f"Marked job {job_id} as deleted because its benchmark was deleted")
                
                # Notify UI of the deletion
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
                
                # Also send a specific deletion event that the frontend can use
                self.ui_bridge.notify_data_change(
                    DataChangeType.BENCHMARK_DELETED, 
                    {"benchmark_id": benchmark_id, "deleted_at": datetime.now().isoformat()}
                )
                
                self.ui_bridge.show_message("info", "Benchmark Deleted", f"Benchmark ID {benchmark_id} was successfully deleted.")
                return {"success": True, "message": f"Benchmark ID {benchmark_id} was successfully deleted."}
            else:
                error_msg = f"Failed to delete benchmark ID: {benchmark_id} via file_store"
                logger.error(error_msg)
                self.ui_bridge.show_message("error", "Delete Failed", f"Could not delete benchmark ID {benchmark_id}.")
                return {"success": False, "error": error_msg}
        except Exception as e:
            # Catch any exceptions and return a proper error response
            error_msg = f"Error deleting benchmark ID {benchmark_id}: {str(e)}"
            logger.exception(error_msg)  # This logs the full stack trace
            self.ui_bridge.show_message("error", "Delete Failed", f"Error deleting benchmark ID {benchmark_id}: {str(e)}")
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

    def list_benchmarks(self) -> List[Dict[str, Any]]:
        """Get a list of all benchmarks from the database."""
        db_path = Path(__file__).parent
        benchmarks_from_db = load_all_benchmarks_with_models(db_path=db_path)
        
        # Initialize the deleted benchmarks tracking set if it doesn't exist
        if not hasattr(self, '_deleted_benchmark_ids'):
            self._deleted_benchmark_ids = set()
            logging.info("Initialized empty deleted benchmarks tracking set")
        
        # Get information about active jobs
        active_jobs_info = self.get_active_benchmarks_info() # This is {job_id: job_data}
        
        # Extract the set of DATABASE benchmark_ids that are currently active
        active_db_benchmark_ids = set()
        for job_data in active_jobs_info.values():
            if 'benchmark_id' in job_data:
                active_db_benchmark_ids.add(job_data['benchmark_id'])

        processed_benchmark_ids = set() # To avoid duplicates if a benchmark is in both lists
        result = []

        # Skip any benchmarks that were previously deleted
        filtered_benchmarks_from_db = [b for b in benchmarks_from_db if b['id'] not in self._deleted_benchmark_ids]
        if len(benchmarks_from_db) != len(filtered_benchmarks_from_db):
            skipped_ids = [b['id'] for b in benchmarks_from_db if b['id'] in self._deleted_benchmark_ids]
            logging.info(f"Filtered out {len(benchmarks_from_db) - len(filtered_benchmarks_from_db)} deleted benchmarks: {skipped_ids}")
            
        # Add benchmarks from the database first, if they are not active or to ensure they appear
        for benchmark_db_item in filtered_benchmarks_from_db:
            db_item_id = benchmark_db_item['id']
            
            # Skip any benchmark in our deleted tracking set
            if db_item_id in self._deleted_benchmark_ids:
                logging.info(f"Skipping deleted benchmark ID {db_item_id} from results")
                continue
                
            if db_item_id in active_db_benchmark_ids:
                # This benchmark is active. Fetch its data from active_jobs_info.
                # Find the job_id corresponding to this db_item_id
                job_id_for_active_item = None
                active_job_data = None
                for j_id, j_data in active_jobs_info.items():
                    if j_data.get('benchmark_id') == db_item_id:
                        job_id_for_active_item = j_id
                        active_job_data = j_data
                        break
                
                if active_job_data:
                    # Construct the benchmark entry from active job data
                    # Ensure all necessary fields expected by the frontend are present
                    result.append({
                        'id': db_item_id, # Use the DB benchmark_id
                        'label': active_job_data.get('label', benchmark_db_item.get('label', f'Benchmark {db_item_id}')),
                        'description': active_job_data.get('description', benchmark_db_item.get('description', '')),
                        'model_names': list(active_job_data.get('models_details', {}).keys()), # Convert to list
                        'status': 'running', # Mark as running
                        'timestamp': benchmark_db_item.get('timestamp', active_job_data.get('start_time', datetime.now().isoformat())),
                        # Include other fields like 'file_paths' if needed, usually from benchmark_db_item
                        'file_paths': benchmark_db_item.get('file_paths', [])
                    })
                    processed_benchmark_ids.add(db_item_id)
                else:
                    # Should not happen if active_db_benchmark_ids is built correctly, but as a fallback:
                    result.append(benchmark_db_item) # No status, frontend defaults to 'in-progress'
                    processed_benchmark_ids.add(db_item_id)

            else:
                # Not an active job, add from DB (will default to 'in-progress' on frontend)
                result.append(benchmark_db_item)
                processed_benchmark_ids.add(db_item_id)
                
        # Ensure any truly new "active" benchmarks (not yet in DB, though unlikely with current flow) are appended
        # This part might be redundant if save_benchmark is always called before workers start.
        # However, it ensures any job in self.jobs (marked 'unfinished') is represented.
        for job_id, job_data in active_jobs_info.items():
            associated_benchmark_id = job_data.get('benchmark_id')
            if associated_benchmark_id and associated_benchmark_id not in processed_benchmark_ids:
                result.append({
                    'id': associated_benchmark_id,
                    'label': job_data.get('label', f'Benchmark {associated_benchmark_id}'),
                    'description': job_data.get('description', ''),
                    'model_names': list(job_data.get('models_details', {}).keys()), # Convert to list
                    'status': 'running',
                    'timestamp': job_data.get('start_time', datetime.now().isoformat()),
                    'file_paths': [] # Or fetch if available
                })
                processed_benchmark_ids.add(associated_benchmark_id)
                
        # Sort by timestamp descending, as the original DB query did.
        # The frontend might also sort, but good to be consistent.
        result.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return result

    def delete_benchmark(self, benchmark_id: int) -> dict:
        """Delete a benchmark and all associated data."""
        try:
            db_path = Path(__file__).parent
            from file_store import delete_benchmark
            
            success = delete_benchmark(benchmark_id, db_path)
            
            if success:
                # Also mark the job as deleted if it exists
                for job_id, job_data in self.jobs.items():
                    if job_data.get('benchmark_id') == benchmark_id:
                        job_data['status'] = 'deleted'  # Mark the job as deleted
                        break
                
                return {"success": True, "message": f"Benchmark {benchmark_id} deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete benchmark"}
                
        except Exception as e:
            logging.error(f"Error deleting benchmark {benchmark_id}: {e}")
            return {"success": False, "error": str(e)}

    # ===== PROMPT SET MANAGEMENT =====
    
    def create_prompt_set(self, name: str, description: str, prompts: List[str]) -> dict:
        """Create a new prompt set."""
        try:
            db_path = Path(__file__).parent
            from file_store import create_prompt_set
            
            prompt_set_id = create_prompt_set(name, description, prompts, db_path)
            
            if prompt_set_id:
                return {
                    "success": True, 
                    "prompt_set_id": prompt_set_id,
                    "message": f"Prompt set '{name}' created successfully"
                }
            else:
                return {"success": False, "error": "Failed to create prompt set"}
                
        except Exception as e:
            logging.error(f"Error creating prompt set: {e}")
            return {"success": False, "error": str(e)}
    
    def get_prompt_sets(self) -> List[dict]:
        """Get all prompt sets."""
        try:
            db_path = Path(__file__).parent
            from file_store import get_all_prompt_sets
            
            return get_all_prompt_sets(db_path)
            
        except Exception as e:
            logging.error(f"Error getting prompt sets: {e}")
            return []
    
    def get_prompt_set_details(self, prompt_set_id: int) -> Optional[dict]:
        """Get detailed information about a specific prompt set."""
        try:
            db_path = Path(__file__).parent
            from file_store import get_prompt_set
            
            return get_prompt_set(prompt_set_id, db_path)
            
        except Exception as e:
            logging.error(f"Error getting prompt set {prompt_set_id}: {e}")
            return None
    
    def update_prompt_set(self, prompt_set_id: int, name: str = None, 
                         description: str = None, prompts: List[str] = None) -> dict:
        """Update a prompt set."""
        try:
            db_path = Path(__file__).parent
            from file_store import update_prompt_set
            
            success = update_prompt_set(prompt_set_id, name, description, prompts, db_path)
            
            if success:
                return {"success": True, "message": f"Prompt set {prompt_set_id} updated successfully"}
            else:
                return {"success": False, "error": "Failed to update prompt set"}
                
        except Exception as e:
            logging.error(f"Error updating prompt set {prompt_set_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_prompt_set(self, prompt_set_id: int) -> dict:
        """Delete a prompt set."""
        try:
            db_path = Path(__file__).parent
            from file_store import delete_prompt_set
            
            success = delete_prompt_set(prompt_set_id, db_path)
            
            if success:
                return {"success": True, "message": f"Prompt set {prompt_set_id} deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete prompt set (may be in use by benchmarks)"}
                
        except Exception as e:
            logging.error(f"Error deleting prompt set {prompt_set_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_next_prompt_set_number(self) -> int:
        """Get the next available prompt set number for auto-naming."""
        try:
            db_path = Path(__file__).parent
            from file_store import get_next_prompt_set_number
            
            return get_next_prompt_set_number(db_path)
            
        except Exception as e:
            logging.error(f"Error getting next prompt set number: {e}")
            return 1

    # ===== FILE MANAGEMENT =====
    
    def handle_upload_file(self, file_path: str) -> dict:
        """Upload and register a file in the system."""
        try:
            db_path = Path(__file__).parent
            from file_store import register_file
            
            file_path_obj = Path(file_path)
            
            # Validate file exists
            if not file_path_obj.exists():
                return {"success": False, "error": "File does not exist"}
            
            # Validate file type (PDF, CSV, XLSX)
            allowed_extensions = {'.pdf', '.csv', '.xlsx'}
            if file_path_obj.suffix.lower() not in allowed_extensions:
                return {"success": False, "error": f"File type not supported. Allowed: {', '.join(allowed_extensions)}"}
            
            # Register file
            file_id = register_file(file_path_obj, db_path)
            
            if file_id:
                return {
                    "success": True,
                    "file_id": file_id,
                    "message": f"File '{file_path_obj.name}' uploaded successfully"
                }
            else:
                return {"success": False, "error": "Failed to register file"}
                
        except Exception as e:
            logging.error(f"Error uploading file {file_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_get_files(self) -> List[dict]:
        """Get all registered files."""
        try:
            db_path = Path(__file__).parent
            from file_store import get_all_files
            
            return get_all_files(db_path)
            
        except Exception as e:
            logging.error(f"Error getting files: {e}")
            return []
    
    def handle_get_file_details(self, file_id: int) -> dict:
        """Get details of a specific file."""
        try:
            db_path = Path(__file__).parent
            from file_store import get_file_details
            
            file_details = get_file_details(file_id, db_path)
            
            if file_details:
                return {"success": True, "file": file_details}
            else:
                return {"success": False, "error": "File not found"}
                
        except Exception as e:
            logging.error(f"Error getting file details {file_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_delete_file(self, file_id: int) -> dict:
        """Delete a file from the system."""
        try:
            db_path = Path(__file__).parent
            from file_store import delete_file
            
            success = delete_file(file_id, db_path)
            
            if success:
                return {"success": True, "message": f"File {file_id} deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete file (may be in use by benchmarks)"}
                
        except Exception as e:
            logging.error(f"Error deleting file {file_id}: {e}")
            return {"success": False, "error": str(e)}

    # ===== PROMPT SET HANDLERS =====
    
    def handle_create_prompt_set(self, name: str, description: str, prompts: List[str]) -> dict:
        """Create a new prompt set."""
        return self.create_prompt_set(name, description, prompts)
    
    def handle_get_prompt_sets(self) -> List[dict]:
        """Get all prompt sets."""
        return self.get_prompt_sets()
    
    def handle_get_prompt_set_details(self, prompt_set_id: int) -> dict:
        """Get detailed information about a specific prompt set."""
        result = self.get_prompt_set_details(prompt_set_id)
        if result:
            return {"success": True, "prompt_set": result}
        else:
            return {"success": False, "error": "Prompt set not found"}
    
    def handle_update_prompt_set(self, prompt_set_id: int, name: str = None, 
                                description: str = None, prompts: List[str] = None) -> dict:
        """Update a prompt set."""
        return self.update_prompt_set(prompt_set_id, name, description, prompts)
    
    def handle_delete_prompt_set(self, prompt_set_id: int) -> dict:
        """Delete a prompt set."""
        return self.delete_prompt_set(prompt_set_id)
    
    def handle_get_next_prompt_set_number(self) -> dict:
        """Get the next available prompt set number."""
        return {"next_number": self.get_next_prompt_set_number()}

    def handle_validate_tokens(self, prompts: list, file_paths: list, model_names: list) -> dict:
        """Validate token limits for given prompts, files, and models."""
        return self.validate_tokens(prompts, file_paths, model_names)

    def validate_tokens(self, prompts: list, pdfPaths: list, modelNames: list) -> dict:
        """
        Validate that prompts + PDFs don't exceed context limits for the selected models.
        
        Args:
            prompts: List of prompt dictionaries with 'prompt_text' keys
            pdfPaths: List of PDF file paths
            modelNames: List of model names to check
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Validate inputs
            if not prompts:
                return {"status": "error", "message": "No prompts provided"}
            if not modelNames:
                return {"status": "error", "message": "No models provided"}
            
            # Run token validation
            validation_results = validate_token_limits(prompts, pdfPaths or [], modelNames)
            
            return {
                "status": "success",
                "validation_results": validation_results,
                "formatted_message": format_token_validation_message(validation_results)
            }
            
        except Exception as e:
            logging.error(f"Error validating tokens: {str(e)}")
            return {"status": "error", "message": f"Token validation failed: {str(e)}"}

    def get_model_token_budget(self, model_name: str) -> int:
        """Get the token budget for a specific model (context limit minus buffer)."""
        model_budgets = {
            # OpenAI models
            'gpt-4o': 120000,  # 128k - 8k buffer
            'gpt-4o-mini': 120000,  # 128k - 8k buffer
            'gpt-4.1': 120000,  # 128k - 8k buffer
            'gpt-4.1-mini': 120000,  # 128k - 8k buffer
            'o3': 120000,  # 128k - 8k buffer
            'o4-mini': 120000,  # 128k - 8k buffer
            
            # Anthropic models
            'claude-opus-4-20250514': 190000,  # 200k - 10k buffer
            'claude-opus-4-20250514-thinking': 190000,
            'claude-sonnet-4-20250514': 190000,
            'claude-sonnet-4-20250514-thinking': 190000,
            'claude-3-7-sonnet-20250219': 190000,
            'claude-3-7-sonnet-20250219-thinking': 190000,
            'claude-3-5-haiku-20241022': 190000,
            
            # Google models
            'gemini-2.5-flash-preview-05-20': 990000,  # 1M - 10k buffer
            'gemini-2.5-pro-preview-05-06': 990000,
        }
        
        return model_budgets.get(model_name, 120000)  # Default to GPT-4o budget

    def process_csv_for_model(self, csv_file_path: str, model_name: str) -> dict:
        """
        Process CSV file for a specific model, applying token budget limits.
        
        Returns:
            Dict with 'data' (markdown string), 'truncation_info', 'included_rows', 'total_rows'
        """
        try:
            from file_store import parse_csv_to_markdown_format, estimate_markdown_tokens
            
            # Get model's token budget
            token_budget = self.get_model_token_budget(model_name)
            
            # Parse full CSV
            csv_data = parse_csv_to_markdown_format(Path(csv_file_path))
            total_rows = csv_data['total_rows']
            
            # Estimate tokens for full dataset
            full_tokens = estimate_markdown_tokens(csv_data['markdown_data'])
            
            if full_tokens <= token_budget:
                # No truncation needed
                return {
                    'data': csv_data['markdown_data'],
                    'truncation_info': None,
                    'included_rows': total_rows,
                    'total_rows': total_rows,
                    'estimated_tokens': full_tokens
                }
            
            # Need to truncate - binary search for optimal row count
            left, right = 1, total_rows
            best_rows = 1
            
            while left <= right:
                mid = (left + right) // 2
                subset_data = parse_csv_to_markdown_format(Path(csv_file_path), max_rows=mid)
                subset_tokens = estimate_markdown_tokens(subset_data['markdown_data'])
                
                if subset_tokens <= token_budget:
                    best_rows = mid
                    left = mid + 1
                else:
                    right = mid - 1
            
            # Get the final truncated data
            truncated_data = parse_csv_to_markdown_format(Path(csv_file_path), max_rows=best_rows)
            final_tokens = estimate_markdown_tokens(truncated_data['markdown_data'])
            
            # Create truncation info
            truncation_info = {
                'csv_truncations': [{
                    'file_name': Path(csv_file_path).name,
                    'original_rows': total_rows,
                    'included_rows': best_rows,
                    'token_budget': token_budget,
                    'actual_tokens': final_tokens,
                    'strategy': 'first_n_rows',
                    'model': model_name
                }]
            }
            
            return {
                'data': truncated_data['markdown_data'],
                'truncation_info': truncation_info,
                'included_rows': best_rows,
                'total_rows': total_rows,
                'estimated_tokens': final_tokens
            }
            
        except Exception as e:
            logging.error(f"Error processing CSV for model {model_name}: {e}")
            raise

    def handle_sync_benchmark(self, benchmark_id: int) -> dict:
        """
        Sync a benchmark by rerunning only missing, failed, or pending prompts.
        
        Args:
            benchmark_id: ID of the benchmark to sync
            
        Returns:
            dict: Status of the sync operation
        """
        try:
            logger = logging.getLogger(__name__)
            logger.info(f"Starting sync for benchmark {benchmark_id}")
            
            # PREVENT DUPLICATE LAUNCHES: Check if this benchmark is currently running
            active_jobs = [job for job in self.jobs.values() 
                          if job.get('benchmark_id') == benchmark_id 
                          and job.get('status') in ['running', 'pending', 'syncing']]
            
            if active_jobs:
                return {
                    "success": False, 
                    "error": f"Cannot sync benchmark {benchmark_id} - it is currently running or syncing. Please wait for it to complete first."
                }
            
            # Check for active workers for this benchmark
            active_workers = [worker_key for worker_key, worker in self.workers.items() 
                             if worker.is_alive() and hasattr(worker, 'benchmark_id') 
                             and worker.benchmark_id == benchmark_id]
            
            if active_workers:
                return {
                    "success": False, 
                    "error": f"Cannot sync benchmark {benchmark_id} - {len(active_workers)} workers are still active. Please wait for them to complete first."
                }
            
            # Get sync analysis
            db_path = Path(__file__).parent
            from file_store import get_benchmark_sync_status
            
            sync_status = get_benchmark_sync_status(benchmark_id, db_path)
            
            if "error" in sync_status:
                return {"success": False, "error": sync_status["error"]}
            
            if not sync_status.get("sync_needed", False):
                return {
                    "success": True, 
                    "message": "Benchmark is already complete - no sync needed",
                    "sync_needed": False,
                    "prompts_synced": 0
                }
            
            # Prepare data for partial benchmark run
            total_prompts_to_sync = sync_status["total_prompts_to_sync"]
            models_needing_sync = sync_status["models_needing_sync"]
            
            logger.info(f"Sync needed: {total_prompts_to_sync} prompts across {len(models_needing_sync)} models")
            
            # Get benchmark details to extract files and other info
            from file_store import get_benchmark_details
            benchmark_details = get_benchmark_details(benchmark_id, db_path)
            
            if not benchmark_details:
                return {"success": False, "error": "Could not load benchmark details"}
            
            # Extract file paths from benchmark
            file_paths = [f['file_path'] for f in benchmark_details.get('files', [])]
            
            # Create a job for tracking
            job_id = self._get_next_job_id()
            
            # Extract just the model names that need syncing
            models_to_sync = [model_info["model_name"] for model_info in models_needing_sync]
            
            # Initialize job tracking
            self.jobs[job_id] = {
                'status': 'syncing',
                'label': f"Sync: {sync_status['benchmark_label']}",
                'description': f"Syncing {total_prompts_to_sync} prompts",
                'pdf_paths': file_paths,
                'benchmark_id': benchmark_id,
                'total_models': len(models_to_sync),
                'completed_models': 0,
                'prompts_count': total_prompts_to_sync,
                'start_time': datetime.now().isoformat(),
                'models_details': {model_name: {'status': 'pending', 'start_time': None, 'end_time': None} for model_name in models_to_sync},
                'is_sync': True,  # Flag to indicate this is a sync operation
                'sync_info': sync_status
            }
            
            # Start sync workers for each model that needs syncing
            workers_started = 0
            
            for model_info in models_needing_sync:
                model_name = model_info["model_name"]
                prompts_to_sync = model_info["prompts_to_sync"]
                
                # Convert prompts to the format expected by the worker
                prompts_for_worker = [
                    {"prompt_text": prompt["prompt_text"]} 
                    for prompt in prompts_to_sync
                ]
                
                logger.info(f"Starting sync worker for model {model_name} with {len(prompts_for_worker)} prompts")
                
                # Create callbacks
                def create_finished_callback(jid, mname):
                    return lambda result: self.handle_run_finished(result, job_id=jid, model_name_for_run=mname)
                    
                def create_progress_callback(jid, mname):
                    return lambda progress_data: self.handle_benchmark_progress(jid, mname, progress_data)
                
                # Create worker for this model's prompts
                worker = BenchmarkWorker(
                    job_id=job_id,
                    benchmark_id=benchmark_id,
                    prompts=prompts_for_worker,
                    pdf_paths=file_paths,
                    model_name=model_name,
                    on_progress=create_progress_callback(job_id, model_name),
                    on_finished=create_finished_callback(job_id, model_name),
                    web_search_enabled=benchmark_details.get('use_web_search', False)
                )
                
                # Store worker
                worker_key = f"{job_id}_{model_name}"
                self.workers[worker_key] = worker
                
                # Start the worker
                worker.start()
                workers_started += 1
                
                logger.info(f"Started sync worker for {model_name}")
            
            # Notify UI about the sync job
            self.ui_bridge.notify_benchmark_progress(job_id, self.jobs[job_id])
            
            logger.info(f"Sync started for benchmark {benchmark_id}: {workers_started} workers, {total_prompts_to_sync} prompts")
            
            return {
                "success": True,
                "job_id": job_id,
                "benchmark_id": benchmark_id,
                "message": f"Sync started for {total_prompts_to_sync} prompts across {workers_started} models",
                "sync_needed": True,
                "prompts_to_sync": total_prompts_to_sync,
                "models_to_sync": workers_started,
                "sync_details": sync_status
            }
            
        except Exception as e:
            error_msg = f"Error syncing benchmark {benchmark_id}: {str(e)}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

    def handle_get_sync_status(self, benchmark_id: int) -> dict:
        """
        Get sync status for a benchmark without starting a sync.
        
        Args:
            benchmark_id: ID of the benchmark to check
            
        Returns:
            dict: Sync status information
        """
        try:
            db_path = Path(__file__).parent
            from file_store import get_benchmark_sync_status
            
            sync_status = get_benchmark_sync_status(benchmark_id, db_path)
            
            if "error" in sync_status:
                return {"success": False, "error": sync_status["error"]}
            
            return {"success": True, "sync_status": sync_status}
            
        except Exception as e:
            error_msg = f"Error getting sync status for benchmark {benchmark_id}: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

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