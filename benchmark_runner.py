"""
Benchmark Runner Module

This module contains the BenchmarkWorker class that handles running benchmarks
in separate threads, providing progress updates and result callbacks.
"""

import sys
import os
import time
import json
import logging
import tempfile
import subprocess
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable


class BenchmarkWorker(threading.Thread):
    """Worker thread for running benchmarks in the background."""
    
    def __init__(self, job_id: int, benchmark_id: int, prompts: List[Dict], pdf_paths: List[str], 
                 model_name: str, on_progress: Optional[Callable] = None, 
                 on_finished: Optional[Callable] = None, web_search_enabled: bool = False, 
                 single_prompt_id: Optional[int] = None):
        """
        Initialize the BenchmarkWorker.
        
        Args:
            job_id: Unique job identifier
            benchmark_id: Benchmark database ID
            prompts: List of prompt dictionaries
            pdf_paths: List of PDF file paths to include
            model_name: Name of the AI model to use
            on_progress: Callback for progress updates
            on_finished: Callback for completion
            web_search_enabled: Whether to enable web search
            single_prompt_id: For single prompt reruns
        """
        super().__init__(name=f"BenchmarkWorker-{job_id}-{model_name}", daemon=True)
        self.job_id = job_id
        self.benchmark_id = benchmark_id
        self.prompts = prompts
        self.pdf_paths = pdf_paths
        self.model_name = model_name
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.web_search_enabled = web_search_enabled
        self.single_prompt_id = single_prompt_id
        self.active = True  # Single source of truth for worker state
        self._original_emit_progress_callback = None
        
        print(f"BenchmarkWorker initialized with job_id={job_id}, benchmark_id={benchmark_id}, model={model_name}, web_search_enabled={web_search_enabled}")
        if single_prompt_id:
            print(f"   Single prompt rerun mode for prompt ID: {single_prompt_id}")
        sys.stdout.flush()
        logging.info(f"BenchmarkWorker created: {self.name} with {len(prompts)} prompts for model {model_name}")

    def run(self):
        """Main execution method for the worker thread."""
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
        # Handle PyInstaller bundled vs development paths
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            script_path = os.path.join(sys._MEIPASS, 'direct_benchmark.py')
        else:
            # Running in development
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
            # Use current executable (works in both dev and packaged)
            sys.executable if not getattr(sys, 'frozen', False) else sys.executable,
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
            # Set up environment for subprocess
            env = os.environ.copy()
            if self.single_prompt_id:
                env['SINGLE_PROMPT_RERUN_ID'] = str(self.single_prompt_id)
                print(f"   Setting SINGLE_PROMPT_RERUN_ID={self.single_prompt_id} for rerun")
                sys.stdout.flush()
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                env=env
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

        # Mark thread as inactive
        self.active = False
        logging.info(f"Thread {self.name}: Finished execution")

    def _emit_progress_override(self, data: Dict[str, Any]):
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
                self.on_progress(data)  # Call with one argument as expected by the lambda
                
        if self._original_emit_progress_callback:
            self._original_emit_progress_callback(data)