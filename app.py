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
import sqlite3
import pandas as pd
import subprocess
import tempfile

# Increase CSV field size limit to handle large web search data
csv.field_size_limit(500000)  # 500KB limit for large web search data

# --- Basic Logger Setup ---
logger = logging.getLogger(__name__)

# Use appropriate base path for both development and PyInstaller
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle - use temp directory for database
    db_path = Path(tempfile.gettempdir())
else:
    # Running in development - use current script directory
    db_path = Path(__file__).parent 

# Configure logging for more concise output
# Use a safe location for log file that works in both dev and packaged mode
log_dir = tempfile.gettempdir() if getattr(sys, 'frozen', False) else '.'
log_path = os.path.join(log_dir, "benchmark.log")

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s',
                    handlers=[
                        # Use temp directory for log file in packaged mode
                        logging.FileHandler(log_path),
                        # For console, ensure high visibility
                        logging.StreamHandler()
                    ])

# Set log levels for specific modules to increase visibility
# logging.getLogger('runner').setLevel(logging.DEBUG)
logging.getLogger('models_openai').setLevel(logging.DEBUG)

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
    delete_file,
    register_vector_store,
    get_vector_store_by_id,
    get_all_vector_stores,
    update_vector_store_stats,
    register_vector_store_file,
    get_vector_store_files,
    associate_benchmark_with_vector_store,
    get_benchmark_vector_stores,
    delete_vector_store,
    reset_stuck_benchmarks
)
# Import the UI bridge protocol and data change types
from ui_bridge import AppUIBridge, DataChangeType
from ui_bridge_impl import ScriptUiBridge
from token_manager import TokenManager
from benchmark_runner import BenchmarkWorker
from file_manager import FileManager
from prompt_manager import PromptManager

# --- AppLogic main application class ---


