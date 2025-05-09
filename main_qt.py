import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QTimer # For safe cross-thread UI updates if needed, or direct calls if simple

from ui_bridge import AppUIBridge
from app import AppLogic  # The refactored, Qt-agnostic AppLogic
from qt_ui import MainWindow # Your existing MainWindow
from ui_styles import APP_STYLESHEET # Existing styles

class QtUIBridgeImpl(AppUIBridge):
    def __init__(self, main_window: MainWindow):
        self.main_window = main_window
        # These callbacks are not used by the bridge itself in the current design
        # self._worker_progress_callback: Optional[Callable[[str], None]] = None 
        # self._worker_finished_callback: Optional[Callable[[dict], None]] = None

    def show_message(self, level: str, title: str, message: str) -> None:
        # This can be called from AppLogic.handle_run_finished (worker thread) or other places.
        # Ensure thread safety for all calls that might originate from a worker thread.
        QTimer.singleShot(0, lambda: self.main_window.show_message_box(level, title, message))

    def update_status_bar(self, message: str, timeout: int = 0) -> None:
        # This can be called from AppLogic.handle_run_finished (worker thread) or launch_benchmark_run (GUI thread).
        # Ensure thread safety.
        QTimer.singleShot(0, lambda: self.main_window.update_status_bar(message, timeout))

    def clear_console_log(self) -> None:
        # Typically called before a new run (GUI thread) or if displaying details (GUI thread).
        # If it could ever be called from a worker context, use QTimer. For now, assuming GUI thread calls.
        self.main_window.clear_console_log()

    def update_console_log(self, text: str) -> None:
        # Called from AppLogic.handle_benchmark_progress (worker thread).
        # Must be thread-safe.
        QTimer.singleShot(0, lambda: self.main_window.update_console_log(text))


    def show_home_page(self) -> None:
        # Typically called from GUI thread (e.g. button clicks, startup).
        self.main_window.show_home_page()
        
    def show_composer_page(self) -> None:
        # QTimer.singleShot(0, self.main_window.show_composer_page)
        self.main_window.show_composer_page()

    def show_console_page(self) -> None:
        # QTimer.singleShot(0, self.main_window.show_console_page)
        self.main_window.show_console_page()

    def populate_composer_table(self, rows: List[List[str]]) -> None:
        # Called when CSV is loaded, typically from a GUI thread interaction.
        self.main_window.populate_composer_table(rows)

    def display_benchmark_summary_in_console(self, result: Dict[str, Any], run_id: Optional[Any]) -> None:
        # Called from AppLogic.handle_run_finished (worker thread).
        # Must be thread-safe.
        QTimer.singleShot(0, lambda: self.main_window.display_benchmark_summary_in_console(result, run_id))


    def display_full_benchmark_details_in_console(self, details: Dict[str, Any]) -> None:
        # Called when a benchmark is selected from the list (GUI thread).
        self.main_window.display_full_benchmark_details_in_console(details)

    def get_csv_file_path_via_dialog(self) -> Optional[Path]:
        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Open CSV Prompts File",
            str(Path.home()), # Default to user's home directory
            "CSV files (*.csv)"
        )
        return Path(file_path_str) if file_path_str else None

    def get_pdf_file_path_via_dialog(self, start_dir_str: str) -> Optional[Path]:
        # start_dir_str is passed from ComposerPage's self.select_pdf_file logic
        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Select PDF for Benchmark",
            start_dir_str,
            "PDF Files (*.pdf)"
        )
        return Path(file_path_str) if file_path_str else None
    
    # The UI bridge itself doesn't need these in this design, AppLogic calls them directly
    # on the UI bridge instance when it gets them from the actual UI elements.
    def get_composer_prompts(self) -> List[Dict[str, str]]:
        return self.main_window.composer.get_prompt_rows()

    def get_selected_pdf(self) -> Optional[Path]:
        return self.main_window.composer.selected_pdf_path

    # --- Methods for active benchmark updates ---
    def notify_active_benchmarks_updated(self, active_benchmarks_data: Dict[Any, Dict[str, Any]]) -> None:
        # Ensure this is called on the main Qt thread if HomePage updates are not thread-safe
        # AppLogic calls this. AppLogic's handle_benchmark_progress is called by BenchmarkWorker (thread)
        # So, this notify method will be called from a worker thread.
        # Thus, emitting the signal should be done via QTimer to ensure it happens on the main thread.
        QTimer.singleShot(0, lambda: self.main_window.active_benchmarks_changed.emit(active_benchmarks_data))

    # These are not used from ui_bridge.py, removing
    # def register_benchmark_worker_callbacks(self, worker_progress_callback: callable, worker_finished_callback: callable) -> None:
    #     self._worker_progress_callback = worker_progress_callback
    #     self._worker_finished_callback = worker_finished_callback

    # def handle_worker_progress(self, message: str) -> None:
    #     if self._worker_progress_callback:
    #         QTimer.singleShot(0, lambda: self._worker_progress_callback(message))


    # def handle_worker_finished(self, result: dict) -> None:
    #     if self._worker_finished_callback:
    #         QTimer.singleShot(0, lambda: self._worker_finished_callback(result))


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    main_window = MainWindow()
    qt_bridge = QtUIBridgeImpl(main_window)
    app_logic = AppLogic(qt_bridge) # Pass the bridge to AppLogic

    # Connect MainWindow signals to AppLogic methods (or bridge methods that call AppLogic)
    # AppLogic methods are now designed to be called directly.
    main_window.new_benchmark_requested.connect(qt_bridge.show_composer_page) # Or app_logic.request_new_benchmark_page
    main_window.open_csv_requested.connect(app_logic.request_open_csv_file)
    
    # For run_benchmark_requested, AppLogic's launch_benchmark_run now takes prompts and pdf_path.
    # The UI (MainWindow) will emit these. QtUIBridge can fetch them.
    # The MainWindow.run_benchmark_requested signal emits (list, Path), matching AppLogic.launch_benchmark_run
    main_window.run_benchmark_requested.connect(app_logic.launch_benchmark_run)

    # The show_home_requested signal from MainWindow should call app_logic.request_show_home_page or similar
    # or directly call qt_bridge.show_home_page if AppLogic doesn't need to do anything.
    # AppLogic now has a startup() method that shows home page.
    # If home button is clicked, AppLogic might need to be involved if it reloads data.
    # For now, let's assume showing home page might involve logic to refresh it.
    main_window.show_home_requested.connect(qt_bridge.show_home_page) 
                                            # This calls main_window.home.load_runs_from_db()

    main_window.benchmark_selected.connect(app_logic.request_display_benchmark_details)

    # The select_pdf_button in ComposerPage needs to use the bridge for dialog
    # Original qt_ui.py: self.select_pdf_button.clicked.connect(self.select_pdf_file)
    # self.select_pdf_file shows dialog and sets self.selected_pdf_path & label
    # This part of qt_ui.py can remain as is, since it's UI-internal state management for the composer.
    # The bridge's get_selected_pdf() will retrieve it.
    # However, if we want AppLogic to initiate PDF selection, that's different.
    # The current `main_window.composer.select_pdf_button` is fine.

    main_window.show()
    app_logic.startup() # Call startup to show the initial page (e.g., home)

    sys.exit(app.exec())

if __name__ == "__main__":
    main() 