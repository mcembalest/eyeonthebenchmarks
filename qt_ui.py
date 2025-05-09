import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QToolBar,
    QStatusBar, QFileDialog, QMessageBox, QTextEdit, QScrollArea,
    QListWidget, QListWidgetItem, QProgressBar, QComboBox
)
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Qt, QThread, Signal

# Import styles
from ui_styles import APP_STYLESHEET

# Import database functions - these will be called by the app logic,
# but UI elements might need to trigger them or display their results.
# Actual database interaction logic should ideally be in app.py.
from engine.file_store import load_all_benchmark_runs, load_benchmark_details
from engine.models_openai import AVAILABLE_MODELS

# --- Progress signal for real-time updates --------------------------------
class RunConsoleWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Add a scroll area for the console log
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        # Text area for logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        scroll.setWidget(self.log_text)
        
        layout.addWidget(scroll)
        
        # Add a "Return to Home" button
        self.return_btn = QPushButton("Return to Home") # Made it an instance variable
        layout.addWidget(self.return_btn)

    def update_log(self, text):
        current_text = self.log_text.toPlainText()
        if current_text:
            self.log_text.append(text) # append already adds a newline if text doesn't have one
        else:
            self.log_text.setText(text)
        
        # Ensure the view scrolls to the bottom to show the latest log entry
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # QApplication.processEvents() # Try to force event processing to update the UI
        # Be cautious with processEvents in production code as it can lead to 
        # re-entrancy issues if not handled carefully. 
        # For live logging, it can sometimes help ensure UI updates are seen sooner.
        # If this also doesn't work, the issue might be more complex, related to how QTimer
        # interacts or if events are getting starved.

    def display_benchmark_details(self, details: dict):
        """Displays the full details of a benchmark run."""
        self.log_text.clear()
        if not details:
            self.update_log("Could not load benchmark details.")
            return

        pdf_name = Path(details['pdf_path']).name
        try:
            dt_obj = datetime.fromisoformat(details['timestamp'])
            formatted_time = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            formatted_time = details['timestamp'] # Fallback if parsing fails

        self.update_log(f"----- BENCHMARK DETAILS (ID: {details['id']}) -----")
        self.update_log(f"Run at: {formatted_time}")
        self.update_log(f"PDF: {pdf_name}")
        self.update_log(f"Model: {details.get('model_name', 'N/A')}")
        self.update_log(f"Mean Score: {details.get('mean_score', 'N/A')}")
        self.update_log(f"Total Items: {details.get('total_items', 'N/A')}")
        self.update_log(f"Elapsed Time: {details.get('elapsed_seconds', 'N/A')}s")

        if 'prompts_data' in details and details['prompts_data']:
            self.update_log("\n----- DETAILED RESULTS -----")
            for i, p_data in enumerate(details['prompts_data']):
                self.update_log(f"\nPrompt {i+1}: {p_data['prompt_text']}")
                self.update_log(f"Expected: {p_data['expected_answer']}")
                self.update_log(f"Answer: {p_data['actual_answer']}")
                self.update_log(f"Score: {p_data['score']}")
        else:
            self.update_log("\nNo detailed prompt data available for this run.")