class AppLogic:
    def __init__(self, ui_bridge: AppUIBridge):
        self.ui_bridge = ui_bridge
        self.jobs = {}  # job_id -> job_data
        self.workers = {}  # Add workers dictionary to track active workers
        self._last_cleanup = time.time()
        self._next_job_id = 1
        self._worker_cleanup_interval = 30  # Clean up every 30 seconds
        self.token_manager = TokenManager()  # Initialize token manager
        self.file_manager = FileManager(self.db_path)  # Initialize file manager
        self.prompt_manager = PromptManager(self.db_path)  # Initialize prompt manager
        
        # Initialize database and reset any stuck benchmarks
        init_file_store_db(self.db_path)
        self.reset_stuck_benchmarks()
        self.cleanup_stuck_rerun_prompts()
    
    @property
    def db_path(self) -> Path:
        """Get the consistent database directory path."""
        return Path(__file__).parent
    
    def _create_worker_callbacks(self, job_id: int, model_name: str):
        """Create standardized callbacks for benchmark workers."""
        def finished_callback(result):
            return self.handle_run_finished(result, job_id=job_id, model_name_for_run=model_name)
        
        def progress_callback(progress_data):
            return self.handle_benchmark_progress(job_id, model_name, progress_data)
        
        return finished_callback, progress_callback
    
    def _create_and_start_worker(self, job_id: int, benchmark_id: int, 
                               prompts: list, pdf_paths: list, model_name: str,
                               web_search_enabled: bool = False, single_prompt_id: int = None):
        """Create and start a benchmark worker with standardized setup."""
        finished_cb, progress_cb = self._create_worker_callbacks(job_id, model_name)
        
        worker = BenchmarkWorker(
            job_id=job_id,
            benchmark_id=benchmark_id,
            prompts=prompts,
            pdf_paths=pdf_paths,
            model_name=model_name,
            on_progress=progress_cb,
            on_finished=finished_cb,
            web_search_enabled=web_search_enabled,
            single_prompt_id=single_prompt_id
        )
        
        worker_key = f"{job_id}_{model_name}"
        self.workers[worker_key] = worker
        worker.start()
        
        return worker, worker_key
    
    def reset_stuck_benchmarks(self):
        """Reset benchmarks that might be stuck from previous runs."""
        try:
            
            reset_count = reset_stuck_benchmarks(self.db_path)
            if reset_count > 0:
                logging.info(f"Reset {reset_count} stuck benchmarks on startup")
                # Notify UI that benchmark list may have changed
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
        except Exception as e:
            logging.error(f"Error resetting stuck benchmarks on startup: {e}")

    def cleanup_stuck_rerun_prompts(self):
        """Clean up any prompts stuck in pending state from interrupted reruns."""
        try:
            from file_store import cleanup_stuck_rerun_prompts
            stuck_count = cleanup_stuck_rerun_prompts(self.db_path)
            if stuck_count > 0:
                logging.info(f"Cleaned up {stuck_count} stuck rerun prompts on startup")
                # Notify UI that benchmark list may have changed
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
        except Exception as e:
            logging.error(f"Error cleaning up stuck rerun prompts on startup: {e}")

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
        logging.info(f"Using database directory: {self.db_path}")
        
        # Initialize database - pass the directory, not the file path
        # Surface any errors directly to assist with debugging
        init_file_store_db(db_path=self.db_path)
        
        # Verify that the database was created successfully
        db_file = self.db_path / 'eotb_file_store.sqlite'
        if not db_file.exists():
            logging.error(f"Database file was not created at expected location: {db_file}")
            raise FileNotFoundError(f"Database initialization failed: {db_file} not found")
            
        logging.info(f"Database successfully initialized at: {db_file}")
        # Store DB file path for later use (e.g., CSV export)
        self.db_file_path = str(db_file)

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
        
        # Use consistent database path
        db_path = self.db_path / 'eotb_file_store.sqlite'
        logger.info(f"Using database at: {db_path} for saving benchmark")
        
        # Ensure database directory exists
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize database if it doesn't exist
        from file_store import init_db
        init_db(self.db_path)
        
        # Save the benchmark to get an ID - let errors propagate naturally
        from file_store import save_benchmark
        benchmark_id = save_benchmark(
            label=label,
            description=description or "",
            file_paths=[str(pdf_path) for pdf_path in pdfs_to_run],
            intended_models=modelNames,  # Store the intended models
            use_web_search=webSearchEnabled,  # Pass web search flag
            db_path=self.db_path
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
            update_benchmark_model(benchmark_id, model_name, self.db_path)
            logger.info(f"Registered model {model_name} in database for benchmark {benchmark_id}")
        
        # Start a worker thread for each model using the helper method
        for model_name in modelNames:
            logger.info(f"Starting worker for model: {model_name}")
            
            # Use the helper method to create and start worker
            worker, worker_key = self._create_and_start_worker(
                job_id=job_id,
                benchmark_id=benchmark_id,
                prompts=prompts,
                pdf_paths=pdfs_to_run,
                model_name=model_name,
                web_search_enabled=webSearchEnabled
            )
        
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
        db_file = self.db_path / 'eotb_file_store.sqlite'
        with sqlite3.connect(db_file) as conn:
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
        # Using self.db_path property instead
        details = load_benchmark_details(benchmark_id, db_path=self.db_path)
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
        if current_time - self._last_cleanup < self._worker_cleanup_interval:
            return
            
        self._last_cleanup = current_time
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
            # Using self.db_path property instead 
            
            # Keep track of deleted benchmark IDs to avoid reloading them during list operations
            if not hasattr(self, '_deleted_benchmark_ids'):
                self._deleted_benchmark_ids = set()
                
            # Record this benchmark as deleted
            self._deleted_benchmark_ids.add(benchmark_id)
            logging.info(f"Added benchmark ID {benchmark_id} to deleted benchmarks tracking list")
            
            # Force-stop any active workers for this benchmark
            workers_stopped = []
            jobs_to_remove = []
            
            # Find and stop all jobs/workers for this benchmark
            for job_id, job_data in list(self.jobs.items()):
                if job_data.get('benchmark_id') == benchmark_id:
                    logger.info(f"Found active job {job_id} for benchmark {benchmark_id}, stopping worker...")
                    
                    # Mark job as deleted to prevent further operations
                    job_data['status'] = 'deleted'
                    
                    # If there's an active worker, try to stop it
                    worker = job_data.get('worker')
                    if worker and hasattr(worker, 'active'):
                        try:
                            worker.active = False  # Signal worker to stop
                            workers_stopped.append(job_id)
                            logger.info(f"Signaled worker for job {job_id} to stop")
                        except Exception as e:
                            logger.warning(f"Error signaling worker to stop for job {job_id}: {e}")
                    
                    # Mark for removal from jobs dict
                    jobs_to_remove.append(job_id)
            
            # Remove stopped jobs from the jobs dictionary
            for job_id in jobs_to_remove:
                if job_id in self.jobs:
                    del self.jobs[job_id]
                    logger.info(f"Removed job {job_id} from active jobs")
            
            # Update the benchmark status to indicate deletion in progress
            try:
                from file_store import update_benchmark_status
                update_benchmark_status(benchmark_id, 'deleting', db_path=self.db_path)
                logger.info(f"Set benchmark {benchmark_id} status to 'deleting'")
            except Exception as e:
                logger.warning(f"Could not update benchmark status before deletion: {e}")
            
            # Perform the actual deletion
            success = delete_benchmark(benchmark_id, db_path=self.db_path)
            
            if success:
                logger.info(f"Successfully deleted benchmark ID: {benchmark_id}")
                
                if workers_stopped:
                    logger.info(f"Stopped {len(workers_stopped)} workers for deleted benchmark: {workers_stopped}")
                
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

        # Using self.db_path property instead 
        success = update_benchmark_details(benchmark_id, label=new_label, description=new_description, db_path=self.db_path)
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

    def rerun_single_prompt(self, prompt_id: int) -> dict:
        """Rerun a single prompt from an existing benchmark.
        
        Args:
            prompt_id: The ID of the prompt to rerun
            
        Returns:
            dict: A response with at least a 'success' field indicating whether the operation succeeded
        """
        try:
            logger.info(f"Attempting to rerun prompt ID: {prompt_id}")
            # Using self.db_path property instead
            
            # Get prompt details and benchmark context
            from file_store import get_prompt_for_rerun, get_benchmark_files
            prompt_data = get_prompt_for_rerun(prompt_id, db_path=self.db_path)
            
            if not prompt_data:
                error_msg = f"Prompt ID {prompt_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Set prompt status to pending and clear previous results
            from file_store import reset_prompt_for_rerun
            reset_prompt_for_rerun(prompt_id, db_path=self.db_path)
            
            # Launch the rerun in a background thread
            job_id = self._next_job_id
            self._next_job_id += 1
            
            # Get benchmark files for context (needed for rerun)
            benchmark_files = get_benchmark_files(prompt_data['benchmark_id'], db_path=self.db_path)
            pdf_paths = [f['file_path'] for f in benchmark_files if f['mime_type'] == 'application/pdf']
            
            # Create callbacks for single prompt rerun
            def create_finished_callback():
                return lambda result: self.handle_single_prompt_rerun_finished(result, prompt_id, job_id)
                
            def create_progress_callback():
                return lambda progress_data: self.handle_single_prompt_rerun_progress(prompt_id, job_id, progress_data)
            
            # Create worker for single prompt rerun
            # Format prompt as dictionary with required structure
            formatted_prompts = [{
                'prompt_text': prompt_data['prompt'],
                'web_search': prompt_data.get('use_web_search', False)
            }]
            
            worker = BenchmarkWorker(
                job_id=job_id,
                benchmark_id=prompt_data['benchmark_id'],
                prompts=formatted_prompts,
                pdf_paths=pdf_paths,
                model_name=prompt_data['model_name'],
                on_progress=create_progress_callback(),
                on_finished=create_finished_callback(),
                web_search_enabled=prompt_data.get('use_web_search', False),
                single_prompt_id=prompt_id  # Pass the prompt ID for in-place update
            )
            
            self.jobs[job_id] = {
                'id': job_id,
                'benchmark_id': prompt_data['benchmark_id'],
                'benchmark_run_id': prompt_data['benchmark_run_id'],
                'model_name': prompt_data['model_name'],
                'provider': prompt_data['provider'],
                'status': 'running',
                'created_at': datetime.now().isoformat(),
                'worker': worker,
                'type': 'single_prompt_rerun',
                'prompt_id': prompt_id
            }
            
            # Start worker with error handling
            try:
                worker.start()
                logger.info(f"Successfully started rerun for prompt ID {prompt_id} with job ID {job_id}")
                self.ui_bridge.show_message("info", "Prompt Rerun Started", f"Rerunning prompt ID {prompt_id}")
                
                # Schedule a timeout check to catch stuck processes
                import threading
                def timeout_check():
                    import time
                    time.sleep(300)  # Wait 5 minutes
                    if job_id in self.jobs and self.jobs[job_id].get('status') == 'running':
                        logger.warning(f"Prompt rerun {prompt_id} timed out after 5 minutes")
                        self.handle_single_prompt_rerun_finished(
                            {'status': 'failed', 'error': 'Rerun timed out after 5 minutes', 'model_name': prompt_data['model_name']}, 
                            prompt_id, job_id
                        )
                        # Mark prompt as failed in database
                        from file_store import mark_prompt_failed
                        mark_prompt_failed(prompt_data['benchmark_run_id'], prompt_data['prompt'], "Rerun timed out after 5 minutes", db_path=self.db_path)
                
                timeout_thread = threading.Thread(target=timeout_check, daemon=True)
                timeout_thread.start()
                
            except Exception as worker_error:
                logger.error(f"Failed to start worker for prompt rerun {prompt_id}: {worker_error}")
                # Clean up and mark as failed
                if job_id in self.jobs:
                    del self.jobs[job_id]
                from file_store import mark_prompt_failed
                mark_prompt_failed(prompt_data['benchmark_run_id'], prompt_data['prompt'], f"Failed to start rerun worker: {str(worker_error)}", db_path=self.db_path)
                return {"success": False, "error": f"Failed to start rerun worker: {str(worker_error)}"}
            
            
            # Notify UI that benchmarks have been updated
            self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
            
            return {"success": True, "job_id": job_id, "message": f"Prompt ID {prompt_id} rerun started"}
            
        except Exception as e:
            error_msg = f"Error rerunning prompt ID {prompt_id}: {str(e)}"
            logger.exception(error_msg)
            self.ui_bridge.show_message("error", "Rerun Failed", f"Error rerunning prompt ID {prompt_id}: {str(e)}")
            return {"success": False, "error": error_msg}

    def handle_single_prompt_rerun_progress(self, prompt_id: int, job_id: int, progress_data: dict):
        """Handle progress updates for single prompt rerun."""
        logger.debug(f"Single prompt rerun progress for prompt {prompt_id}: {progress_data}")
        
        # Add context to progress data
        progress_data.update({
            'prompt_id': prompt_id,
            'job_id': job_id,
            'type': 'single_prompt_rerun'
        })
        
        # Notify UI of progress
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, progress_data)

    def handle_single_prompt_rerun_finished(self, result: dict, prompt_id: int, job_id: int):
        """Handle completion of single prompt rerun."""
        logger.info(f"Single prompt rerun finished for prompt {prompt_id}: {result}")
        
        # Get benchmark_id from the result to update progress
        benchmark_id = result.get('benchmark_id')
        if benchmark_id:
            # Update benchmark progress and status based on completed prompts
            from file_store import update_benchmark_progress
            update_benchmark_progress(benchmark_id, self.db_path)
            logger.info(f"Updated benchmark progress for benchmark {benchmark_id} after prompt {prompt_id} rerun")
        
        # Clean up job from active jobs
        if job_id in self.jobs:
            del self.jobs[job_id]
        
        # Remove worker from workers dict using appropriate key
        worker_key = f"{job_id}_{result.get('model_name', 'unknown')}"
        if worker_key in self.workers:
            del self.workers[worker_key]
        
        if result.get('status') == 'completed':
            self.ui_bridge.show_message("success", "Prompt Rerun Complete", f"Prompt ID {prompt_id} has been successfully rerun")
        else:
            error_msg = result.get('error', 'Unknown error occurred')
            self.ui_bridge.show_message("error", "Prompt Rerun Failed", f"Failed to rerun prompt ID {prompt_id}: {error_msg}")
        
        # Check if benchmark is now complete and send appropriate completion event
        if benchmark_id:
            from file_store import get_benchmark_by_id
            benchmark = get_benchmark_by_id(benchmark_id, self.db_path)
            if benchmark and benchmark.get('status') in ['completed', 'completed_with_errors']:
                # Send benchmark completion event like regular benchmarks
                completion_data = {
                    'benchmark_id': benchmark_id,
                    'success': True,
                    'all_models_complete': True,
                    'final_completion': True,
                    'rerun_completion': True
                }
                self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_COMPLETED, completion_data)
                logger.info(f"Sent benchmark completion event for benchmark {benchmark_id} after rerun")
        
        # Notify UI that benchmarks have been updated
        self.ui_bridge.notify_data_change(DataChangeType.BENCHMARK_LIST, None)

    def list_benchmarks(self) -> List[Dict[str, Any]]:
        """Get a list of all benchmarks from the database."""
        # Using self.db_path property instead
        benchmarks_from_db = load_all_benchmarks_with_models(db_path=self.db_path)
        
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
            # Using self.db_path property instead
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
        """Delegate to prompt manager for prompt set creation."""
        return self.prompt_manager.create_prompt_set(name, description, prompts)
    
    def get_prompt_sets(self) -> List[dict]:
        """Delegate to prompt manager for getting prompt sets."""
        return self.prompt_manager.get_prompt_sets()
    
    def get_prompt_set_details(self, prompt_set_id: int) -> Optional[dict]:
        """Delegate to prompt manager for prompt set details."""
        return self.prompt_manager.get_prompt_set_details(prompt_set_id)
    
    def update_prompt_set(self, prompt_set_id: int, name: str = None, 
                         description: str = None, prompts: List[str] = None) -> dict:
        """Delegate to prompt manager for prompt set update."""
        return self.prompt_manager.update_prompt_set(prompt_set_id, name, description, prompts)
    
    def delete_prompt_set(self, prompt_set_id: int) -> dict:
        """Delegate to prompt manager for prompt set deletion."""
        return self.prompt_manager.delete_prompt_set(prompt_set_id)
    
    def get_next_prompt_set_number(self) -> int:
        """Delegate to prompt manager for next prompt set number."""
        return self.prompt_manager.get_next_prompt_set_number()

    # ===== FILE MANAGEMENT =====
    
    def handle_upload_file(self, file_path: str) -> dict:
        """Delegate to file manager for file upload."""
        return self.file_manager.handle_upload_file(file_path)
    
    def handle_get_files(self) -> List[dict]:
        """Delegate to file manager for getting files."""
        return self.file_manager.handle_get_files()
    
    def handle_get_file_details(self, file_id: int) -> dict:
        """Delegate to file manager for file details."""
        return self.file_manager.handle_get_file_details(file_id)
    
    def handle_delete_file(self, file_id: int) -> dict:
        """Delegate to file manager for file deletion."""
        return self.file_manager.handle_delete_file(file_id)

    # ===== PROMPT SET HANDLERS =====
    
    def handle_create_prompt_set(self, name: str, description: str, prompts: List[str]) -> dict:
        """Delegate to prompt manager for prompt set creation."""
        return self.prompt_manager.handle_create_prompt_set(name, description, prompts)
    
    def handle_get_prompt_sets(self) -> List[dict]:
        """Delegate to prompt manager for getting prompt sets."""
        return self.prompt_manager.handle_get_prompt_sets()
    
    def handle_get_prompt_set_details(self, prompt_set_id: int) -> dict:
        """Delegate to prompt manager for prompt set details."""
        return self.prompt_manager.handle_get_prompt_set_details(prompt_set_id)
    
    def handle_update_prompt_set(self, prompt_set_id: int, name: str = None, 
                                description: str = None, prompts: List[str] = None) -> dict:
        """Delegate to prompt manager for prompt set update."""
        return self.prompt_manager.handle_update_prompt_set(prompt_set_id, name, description, prompts)
    
    def handle_delete_prompt_set(self, prompt_set_id: int) -> dict:
        """Delegate to prompt manager for prompt set deletion."""
        return self.prompt_manager.handle_delete_prompt_set(prompt_set_id)
    
    def handle_get_next_prompt_set_number(self) -> dict:
        """Delegate to prompt manager for next prompt set number."""
        return self.prompt_manager.handle_get_next_prompt_set_number()

    def handle_validate_tokens(self, prompts: list, file_paths: list, model_names: list) -> dict:
        """Validate token limits for given prompts, files, and models."""
        return self.token_manager.validate_tokens(prompts, file_paths, model_names)
    
    def handle_count_tokens_for_file(self, file_path: str, sample_prompt: str, model_names: list) -> dict:
        """Count tokens for a specific file using different model providers."""
        try:
            from token_validator import get_provider_from_model
            from pathlib import Path
            import json
            
            # Check if this is a CSV file
            if file_path.lower().endswith('.csv'):
                return self._count_tokens_for_csv(file_path, sample_prompt, model_names)
            else:
                # For non-CSV files, use the original PDF-based approach
                return self._count_tokens_for_pdf(file_path, sample_prompt, model_names)
            
        except Exception as e:
            logging.error(f"Error in handle_count_tokens_for_file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _count_tokens_for_csv(self, file_path: str, sample_prompt: str, model_names: list) -> dict:
        """Count tokens for CSV files by converting to text format."""
        try:
            from token_validator import get_provider_from_model
            from models_openai import count_tokens_openai, get_context_limit_openai
            from models_anthropic import count_tokens_anthropic, get_context_limit_anthropic  
            from models_google import count_tokens_google, get_context_limit_google
            import json
            
            # Get CSV data and convert to text format
            csv_text = self._convert_csv_to_text(file_path)
            if not csv_text:
                # Fall back to estimates if we can't read the CSV
                return self._fallback_to_estimates(file_path, sample_prompt, model_names)
            
            # Combine prompt + CSV text
            full_text = f"{sample_prompt}\n\n{csv_text}"
            
            # Debug logging
            logging.info(f"CSV text length: {len(csv_text)} chars")
            logging.info(f"Full text length: {len(full_text)} chars")
            logging.info(f"CSV text preview: {csv_text[:500]}...")
            
            # Get unique providers from model names
            providers_tested = {}
            results = {}
            
            for model_name in model_names:
                try:
                    provider = get_provider_from_model(model_name)
                    
                    # Skip if we already tested this provider
                    if provider in providers_tested:
                        continue
                    
                    # Count tokens using text-only approach for each provider
                    if provider == "openai":
                        # For OpenAI, use simple text content
                        content = [{"type": "input_text", "text": full_text}]
                        actual_tokens = count_tokens_openai(content, model_name)
                        context_limit = get_context_limit_openai(model_name)
                        
                    elif provider == "anthropic":
                        # For Anthropic, use text message format
                        content = [{"type": "text", "text": full_text}]
                        actual_tokens = count_tokens_anthropic(content, model_name)
                        context_limit = get_context_limit_anthropic(model_name)
                        
                    elif provider == "google":
                        # Use updated model names and proper Content structure
                        if model_name == "gemini-2.5-pro":
                            model_name = "gemini-2.5-pro-preview-06-05"
                        elif model_name == "gemini-2.5-flash":
                            model_name = "gemini-2.5-flash-preview-05-20"
                            
                        from google import genai
                        contents = [
                            genai.types.Content(
                                role="user",
                                parts=[genai.types.Part.from_text(text=full_text)]
                            )
                        ]
                        actual_tokens = count_tokens_google(contents, model_name)
                        context_limit = get_context_limit_google(model_name)
                        
                    else:
                        logging.warning(f"Unknown provider {provider} for model {model_name}")
                        continue
                    
                    will_exceed = actual_tokens > context_limit
                    
                    results[provider] = {
                        "model_name": model_name,
                        "actual_tokens": actual_tokens,
                        "context_limit": context_limit,
                        "will_exceed": will_exceed,
                        "provider": provider
                    }
                    providers_tested[provider] = True
                    
                except Exception as e:
                    logging.error(f"Error counting tokens for CSV with {model_name}: {e}")
                    # Fall back to estimates for this provider
                    provider = get_provider_from_model(model_name)
                    estimated_tokens = self._estimate_file_tokens(file_path, sample_prompt)
                    context_limit = self._get_context_limit_for_model(model_name)
                    will_exceed = estimated_tokens > context_limit
                    
                    results[provider] = {
                        "model_name": model_name,
                        "estimated_tokens": estimated_tokens,
                        "context_limit": context_limit,
                        "will_exceed": will_exceed,
                        "provider": provider,
                        "is_estimate": True
                    }
                    providers_tested[provider] = True
            
            return {
                "success": True,
                "file_path": file_path,
                "sample_prompt": sample_prompt,
                "provider_results": results
            }
            
        except Exception as e:
            logging.error(f"Error in _count_tokens_for_csv: {e}")
            return self._fallback_to_estimates(file_path, sample_prompt, model_names)
    
    def _count_tokens_for_pdf(self, file_path: str, sample_prompt: str, model_names: list) -> dict:
        """Count tokens for PDF files using proper text extraction and provider APIs."""
        try:
            from token_validator import get_provider_from_model
            from models_openai import count_tokens_openai, get_context_limit_openai
            from models_anthropic import count_tokens_anthropic, get_context_limit_anthropic  
            from models_google import count_tokens_google, get_context_limit_google
            
            # Extract text from PDF
            pdf_text = self._extract_pdf_text(file_path)
            if not pdf_text:
                logging.warning(f"No text extracted from PDF: {file_path}")
                return self._fallback_to_estimates(file_path, sample_prompt, model_names)
            
            # Combine prompt + PDF text (only once!)
            full_text = f"{sample_prompt}\n\n{pdf_text}"
            
            # Debug logging
            logging.info(f"PDF text: {len(pdf_text)} chars, Full prompt: {len(full_text)} chars")
            
            # Get unique providers and test one model per provider
            provider_models = {}
            for model_name in model_names:
                provider = get_provider_from_model(model_name)
                if provider not in provider_models:
                    provider_models[provider] = model_name
            
            results = {}
            
            # Test each provider separately
            for provider, model_name in provider_models.items():
                try:
                    logging.info(f"Testing {provider} with model {model_name}")
                    
                    if provider == "openai":
                        content = [{"type": "input_text", "text": full_text}]
                        actual_tokens = count_tokens_openai(content, model_name)
                        context_limit = get_context_limit_openai(model_name)
                        
                    elif provider == "anthropic":
                        content = [{"type": "text", "text": full_text}]
                        actual_tokens = count_tokens_anthropic(content, model_name)
                        context_limit = get_context_limit_anthropic(model_name)
                        
                    elif provider == "google":
                        # Use updated model names
                        if model_name == "gemini-2.5-pro":
                            model_name = "gemini-2.5-pro-preview-06-05"
                        elif model_name == "gemini-2.5-flash":
                            model_name = "gemini-2.5-flash-preview-05-20"
                            
                        from google import genai
                        contents = [
                            genai.types.Content(
                                role="user",
                                parts=[genai.types.Part.from_text(text=full_text)]
                            )
                        ]
                        actual_tokens = count_tokens_google(contents, model_name)
                        context_limit = get_context_limit_google(model_name)
                        
                    else:
                        logging.warning(f"Unknown provider: {provider}")
                        continue
                    
                    logging.info(f"{provider} tokens: {actual_tokens}")
                    
                    will_exceed = actual_tokens > context_limit
                    
                    results[provider] = {
                        "model_name": model_name,
                        "actual_tokens": actual_tokens,
                        "context_limit": context_limit,
                        "will_exceed": will_exceed,
                        "provider": provider
                    }
                    
                except Exception as e:
                    logging.error(f"Error counting tokens for {provider}: {e}")
                    # Fall back to estimates for this provider only
                    estimated_tokens = self._estimate_file_tokens(file_path, sample_prompt)
                    context_limit = self._get_context_limit_for_model(model_name)
                    will_exceed = estimated_tokens > context_limit
                    
                    results[provider] = {
                        "model_name": model_name,
                        "estimated_tokens": estimated_tokens,
                        "context_limit": context_limit,
                        "will_exceed": will_exceed,
                        "provider": provider,
                        "is_estimate": True
                    }
            
            return {
                "success": True,
                "file_path": file_path,
                "sample_prompt": sample_prompt,
                "provider_results": results
            }
            
        except Exception as e:
            logging.error(f"Error in _count_tokens_for_pdf: {e}")
            return self._fallback_to_estimates(file_path, sample_prompt, model_names)
    
    def _estimate_file_tokens(self, file_path: str, sample_prompt: str) -> int:
        """Estimate token count for a file based on size and content."""
        try:
            from pathlib import Path
            import json
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return 1000  # Default fallback
                
            if file_path.lower().endswith('.csv'):
                # For CSV files, try to get more accurate estimates
                try:
                    from file_store import get_file_details_by_path
                    file_details = get_file_details_by_path(file_path)
                    if file_details and file_details.get('csv_data'):
                        csv_data = json.loads(file_details['csv_data'])
                        if isinstance(csv_data, dict):
                            total_rows = csv_data.get('total_rows', 0)
                            columns = csv_data.get('columns', [])
                            # Estimate tokens: roughly 1 token per 3.5 characters
                            chars_per_row = len(columns) * 15  # Average 15 chars per field
                            total_chars = (total_rows * chars_per_row) + len(sample_prompt)
                            return int(total_chars / 3.5)
                except Exception:
                    pass
                    
            # Fallback: estimate based on file size
            file_size = file_path_obj.stat().st_size
            # Rough estimate: 1 token per 4 bytes for text files
            estimated_tokens = int(file_size / 4) + len(sample_prompt.split())
            return max(estimated_tokens, 100)  # Minimum 100 tokens
            
        except Exception as e:
            logging.error(f"Error estimating tokens for {file_path}: {e}")
            return 1000  # Safe fallback
    
    def _get_context_limit_for_model(self, model_name: str) -> int:
        """Get context limit for a specific model."""
        limits = {
            # OpenAI models
            'gpt-4o': 128000,
            'gpt-4o-mini': 128000,
            'o3': 200000,
            'o4-mini': 200000,
            'gpt-4.1': 1047576,
            'gpt-4.1-mini': 1047576,
            'gpt-4.1-nano': 1047576,
            
            # Anthropic models (all 200K)
            'claude-3-5-haiku-20241022': 200000,
            'claude-3-7-sonnet-20250219': 200000,
            'claude-3-7-sonnet-20250219-thinking': 200000,
            'claude-sonnet-4-20250514': 200000,
            'claude-sonnet-4-20250514-thinking': 200000,
            'claude-opus-4-20250514': 200000,
            'claude-opus-4-20250514-thinking': 200000,
            
            # Google models
            'gemini-2.5-flash-preview-05-20': 1000000,
            'gemini-2.5-pro-preview-06-05': 1000000,
        }
        
        return limits.get(model_name, 128000)  # Conservative default
    
    def _convert_csv_to_text(self, file_path: str) -> str:
        """Convert CSV file to Hybrid Structured Format for token-efficient representation."""
        try:
            from file_store import get_file_details_by_path
            import json
            
            # Get file details from database
            file_details = get_file_details_by_path(file_path)
            if not file_details or not file_details.get('csv_data'):
                # Fall back to reading the file directly
                return self._read_csv_file_directly(file_path, full_content=True)
            
            # Parse the stored CSV data
            csv_data = json.loads(file_details['csv_data'])
            
            if isinstance(csv_data, dict) and 'records' in csv_data:
                # New format with records - use Hybrid Structured Format
                records = csv_data['records']
                columns = csv_data.get('columns', [])
                
                lines = []
                
                # Header with metadata
                lines.append(f"Dataset: {len(records)} records")
                lines.append(f"Columns: {', '.join(columns)}")
                
                for i in range(len(records)):
                    record = records[i]
                    if isinstance(record, dict):
                        row_values = [str(record.get(col, '')) for col in columns]
                        lines.append(" | ".join(row_values))
                    else:
                        lines.append(str(record))
                    
                return "\n".join(lines)
                
            elif isinstance(csv_data, list):
                # Legacy format - use Hybrid Structured Format
                lines = []
                
                # Header with metadata
                lines.append(f"Dataset: {len(csv_data)} records")
                lines.append("")
                for i in range(len(csv_data)):
                    lines.append(str(csv_data[i]))
                    
                return "\n".join(lines)
            
            else:
                # Fallback for unknown format
                return f"CSV Data: {str(csv_data)}"
                
        except Exception as e:
            logging.error(f"Error converting CSV to text: {e}")
            return self._read_csv_file_directly(file_path, full_content=True)
    
    def _read_csv_file_directly(self, file_path: str, full_content: bool = False) -> str:
        """Read CSV file directly and convert to Hybrid Structured Format."""
        try:
            import csv
            from pathlib import Path
            
            if not Path(file_path).exists():
                return ""
            
            lines = []
            all_rows = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                
                # Get column names
                fieldnames = csv_reader.fieldnames or []
                
                # Read all rows into memory
                for row in csv_reader:
                    all_rows.append(row)
            
            total_rows = len(all_rows)
            
            if full_content:
                # Use Hybrid Structured Format for token counting
                lines.append(f"Dataset: {total_rows} records")
                lines.append(f"Columns: {', '.join(fieldnames)}")
                lines.append("")
                for i in range(total_rows):
                    row = all_rows[i]
                    row_values = [str(row.get(col, '')) for col in fieldnames]
                    lines.append(" | ".join(row_values))
            
            else:
                # Preview format (for UI display - keep existing format)
                lines.append("CSV Data Analysis:")
                lines.append(f"Columns: {', '.join(fieldnames)}")
                lines.append("")
                
                if fieldnames:
                    lines.append(" | ".join(fieldnames))
                    lines.append("-" * (len(" | ".join(fieldnames))))
                
                # Show first 5 rows for preview
                for i, row in enumerate(all_rows[:5]):
                    row_values = [str(row.get(col, '')) for col in fieldnames]
                    lines.append(" | ".join(row_values))
            
            return "\n".join(lines)
            
        except Exception as e:
            logging.error(f"Error reading CSV file directly: {e}")
            return f"CSV file: {file_path} (could not read content)"
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text content from PDF file using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
            from pathlib import Path
            
            if not Path(file_path).exists():
                logging.error(f"PDF file not found: {file_path}")
                return ""
            
            pdf_reader = PdfReader(file_path)
            page_texts = []
            
            # Extract text from each page
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text().strip()
                    if page_text:
                        # Just include the text, no page headers to reduce token usage
                        page_texts.append(page_text)
                except Exception as e:
                    logging.warning(f"Error extracting page {page_num + 1}: {e}")
                    continue
            
            if not page_texts:
                logging.warning(f"No text extracted from PDF: {file_path}")
                return ""
            
            # Join pages with simple separator
            full_text = "\n\n".join(page_texts)
            logging.info(f"Extracted {len(full_text)} chars from {len(page_texts)} pages")
            
            return full_text
            
        except Exception as e:
            logging.error(f"Error extracting PDF text: {e}")
            return ""
    
    def _fallback_to_estimates(self, file_path: str, sample_prompt: str, model_names: list) -> dict:
        """Fallback to estimated token counts when APIs fail."""
        try:
            from token_validator import get_provider_from_model
            
            providers_tested = {}
            results = {}
            
            for model_name in model_names:
                provider = get_provider_from_model(model_name)
                
                # Skip if we already tested this provider
                if provider in providers_tested:
                    continue
                
                estimated_tokens = self._estimate_file_tokens(file_path, sample_prompt)
                context_limit = self._get_context_limit_for_model(model_name)
                will_exceed = estimated_tokens > context_limit
                
                results[provider] = {
                    "model_name": model_name,
                    "estimated_tokens": estimated_tokens,
                    "context_limit": context_limit,
                    "will_exceed": will_exceed,
                    "provider": provider,
                    "is_estimate": True
                }
                providers_tested[provider] = True
            
            return {
                "success": True,
                "file_path": file_path,
                "sample_prompt": sample_prompt,
                "provider_results": results
            }
            
        except Exception as e:
            logging.error(f"Error in _fallback_to_estimates: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def validate_tokens(self, prompts: list, pdfPaths: list, modelNames: list) -> dict:
        """Delegate to token manager for validation."""
        return self.token_manager.validate_tokens(prompts, pdfPaths, modelNames)

    def get_model_token_budget(self, model_name: str) -> int:
        """Delegate to token manager for budget calculation."""
        return self.token_manager.get_model_token_budget(model_name)

    def process_csv_for_model(self, csv_file_path: str, model_name: str) -> dict:
        """Delegate to token manager for CSV processing."""
        return self.token_manager.process_csv_for_model(csv_file_path, model_name)

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
            # Using self.db_path property instead
            from file_store import get_benchmark_sync_status
            
            sync_status = get_benchmark_sync_status(benchmark_id, self.db_path)
            
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
                
                # Use the helper method to create and start worker
                worker, worker_key = self._create_and_start_worker(
                    job_id=job_id,
                    benchmark_id=benchmark_id,
                    prompts=prompts_for_worker,
                    pdf_paths=file_paths,
                    model_name=model_name,
                    web_search_enabled=benchmark_details.get('use_web_search', False)
                )
                
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
            # Using self.db_path property instead
            from file_store import get_benchmark_sync_status
            
            sync_status = get_benchmark_sync_status(benchmark_id, db_path)
            
            if "error" in sync_status:
                return {"success": False, "error": sync_status["error"]}
            
            return {"success": True, "sync_status": sync_status}
            
        except Exception as e:
            error_msg = f"Error getting sync status for benchmark {benchmark_id}: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    # ===== VECTOR SEARCH METHODS =====

    def handle_create_vector_store(self, name: str, description: str = None, 
                                  file_ids: List[int] = None, 
                                  expires_after_days: int = None) -> dict:
        """Create a new vector store."""
        try:
            from models_openai import create_vector_store_from_files
            
            # Get file paths from file IDs
            file_paths = []
            if file_ids:
                for file_id in file_ids:
                    file_details = get_file_details(file_id)
                    if file_details:
                        file_paths.append(Path(file_details['file_path']))
                    else:
                        return {"success": False, "error": f"File with ID {file_id} not found"}
            
            # Create vector store
            vector_store_id = create_vector_store_from_files(
                name=name,
                file_paths=file_paths,
                description=description,
                expires_after_days=expires_after_days
            )
            
            return {
                "success": True, 
                "vector_store_id": vector_store_id,
                "message": f"Vector store '{name}' created successfully"
            }
            
        except Exception as e:
            error_msg = f"Error creating vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_get_vector_stores(self) -> dict:
        """Get all vector stores."""
        try:
            vector_stores = get_all_vector_stores()
            return {"success": True, "vector_stores": vector_stores}
        except Exception as e:
            error_msg = f"Error getting vector stores: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_get_vector_store_details(self, vector_store_id: str) -> dict:
        """Get details of a specific vector store."""
        try:
            vector_store = get_vector_store_by_id(vector_store_id)
            if not vector_store:
                return {"success": False, "error": "Vector store not found"}
            
            # Get files in the vector store
            files = get_vector_store_files(vector_store_id)
            vector_store["files"] = files
            
            return {"success": True, "vector_store": vector_store}
        except Exception as e:
            error_msg = f"Error getting vector store details: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_add_files_to_vector_store(self, vector_store_id: str, 
                                        file_ids: List[int]) -> dict:
        """Add files to an existing vector store."""
        try:
            from vector_search import VectorSearchManager
            
            # Get file paths from file IDs
            file_paths = []
            for file_id in file_ids:
                file_details = get_file_details(file_id)
                if file_details:
                    file_paths.append(Path(file_details['file_path']))
                else:
                    return {"success": False, "error": f"File with ID {file_id} not found"}
            
            # Add files to vector store
            vector_manager = VectorSearchManager()
            added_files = vector_manager.add_files_to_vector_store(
                vector_store_id=vector_store_id,
                file_paths=file_paths
            )
            
            # Register files in local database
            from file_store import get_provider_file_id
            for file_path, file_id in zip(file_paths, file_ids):
                provider_file_id = get_provider_file_id(file_id, "openai")
                if provider_file_id:
                    register_vector_store_file(
                        vector_store_id=vector_store_id,
                        file_id=file_id,
                        provider_file_id=provider_file_id
                    )
            
            return {
                "success": True, 
                "added_files": len(added_files),
                "message": f"Added {len(added_files)} files to vector store"
            }
            
        except Exception as e:
            error_msg = f"Error adding files to vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_search_vector_store(self, vector_store_id: str, query: str, 
                                  max_results: int = 10) -> dict:
        """Search a vector store directly."""
        try:
            from models_openai import search_vector_store_direct
            
            results = search_vector_store_direct(
                vector_store_id=vector_store_id,
                query=query,
                max_results=max_results
            )
            
            return {"success": True, "results": results}
            
        except Exception as e:
            error_msg = f"Error searching vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_ask_vector_store(self, vector_store_ids: List[str], question: str,
                               model: str = "gpt-4o-mini", 
                               max_results: int = 20) -> dict:
        """Ask a question using vector search."""
        try:
            from models_openai import openai_ask_with_vector_search
            
            # Perform vector search
            result = openai_ask_with_vector_search(
                vector_store_ids=vector_store_ids,
                prompt_text=question,
                model_name=model,
                max_results=max_results,
                include_search_results=True
            )
            
            answer, input_tokens, cached_tokens, output_tokens, reasoning_tokens, file_search_used, search_sources, citations = result
            
            return {
                "success": True,
                "answer": answer,
                "tokens": {
                    "input": input_tokens,
                    "cached": cached_tokens,
                    "output": output_tokens,
                    "reasoning": reasoning_tokens
                },
                "search_sources": search_sources,
                "citations": citations,
                "file_search_used": file_search_used
            }
            
        except Exception as e:
            error_msg = f"Error asking vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_delete_vector_store(self, vector_store_id: str) -> dict:
        """Delete a vector store."""
        try:
            from vector_search import VectorSearchManager
            
            # Delete from OpenAI
            vector_manager = VectorSearchManager()
            deleted = vector_manager.delete_vector_store(vector_store_id)
            
            if deleted:
                # Delete from local database
                delete_vector_store(vector_store_id)
                return {"success": True, "message": "Vector store deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete vector store from OpenAI"}
                
        except Exception as e:
            error_msg = f"Error deleting vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_associate_benchmark_vector_store(self, benchmark_id: int, 
                                               vector_store_id: str) -> dict:
        """Associate a benchmark with a vector store."""
        try:
            success = associate_benchmark_with_vector_store(benchmark_id, vector_store_id)
            if success:
                return {"success": True, "message": "Benchmark associated with vector store"}
            else:
                return {"success": False, "error": "Failed to associate benchmark with vector store"}
                
        except Exception as e:
            error_msg = f"Error associating benchmark with vector store: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}

    def handle_get_benchmark_vector_stores(self, benchmark_id: int) -> dict:
        """Get vector stores associated with a benchmark."""
        try:
            vector_stores = get_benchmark_vector_stores(benchmark_id)
            return {"success": True, "vector_stores": vector_stores}
        except Exception as e:
            error_msg = f"Error getting benchmark vector stores: {str(e)}"
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