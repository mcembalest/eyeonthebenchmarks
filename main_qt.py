import sys
if sys.platform == "darwin":
    try:
        from AppKit import NSApplication, NSImage
        import os
        icon_path = os.path.abspath("assets/icon.icns")
        if os.path.exists(icon_path):
            nsimage = NSImage.alloc().initByReferencingFile_(icon_path)
            if nsimage and nsimage.isValid():
                NSApplication.sharedApplication().setApplicationIconImage_(nsimage)
            else:
                print("Icon image is not valid for Dock.")
        else:
            print("Icon file not found:", icon_path)
    except Exception as e:
        print("Could not set macOS dock icon:", e)

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple

from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QTimer # For safe cross-thread UI updates if needed, or direct calls if simple

from ui_bridge import AppUIBridge
from app import AppLogic  # The refactored, Qt-agnostic AppLogic
from qt_ui import MainWindow # Your existing MainWindow
from ui_styles import APP_STYLESHEET # Existing styles

from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from collections import defaultdict
from ui_bridge import AppUIBridge, DataChangeType

class QtUIBridgeImpl(AppUIBridge):
    def __init__(self, main_window: MainWindow):
        self.main_window = main_window
        self._refresh_timer: Optional[QTimer] = None
        self._data_callbacks: Dict[DataChangeType, List[Callable[[Any], None]]] = defaultdict(list)
        self._current_page = None
        
    def show_message(self, level: str, title: str, message: str) -> None:
        # Ensure UI updates happen on the main thread
        QTimer.singleShot(0, lambda: self._show_message_impl(level, title, message))
        
    def _show_message_impl(self, level: str, title: str, message: str) -> None:
        # Ensure thread safety for all calls that might originate from a worker thread.
        QTimer.singleShot(0, lambda: self.main_window.show_message_box(level, title, message))

    # Auto-refresh implementation
    def start_auto_refresh(self, interval_ms: int = 1000) -> None:
        if not self._refresh_timer:
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self._handle_auto_refresh)
        self._refresh_timer.setInterval(interval_ms)
        self._refresh_timer.start()

    def stop_auto_refresh(self) -> None:
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _handle_auto_refresh(self) -> None:
        # Only refresh active benchmarks data for the home page to minimize visual disruption
        if self._current_page == 'home':
            # Get the latest active benchmarks data without refreshing the entire page
            from engine.file_store import get_active_benchmarks
            active_benchmarks = get_active_benchmarks()
            if hasattr(self.main_window, 'home'):
                QTimer.singleShot(0, lambda: self.main_window.home.update_active_benchmarks_display(active_benchmarks))
        elif self._current_page == 'composer':
            # Minimal refresh for composer page
            self.refresh_composer_page_data()
        elif self._current_page == 'console':
            # Console updates are event-driven, no need for polling refresh
            pass

    # Observer pattern implementation
    def register_data_callback(self, change_type: DataChangeType, callback: Callable[[Any], None]) -> None:
        self._data_callbacks[change_type].append(callback)

    def unregister_data_callback(self, change_type: DataChangeType, callback: Callable[[Any], None]) -> None:
        if callback in self._data_callbacks[change_type]:
            self._data_callbacks[change_type].remove(callback)

    def notify_data_change(self, change_type: DataChangeType, data: Any) -> None:
        # Execute callbacks on the main thread
        for callback in self._data_callbacks[change_type]:
            QTimer.singleShot(0, lambda cb=callback: cb(data))

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
        # Must be thread-safe, with forced refresh to ensure real-time updates.
        QTimer.singleShot(0, lambda: self._update_console_with_refresh(text))
        
    def _update_console_with_refresh(self, text: str) -> None:
        # Update the console text
        self.main_window.update_console_log(text)
        # Force the application to process events to update the UI immediately
        QApplication.processEvents()


    def show_home_page(self) -> None:
        self._current_page = 'home'
        QTimer.singleShot(0, lambda: self.main_window.stack.setCurrentWidget(self.main_window.home))
        self.refresh_home_page_data()

    def show_composer_page(self) -> None:
        self._current_page = 'composer'
        QTimer.singleShot(0, lambda: self.main_window.stack.setCurrentWidget(self.main_window.composer))
        self.refresh_composer_page_data()

    def show_console_page(self) -> None:
        self._current_page = 'console'
        QTimer.singleShot(0, lambda: self.main_window.stack.setCurrentWidget(self.main_window.console))
        self.refresh_console_page_data()

    def refresh_home_page_data(self) -> None:
        # Notify observers about the refresh request
        self.notify_data_change(DataChangeType.BENCHMARK_LIST, None)
        # Update active benchmarks display
        if hasattr(self.main_window, 'home'):
            QTimer.singleShot(0, lambda: self.main_window.home.update_active_benchmarks_display(
                self.main_window.home._active_benchmarks_data
            ))

    def refresh_composer_page_data(self) -> None:
        self.notify_data_change(DataChangeType.COMPOSER_DATA, None)
        # Any composer-specific refresh logic here

    def refresh_console_page_data(self) -> None:
        # Console data is typically event-driven (benchmark results)
        # but we could refresh any persistent data here
        pass

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

    # --- Method to populate home page benchmark table ---
    def populate_home_benchmarks_table(self, benchmarks_data: Optional[List[Tuple]] = None) -> None:
        # HomePage is responsible for loading its own data. This call just triggers it.
        QTimer.singleShot(0, lambda: self.main_window.home.load_runs_from_db())

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