# --- Pages ----------------------------------------------------------------
class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        self._active_benchmarks_data: dict = {} # To store current active benchmark data
        self._progress_bars: dict = {} # To store QProgressBar widgets by run_id

        # Title for previous runs
        self.layout.addWidget(QLabel("Previous Benchmark Runs:"))
        self.previous_runs_list_widget = QListWidget()
        self.previous_runs_list_widget.setStyleSheet("font-size: 17pt; padding: 10px;")
        self.layout.addWidget(self.previous_runs_list_widget)

        # Title and list for active runs
        self.layout.addWidget(QLabel("Active Benchmarks:")) 
        self.active_runs_list_widget = QListWidget()
        self.active_runs_list_widget.setStyleSheet("font-size: 17pt; padding: 10px;") # Keep similar style
        self.layout.addWidget(self.active_runs_list_widget)
        
        self.refresh_button = QPushButton("🔄 Refresh Lists")
        self.refresh_button.clicked.connect(self.refresh_display)
        self.layout.addWidget(self.refresh_button)
        
        self.load_runs_from_db() # Initial load of completed runs
        # Active runs will be populated by update_active_benchmarks_display

    def refresh_display(self):
        self.load_runs_from_db() # Reload completed runs
        # Re-apply current active data to refresh their state (e.g. if UI was out of sync)
        self.update_active_benchmarks_display(self._active_benchmarks_data) 

    def load_runs_from_db(self):
        self.previous_runs_list_widget.clear()
        runs = load_all_benchmark_runs()
        
        if not runs:
            no_runs_item = QListWidgetItem("🧪 No completed experiments yet.")
            no_runs_item.setFlags(no_runs_item.flags() & ~Qt.ItemIsSelectable)
            self.previous_runs_list_widget.addItem(no_runs_item)
            # Do not return here, active runs might still need to be displayed or cleared
        else:
            for run in runs:
                try:
                    dt_obj = datetime.fromisoformat(run['timestamp'])
                    formatted_time = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                    pdf_name = Path(run['pdf_path']).name
                    score_info = f"Score: {run['mean_score']:.2f}" if run['mean_score'] is not None else "N/A"
                    status = f"{formatted_time}  |  PDF: {pdf_name}  |  Items: {run['total_items']}  |  {score_info}  |  Model: {run['model_name']}"
                    
                    item = QListWidgetItem(status)
                    item.setData(Qt.UserRole, run['id']) # Store benchmark ID for selection
                    self.previous_runs_list_widget.addItem(item)
                except Exception as e:
                    print(f"Error formatting run data for display: {e} - Run data: {run}")
                    error_item = QListWidgetItem(f"Error displaying run: {run.get('id', 'Unknown ID')}")
                    error_item.setData(Qt.UserRole, run.get('id'))
                    self.previous_runs_list_widget.addItem(error_item)
        
        # Ensure active list is also cleared if no active data (will be repopulated by update_active_benchmarks_display)
        if not self._active_benchmarks_data:
            self.active_runs_list_widget.clear()
            no_active_item = QListWidgetItem("No benchmarks currently running.")
            no_active_item.setFlags(no_active_item.flags() & ~Qt.ItemIsSelectable)
            self.active_runs_list_widget.addItem(no_active_item)

    def update_active_benchmarks_display(self, active_data: dict):
        print(f"DEBUG: HomePage.update_active_benchmarks_display called with data: {active_data}") # DEBUG
        self._active_benchmarks_data = active_data # Store the latest data
        self.active_runs_list_widget.clear() 
        self._progress_bars.clear() # Clear old progress bar references

        if not active_data:
            no_active_item = QListWidgetItem("No benchmarks currently running.")
            no_active_item.setFlags(no_active_item.flags() & ~Qt.ItemIsSelectable)
            self.active_runs_list_widget.addItem(no_active_item)
            return

        for run_id, data in active_data.items():
            pdf_name = data.get('pdf_name', 'N/A')
            current_prompt = data.get('current_prompt', 0)
            total_prompts = data.get('total_prompts', 0)
            status_msg = data.get('status_message', 'Running...')
            start_time_dt = data.get('start_time')
            start_time_str = start_time_dt.strftime("%H:%M:%S") if start_time_dt else "N/A"

            item_widget = QWidget() # Custom widget for each item
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5) # Reduce margins

            # Info line
            info_text = f"Run ID: {run_id} | PDF: {pdf_name} | Started: {start_time_str}"
            info_label = QLabel(info_text)
            item_layout.addWidget(info_label)

            # Progress bar
            progress_bar = QProgressBar()
            progress_bar.setRange(0, total_prompts)
            progress_bar.setValue(current_prompt)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"%v/%m ({status_msg[:30]}...)")
            item_layout.addWidget(progress_bar)
            self._progress_bars[run_id] = progress_bar # Store for potential direct updates

            list_item = QListWidgetItem(self.active_runs_list_widget)
            list_item.setSizeHint(item_widget.sizeHint())
            self.active_runs_list_widget.addItem(list_item)
            self.active_runs_list_widget.setItemWidget(list_item, item_widget)
            # Active items are not selectable to view details while running
            list_item.setFlags(list_item.flags() & ~Qt.ItemIsSelectable)


