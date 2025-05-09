import sys
from datetime import datetime
from pathlib import Path
import os
import csv
import threading # Added for threading.Thread

# Removed PySide6 imports for QThread, Signal, Slot as they are being decoupled from AppLogic
# from PySide6.QtWidgets import QApplication, QFileDialog, QTableWidgetItem
# from PySide6.QtCore import QThread, Signal, Slot

# UI components - will be managed by the UI layer (e.g., main_qt.py)
# from qt_ui import MainWindow
# Styles - will be managed by the UI layer
# from ui_styles import APP_STYLESHEET

# Engine components
from engine.file_store import init_db as init_file_store_db
from engine.file_store import save_benchmark_run, load_benchmark_details
# engine.runner is imported within BenchmarkWorker to allow monkeypatching

# Import the UI bridge protocol
from ui_bridge import AppUIBridge


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
        self.active_benchmarks = {} # {run_id: {'pdf_name': str, 'current_prompt': int, 'total_prompts': int, 'start_time': datetime}}
        self._next_run_id = 0 # Simple way to generate unique IDs for active runs

        # Initial setup
        self._initialize_database()
        self._ensure_directories_exist()
        
        # The UI layer is responsible for showing the initial page.
        # self.ui_bridge.show_home_page() # This could be called by the runner after AppLogic init

    def _initialize_database(self):
        try:
            init_file_store_db()
        except Exception as e:
            print(f"CRITICAL: Failed to initialize file store database: {e}")
            self.ui_bridge.show_message( # Use UI bridge
                "critical", 
                "Database Error", 
                f"Could not initialize the file store database: {e}. The application might not work correctly."
            )

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
    def launch_benchmark_run(self, prompts: list, pdf_to_run: Path, model_names: list): # Changed model_name to model_names list
        if not prompts:
            self.ui_bridge.show_message("warning", "No prompts", "Please enter at least one prompt.")
            return
        if not pdf_to_run:
            self.ui_bridge.show_message("warning", "No PDF", "Please select a PDF file for the benchmark.")
            return
        if not model_names: # Basic check for model_names list
            self.ui_bridge.show_message("warning", "No Model(s) Selected", "Please select at least one model for the benchmark.")
            return

        # For now, backend processes one model. Take the first one.
        model_to_run = model_names[0]

        run_label = datetime.now().strftime("%H:%M:%S")
        current_run_id = self._next_run_id
        self._next_run_id += 1

        self.active_benchmarks[current_run_id] = {
            'pdf_name': pdf_to_run.name,
            'current_prompt': 0,
            'total_prompts': len(prompts),
            'start_time': datetime.now(),
            'status_message': 'Initializing...'
        }
        # Notify UI about the new active benchmark and any other changes
        if hasattr(self.ui_bridge, 'notify_active_benchmarks_updated'):
             self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())

        self.ui_bridge.clear_console_log()
        self.ui_bridge.update_console_log(f"[{current_run_id}] Running benchmark with {pdf_to_run.name} at {run_label}...\n")
        self.ui_bridge.show_console_page()
        self.ui_bridge.update_status_bar(f"Benchmark [{current_run_id}] {run_label} starting with {pdf_to_run.name}")

        self.worker = BenchmarkWorker(
            prompts,
            pdf_to_run,
            model_to_run, # Pass the first selected model to the worker
            # Pass current_run_id to callbacks so they know which benchmark to update
            on_progress=lambda progress_data: self.handle_benchmark_progress(current_run_id, progress_data),
            on_finished=lambda result_data: self.handle_run_finished(current_run_id, result_data)
        )
        self.worker.start()

    def handle_benchmark_progress(self, run_id: int, progress_data: dict):
        # Assuming progress_data is now like {'current': int, 'total': int, 'message': str}
        if run_id in self.active_benchmarks:
            self.active_benchmarks[run_id]['current_prompt'] = progress_data.get('current', 0)
            self.active_benchmarks[run_id]['status_message'] = progress_data.get('message', '')
            # Notify UI about the updated active benchmark
            if hasattr(self.ui_bridge, 'notify_active_benchmarks_updated'):
                self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        
        # Still send raw message to console log if desired
        self.ui_bridge.update_console_log(f"[{run_id}] {progress_data.get('message', 'Progress update...')}\n")

    def handle_run_finished(self, run_id: int, result: dict):
        print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] Received result: {result}") # Log the received result

        if not self.worker: # This check might need to be per-run if multiple workers are supported
            self.ui_bridge.show_message("critical", "Worker Error", "Benchmark worker not found during finish.")
            if run_id in self.active_benchmarks:
                del self.active_benchmarks[run_id]
                if hasattr(self.ui_bridge, 'notify_active_benchmarks_updated'):
                    self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
            return
        
        pdf_path_from_result = result.get('pdf_path')
        pdf_path_to_use = None
        if pdf_path_from_result:
            pdf_path_to_use = Path(pdf_path_from_result)
        elif self.worker:
            pdf_path_to_use = self.worker.pdf_path
        
        print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] PDF path to use for saving: {pdf_path_to_use}")

        if result.get("error"):
            error_message = f"Benchmark [{run_id}] failed for {pdf_path_to_use.name if pdf_path_to_use else 'Unknown PDF'}: {result['error']}"
            self.ui_bridge.show_message("critical", "Benchmark Error", error_message)
            self.ui_bridge.update_status_bar(error_message, 5000)
            summary_for_console = {
                'error': result['error'], 
                'message': error_message
            }
            self.ui_bridge.display_benchmark_summary_in_console(summary_for_console, f"Failed Run {run_id}")
        else:
            saved_db_id = None
            if pdf_path_to_use:
                try:
                    print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] Attempting to save benchmark with pdf_path: {pdf_path_to_use} and result: {result}")
                    saved_db_id = save_benchmark_run(pdf_path_to_use, result)
                    print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] save_benchmark_run returned ID: {saved_db_id}")
                    if saved_db_id:
                        self.ui_bridge.update_status_bar(f"Benchmark [{run_id}] run saved with DB ID: {saved_db_id}", 5000)
                    else:
                        self.ui_bridge.update_status_bar(f"Benchmark [{run_id}] failed to save to database.", 5000)
                        self.ui_bridge.show_message("warning", "DB Error", f"Could not save benchmark [{run_id}] results to the database.")
                except Exception as e:
                    print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] Exception during save_benchmark_run: {e}") # Log exception
                    self.ui_bridge.update_status_bar(f"Error saving benchmark [{run_id}]: {e}", 5000)
                    self.ui_bridge.show_message("critical", "Save Error", f"Error saving benchmark [{run_id}] to database: {e}")
            else:
                print(f"[AppLogic.handle_run_finished RUN_ID: {run_id}] PDF path was None. Cannot save.") # Log if PDF path is None
                self.ui_bridge.update_status_bar(f"Error: PDF path not found for benchmark [{run_id}], cannot save.", 5000)
                self.ui_bridge.show_message("critical", "Save Error", f"Critical error: PDF path not found for benchmark [{run_id}], not saved.")

            summary_result_for_console = result.copy()
            self.ui_bridge.display_benchmark_summary_in_console(summary_result_for_console, f"Run {run_id} (DB ID: {saved_db_id})")
            self.ui_bridge.update_status_bar(f"Benchmark [{run_id}] completed.", 5000)

        # Clean up from active_benchmarks
        if run_id in self.active_benchmarks:
            del self.active_benchmarks[run_id]
            if hasattr(self.ui_bridge, 'notify_active_benchmarks_updated'):
                self.ui_bridge.notify_active_benchmarks_updated(self.get_active_benchmarks_info())
        
        # Potentially switch back to home page or refresh home page view
        # self.ui_bridge.show_home_page() 

    def get_active_benchmarks_info(self) -> dict:
        return self.active_benchmarks.copy() # Return a copy

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