class ComposerPage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_pdf_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste or type your test prompts:"))
        
        self.table = QTableWidget(5, 2)
        default_rows = [
            ("what year did this piece get written", "2025"),
            ("what is happening faster, decarbonization or electrification", "decarbonization"),
            ("whats the meaning of the title of this piece", "heliocentrism means the solar and green transition is further away than it appears to optimists, they imagine exponential growth of solar despite the necessity of other energies like natural gas and the fact that energy transitions are linear not exponential"),
        ]
        for r, (p, e) in enumerate(default_rows):
            self.table.setItem(r, 0, QTableWidgetItem(p))
            self.table.setItem(r, 1, QTableWidgetItem(e))
        self.table.setHorizontalHeaderLabels(["Prompt", "Expected" ])
        layout.addWidget(self.table)

        # Model Selection ListWidget
        model_selection_layout = QVBoxLayout() # Changed to QVBoxLayout for label and list
        model_selection_layout.addWidget(QLabel("Select Model(s) for Benchmark:"))
        self.model_list_widget = QListWidget()
        self.model_list_widget.setMinimumHeight(100) # Give it some initial height
        self.model_list_widget.setStyleSheet("font-size: 14pt;") # Consistent font size
        for model_name in AVAILABLE_MODELS:
            item = QListWidgetItem(model_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.model_list_widget.addItem(item)
        # Default check gpt-4o-mini if available
        if "gpt-4o-mini" in AVAILABLE_MODELS:
            for i in range(self.model_list_widget.count()):
                item = self.model_list_widget.item(i)
                if item.text() == "gpt-4o-mini":
                    item.setCheckState(Qt.Checked)
                    break
        model_selection_layout.addWidget(self.model_list_widget)
        layout.addLayout(model_selection_layout)

        pdf_selection_layout = QHBoxLayout()
        self.select_pdf_button = QPushButton("Select PDF for Benchmark")
        self.select_pdf_button.clicked.connect(self.select_pdf_file)
        pdf_selection_layout.addWidget(self.select_pdf_button)
        self.selected_pdf_label = QLabel("No PDF selected")
        self.selected_pdf_label.setStyleSheet("padding-left: 10px; font-style: italic; color: #6c757d;")
        pdf_selection_layout.addWidget(self.selected_pdf_label)
        layout.addLayout(pdf_selection_layout)
        
        self.run_btn = QPushButton("Run Benchmark ▸")
        self.run_btn.setStyleSheet("font-size: 15pt; padding: 12px 20px;")
        layout.addWidget(self.run_btn)

        self.return_home_btn = QPushButton("Return to Home")
        self.return_home_btn.setObjectName("returnButton")
        layout.addWidget(self.return_home_btn)

    def select_pdf_file(self):
        start_dir = str(Path.cwd() / "files")
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select PDF File", 
            start_dir, 
            "PDF Files (*.pdf)"
        )
        if file_path:
            self.selected_pdf_path = Path(file_path)
            self.selected_pdf_label.setText(self.selected_pdf_path.name)
        else:
            self.selected_pdf_path = None
            self.selected_pdf_label.setText("No PDF selected")

    def get_prompt_rows(self):
        prompts = []
        for row in range(self.table.rowCount()):
            prompt_item = self.table.item(row, 0)
            expect_item = self.table.item(row, 1)
            if prompt_item and prompt_item.text().strip():
                prompts.append({
                    "prompt": prompt_item.text(),
                    "expected": expect_item.text() if expect_item else ""
                })
        return prompts

    def get_selected_models(self) -> list[str]:
        selected_models = []
        for i in range(self.model_list_widget.count()):
            item = self.model_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_models.append(item.text())
        return selected_models

# --- Main window ----------------------------------------------------------
class MainWindow(QMainWindow):
    # Define signals that the app logic can connect to
    new_benchmark_requested = Signal()
    open_csv_requested = Signal()
    run_benchmark_requested = Signal(list, Path, list) # prompts, pdf_path, model_names_list
    show_home_requested = Signal()
    benchmark_selected = Signal(object) # benchmark_id (item.data)
    active_benchmarks_changed = Signal(dict) # New signal for active benchmark updates

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EOTMBench")
        self.resize(900, 600)

        self.stack = QStackedWidget()
        self.home = HomePage()
        self.composer = ComposerPage()
        self.console = RunConsoleWidget()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.composer)
        self.stack.addWidget(self.console)
        self.setCentralWidget(self.stack)

        tb = QToolBar()
        self.addToolBar(tb)
        new_action = QAction("New Benchmark", self)
        new_action.triggered.connect(self.new_benchmark_requested.emit)
        tb.addAction(new_action)
        tb.addSeparator()
        open_action = QAction("Open prompts CSV", self)
        open_action.triggered.connect(self.open_csv_requested.emit)
        tb.addAction(open_action)

        # Connect signals from composer and home page
        self.composer.run_btn.clicked.connect(self._emit_run_benchmark_request)
        self.composer.return_home_btn.clicked.connect(self.show_home_requested.emit)
        
        # Connect itemClicked for the list of previous (completed) runs
        self.home.previous_runs_list_widget.itemClicked.connect(self._emit_benchmark_selected)
        
        # Connect the new signal for active benchmark updates to HomePage's slot
        self.active_benchmarks_changed.connect(self.home.update_active_benchmarks_display)
        
        if self.console.return_btn:
            self.console.return_btn.setObjectName("returnButton")
            self.console.return_btn.clicked.connect(self.show_home_requested.emit)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _emit_run_benchmark_request(self):
        prompts = self.composer.get_prompt_rows()
        pdf_path = self.composer.selected_pdf_path
        selected_models = self.composer.get_selected_models() # Get list of selected models

        if not prompts:
            QMessageBox.warning(self, "No prompts", "Please enter at least one prompt.")
            return
        if not pdf_path:
            QMessageBox.warning(self, "No PDF", "Please select a PDF file for the benchmark.")
            return
        if not pdf_path.exists(): # Check existence here as it's UI related
            QMessageBox.critical(self, "File Error", f"Selected PDF not found: {pdf_path}")
            return
        if not selected_models: # Check if at least one model is selected
            QMessageBox.warning(self, "No Model(s)", "Please select at least one model for the benchmark.")
            return
        self.run_benchmark_requested.emit(prompts, pdf_path, selected_models) # Emit with list of models

    def _emit_benchmark_selected(self, item: QListWidgetItem):
        benchmark_id = item.data(Qt.UserRole)
        if benchmark_id is not None:
            self.benchmark_selected.emit(benchmark_id)
        else:
            QMessageBox.warning(self, "Error", "Could not retrieve benchmark ID.")


    def show_composer_page(self):
        self.stack.setCurrentWidget(self.composer)
        
    def show_console_page(self):
        self.stack.setCurrentWidget(self.console)
        
    def show_home_page(self):
        self.stack.setCurrentWidget(self.home)
        self.home.load_runs_from_db() # Refresh home page when shown

    def update_status_bar(self, message: str, timeout: int = 0):
        self.statusBar().showMessage(message, timeout)

    def update_console_log(self, text: str):
        self.console.update_log(text)

    def clear_console_log(self):
        self.console.log_text.clear()

    def display_benchmark_summary_in_console(self, result: dict, run_id):
        self.console.log_text.clear() # Clear previous run's live log
        self.console.update_log(f"----- BENCHMARK COMPLETE (ID: {run_id if run_id else 'N/A'}) -----")
        self.console.update_log(f"Mean Score: {result.get('mean_score', 'N/A')}")
        self.console.update_log(f"Items: {result.get('items', 'N/A')}") # Note: result from run_benchmark has 'items'
        self.console.update_log(f"Time: {result.get('elapsed_s', 'N/A')}s") # Note: result from run_benchmark has 'elapsed_s'
        self.console.update_log(f"Model: {result.get('model', 'unknown')}")
        
        if 'scores' in result and 'prompts' in result and 'answers' in result:
            # Assuming 'prompts' in result is a list of dicts [{'prompt': ..., 'expected': ...}]
            # And 'answers' is a list of actual answers
            # And 'scores' is a list of scores
            
            # We need 'expected' answers. The 'prompts' list in the result from run_benchmark
            # (which is `engine.runner.run_benchmark`) contains dicts like `{'prompt': str, 'expected': str}`.
            # Let's iterate assuming this structure for `result['prompts']`

            self.console.update_log("\n----- DETAILED RESULTS -----")
            for i, prompt_data in enumerate(result.get('prompts', [])):
                actual_answer = result.get('answers', [])[i] if i < len(result.get('answers', [])) else "N/A"
                score = result.get('scores', [])[i] if i < len(result.get('scores', [])) else "N/A"
                expected_answer = prompt_data.get('expected', "N/A") # Get expected from prompt_data

                self.console.update_log(f"\nPrompt {i+1}: {prompt_data.get('prompt', 'N/A')}")
                self.console.update_log(f"Expected: {expected_answer}")
                self.console.update_log(f"Answer: {actual_answer}")
                self.console.update_log(f"Score: {score}")
    
    def display_full_benchmark_details_in_console(self, details: dict):
        self.console.display_benchmark_details(details)

    def populate_composer_table(self, rows: list):
        self.composer.table.setRowCount(max(5, len(rows)))
        for r, (prompt, expected) in enumerate(rows):
            self.composer.table.setItem(r, 0, QTableWidgetItem(prompt))
            self.composer.table.setItem(r, 1, QTableWidgetItem(expected))

    def show_message_box(self, level: str, title: str, message: str):
        if level == "warning":
            QMessageBox.warning(self, title, message)
        elif level == "critical":
            QMessageBox.critical(self, title, message)
        elif level == "information":
            QMessageBox.information(self, title, message)
        else: # default to information
            QMessageBox.information(self, title, message) 