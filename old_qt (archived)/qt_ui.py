import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QListWidget,
    QListWidgetItem, QStackedWidget, QToolBar, QStatusBar, QMessageBox,
    QFileDialog, QTextEdit, QScrollArea, QProgressBar, QGridLayout, QFrame,
    QAbstractItemView
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QBrush, QAction
from PySide6.QtCore import Qt, QSize, QThread, QEvent, QObject, Signal, QTimer
# Import styles
from ui_styles import APP_STYLESHEET

# Import database functions - these will be called by the app logic,
# but UI elements might need to trigger them or display their results.
# Actual database interaction logic should ideally be in app.py.
from engine.file_store import load_all_benchmark_runs, load_benchmark_details, load_all_benchmarks_with_models, delete_benchmark
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
        
        # Button container for actions
        button_layout = QHBoxLayout()
        
        # Add an "Export to CSV" button
        self.export_csv_btn = QPushButton("Export to CSV")
        self.export_csv_btn.setIcon(QIcon.fromTheme("document-save"))
        self.export_csv_btn.setToolTip("Export benchmark results to CSV file")
        button_layout.addWidget(self.export_csv_btn)
        
        # Add spacer to separate buttons
        button_layout.addStretch(1)
        
        # Add a "Return to Home" button
        self.return_btn = QPushButton("Return to Home") # Made it an instance variable
        button_layout.addWidget(self.return_btn)
        
        # Add button container to main layout
        layout.addLayout(button_layout)

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
    benchmark_selected = Signal(object)
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self._active_benchmarks_data: dict = {}
        self._benchmarks_data: list = []
        self._view_mode = 'grid'  # or 'table'
        self._card_refs = []  # To keep references for click events

        # Header section with title and toggle button
        header_layout = QHBoxLayout()
        title_label = QLabel("Benchmarks")
        title_label.setStyleSheet("font-size: 24pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Toggle button with icon
        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(QIcon.fromTheme("view-list-details"))
        self.toggle_btn.setText("Switch to Table View")
        self.toggle_btn.setStyleSheet("font-size: 12pt; padding: 8px 16px;")
        self.toggle_btn.clicked.connect(self.toggle_view)
        header_layout.addWidget(self.toggle_btn)
        
        self.layout.addLayout(header_layout)
        
        # Grid view widget with scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(16)  # Add spacing between cards
        self.grid_layout.setRowMinimumHeight(0, 20)  # Reduced height since delete icon is now smaller
        scroll_area.setWidget(self.grid_widget)
        self.layout.addWidget(scroll_area)

        # Table view widget
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(5)  # Status, Label, Date, Models, Files
        self.table_widget.setHorizontalHeaderLabels(["Status", "Label", "Date", "Models", "Files"])
        self.table_widget.setSortingEnabled(True)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # Set column widths
        self.table_widget.setColumnWidth(0, 80)  # Status column
        self.table_widget.setColumnWidth(2, 180)  # Date column
        self.table_widget.setColumnWidth(3, 120)  # Models column
        self.table_widget.setColumnWidth(4, 200)  # Files column
        
        # Configure headers
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Status column fixed width
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Label column stretches
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Date column fixed width
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Models column fixed width
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Files column fixed width
        
        # Other table settings
        self.table_widget.verticalHeader().setVisible(True)  # Show row numbers
        self.table_widget.setAlternatingRowColors(True)  # Alternate row colors
        self.table_widget.setShowGrid(True)  # Show grid lines
        self.table_widget.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 4px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
            }
        """)
        self.table_widget.cellClicked.connect(self.handle_table_row_clicked)
        
        # Create a separate layout for the table view
        self.table_view_widget = QWidget()
        table_layout = QVBoxLayout(self.table_view_widget)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.addWidget(self.table_widget)
        
        # Add the table view widget to the main layout
        self.layout.addWidget(self.table_view_widget)
        self.table_view_widget.hide()
        
        # Refresh button at the bottom
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setStyleSheet("font-size: 12pt; padding: 8px 16px;")
        self.refresh_button.clicked.connect(self.refresh_display)
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        refresh_layout.addWidget(self.refresh_button)
        refresh_layout.addStretch()
        self.layout.addLayout(refresh_layout)

    def toggle_view(self):
        if self._view_mode == 'grid':
            self._view_mode = 'table'
            self.grid_widget.parentWidget().hide()  # Hide the grid scroll area
            self.table_view_widget.show()  # Show the table view widget
            self.toggle_btn.setIcon(QIcon.fromTheme("view-grid"))
            self.toggle_btn.setText("Switch to Grid View")
        else:
            self._view_mode = 'grid'
            self.table_view_widget.hide()  # Hide the table view widget
            self.grid_widget.parentWidget().show()  # Show the grid scroll area
            self.toggle_btn.setIcon(QIcon.fromTheme("view-list-details"))
            self.toggle_btn.setText("Switch to Table View")

    def refresh_display(self):
        self.load_runs_from_db()
        self.update_active_benchmarks_display(self._active_benchmarks_data)

    def load_runs_from_db(self):
        try:
            self._benchmarks_data = load_all_benchmarks_with_models()
        except Exception as e:
            print(f"Error loading benchmarks: {e}")
            self._benchmarks_data = []
        self.populate_grid_view()
        self.populate_table_view()

    def populate_grid_view(self):
        # Clear grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._card_refs = []
        
        # Add cards
        for idx, bench in enumerate(self._benchmarks_data):
            # Create card with border and styling
            card = QWidget()
            card.setObjectName("benchmark-card")
            card.setStyleSheet("""
                #benchmark-card {
                    background-color: white;
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                }
                .card-title { font-size: 16pt; font-weight: bold; }
                .card-date { font-size: 10pt; color: #666; }
                .model-score { font-size: 9pt; color: #333; }
                .model-metrics { font-size: 8pt; color: #666; }
            """)
            
            # Main layout for the card
            card_layout = QGridLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(8)
            card_layout.setRowMinimumHeight(0, 28)  # Reserve space in row 0 for delete icon without overlapping content
            
            # Content container for the card
            content_widget = QWidget()
            vbox = QVBoxLayout(content_widget)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(8)
            # Place main content below the delete button to avoid overlap
            card_layout.addWidget(content_widget, 1, 0, 1, 2)
            
            # Header with title and status icon
            header_layout = QHBoxLayout()
            
            # Title
            title = bench.get('label', bench.get('description', 'No Label'))
            label = QLabel(title)
            label.setProperty("class", "card-title")
            label.setWordWrap(True)
            header_layout.addWidget(label, 1)
            
            # Status icon (done or loading)
            is_active = bench.get('id') in self._active_benchmarks_data
            status_icon = QLabel()
            icon_path = "assets/loading.png" if is_active else "assets/done.png"
            status_pixmap = QPixmap(icon_path)
            if not status_pixmap.isNull():
                status_icon.setPixmap(status_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                status_icon.setToolTip("Running" if is_active else "Completed")
            header_layout.addWidget(status_icon)
            
            vbox.addLayout(header_layout)
            
            # Date
            date = QLabel(f"{bench.get('timestamp', '')[:19]}")
            date.setProperty("class", "card-date")
            vbox.addWidget(date)
            
            # Separator line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("background-color: #e0e0e0;")
            vbox.addWidget(line)
            
            # Model section
            model_section = QWidget()
            model_layout = QVBoxLayout(model_section)
            model_layout.setContentsMargins(0, 0, 0, 0)
            model_layout.setSpacing(4)
            
            # For each model, show icon, score, cost and latency
            for model in bench.get('model_names', []):
                model_item = QHBoxLayout()
                
                # Model icon
                icon_path = f"assets/{model}.png"
                pixmap = QPixmap(icon_path)
                if pixmap.isNull():
                    pixmap = QPixmap("assets/icon.png")  # fallback
                icon_label = QLabel()
                icon_label.setPixmap(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                model_item.addWidget(icon_label)
                
                # Model info
                model_info = QVBoxLayout()
                model_info.setSpacing(0)
                
                # Model name and score
                model_results = bench.get('model_results', {})
                model_data = model_results.get(model, {})
                score = model_data.get('score', 'N/A')
                cost = model_data.get('cost', 'N/A')
                latency = model_data.get('latency', 'N/A')
                
                if isinstance(score, (int, float)):
                    score_str = f"{score:.2f}%"
                else:
                    score_str = str(score)
                    
                score_label = QLabel(f"{model}: {score_str}")
                score_label.setProperty("class", "model-score")
                model_info.addWidget(score_label)
                
                # Cost and latency
                if isinstance(cost, (int, float)):
                    cost_str = f"${cost:.4f}"
                else:
                    cost_str = str(cost)
                    
                if isinstance(latency, (int, float)):
                    latency_str = f"{latency:.2f}s"
                else:
                    latency_str = str(latency)
                    
                metrics_label = QLabel(f"Cost: {cost_str} | Latency: {latency_str}")
                metrics_label.setProperty("class", "model-metrics")
                model_info.addWidget(metrics_label)
                
                model_item.addLayout(model_info)
                model_layout.addLayout(model_item)
            
            vbox.addWidget(model_section)
            vbox.addStretch(1)
            
            # Create a QLabel for the delete icon that appears on hover
            del_label = QLabel()
            del_label.setToolTip("Delete benchmark")
            del_label.setFixedSize(16, 16)  # Smaller size to be less disruptive
            del_label.setCursor(Qt.PointingHandCursor)
            # Keep a reference to prevent garbage collection
            card._del_label = del_label
            
            # Load the image directly as a pixmap
            del_pixmap = QPixmap("assets/delete.jpg")
            if not del_pixmap.isNull():
                del_label.setPixmap(del_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            # Create a mouse event handler for the label
            def label_click_handler(event):
                self.confirm_delete_benchmark(bench.get('id'))
            del_label.mousePressEvent = label_click_handler
            
            # Create a container widget for the delete button to maintain layout stability
            delete_container = QWidget()
            delete_container.setFixedSize(18, 18)  # Slightly larger than the button to provide padding
            delete_layout = QVBoxLayout(delete_container)
            delete_layout.setContentsMargins(0, 0, 0, 0)
            delete_layout.addWidget(del_label, alignment=Qt.AlignCenter)
            
            # Initially hide just the label, not the container
            del_label.hide()
            
            # Position delete container in top-right corner of the grid cell
            card_layout.addWidget(delete_container, 0, 1, 1, 1, Qt.AlignTop | Qt.AlignRight)
            
            # Create an event filter for the card to handle hover events
            class HoverFilter(QObject):
                def __init__(self, watched, label):
                    super().__init__()
                    self.watched = watched
                    self.label = label
                    
                def eventFilter(self, obj, event):
                    if obj is self.watched:
                        if event.type() == QEvent.Enter:
                            self.label.show()
                        elif event.type() == QEvent.Leave:
                            self.label.hide()
                    return False
            
            # Install the event filter on the card
            hover_filter = HoverFilter(card, del_label)  # We still pass del_label as what gets shown/hidden
            card.installEventFilter(hover_filter)
            
            # Store reference to filter to prevent garbage collection
            card.hover_filter = hover_filter
            
            # Make the entire card clickable
            card.mousePressEvent = self._make_card_click_handler(bench.get('id'))
            self._card_refs.append(card)
            
            # Add to grid layout - 4 cards per row instead of 3
            self.grid_layout.addWidget(card, idx // 4, idx % 4)

    def _make_card_click_handler(self, bench_id):
        def handler(event):
            self.benchmark_selected.emit(bench_id)
        return handler

    def populate_table_view(self):
        self.table_widget.setRowCount(len(self._benchmarks_data))
        for row, bench in enumerate(self._benchmarks_data):
            # Status icon (done or loading)
            is_active = bench.get('id') in self._active_benchmarks_data
            status_widget = QWidget()
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(4, 4, 4, 4)
            status_layout.setAlignment(Qt.AlignCenter)
            
            status_icon = QLabel()
            icon_path = "assets/loading.png" if is_active else "assets/done.png"
            status_pixmap = QPixmap(icon_path)
            if not status_pixmap.isNull():
                status_icon.setPixmap(status_pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                status_icon.setToolTip("Running" if is_active else "Completed")
            status_layout.addWidget(status_icon)
            self.table_widget.setCellWidget(row, 0, status_widget)
            
            # Label/Title
            self.table_widget.setItem(row, 1, QTableWidgetItem(bench.get('label', bench.get('description', 'No Label'))))
            
            # Date
            self.table_widget.setItem(row, 2, QTableWidgetItem(bench.get('timestamp', '')[:19]))
            
            # Model icons in a widget
            model_widget = QWidget()
            hbox = QHBoxLayout(model_widget)
            hbox.setContentsMargins(4, 4, 4, 4)
            
            # For each model, show icon with tooltip containing score/cost/latency
            for model in bench.get('model_names', []):
                icon_path = f"assets/{model}.png"
                pixmap = QPixmap(icon_path)
                if pixmap.isNull():
                    pixmap = QPixmap("assets/icon.png")
                    
                icon_label = QLabel()
                icon_label.setPixmap(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                
                # Add tooltip with metrics
                model_results = bench.get('model_results', {})
                model_data = model_results.get(model, {})
                score = model_data.get('score', 'N/A')
                cost = model_data.get('cost', 'N/A')
                latency = model_data.get('latency', 'N/A')
                
                if isinstance(score, (int, float)):
                    score_str = f"{score:.2f}%"
                else:
                    score_str = str(score)
                    
                if isinstance(cost, (int, float)):
                    cost_str = f"${cost:.4f}"
                else:
                    cost_str = str(cost)
                    
                if isinstance(latency, (int, float)):
                    latency_str = f"{latency:.2f}s"
                else:
                    latency_str = str(latency)
                
                tooltip_text = f"{model}\nScore: {score_str}\nCost: {cost_str}\nLatency: {latency_str}"
                icon_label.setToolTip(tooltip_text)
                
                hbox.addWidget(icon_label)
                
            self.table_widget.setCellWidget(row, 3, model_widget)
            
            # Files
            files_str = ', '.join([Path(f).name for f in bench.get('file_paths', [])])
            self.table_widget.setItem(row, 4, QTableWidgetItem(files_str))
            
            # No delete button in table view
            
        self.table_widget.resizeColumnsToContents()

    def handle_table_row_clicked(self, row, col):
        if 0 <= row < len(self._benchmarks_data):
            bench_id = self._benchmarks_data[row].get('id')
            self.benchmark_selected.emit(bench_id)

    def update_active_benchmarks_display(self, active_data: dict):
        # Store active benchmarks data
        old_active_data = self._active_benchmarks_data.copy()
        self._active_benchmarks_data = active_data
        
        # Only update if there's a change in active benchmarks
        if old_active_data != active_data:
            # Update only the status icons without recreating the entire view
            if self._view_mode == 'grid':
                self._update_grid_status_icons()
            else:
                self._update_table_status_icons()

    def _update_grid_status_icons(self):
        # Update only the status icons in the grid view without recreating the entire grid
        for idx, bench in enumerate(self._benchmarks_data):
            # Find the card widget in the grid layout
            if idx < len(self._card_refs):
                card = self._card_refs[idx]
                # Find the status icon in the card's header layout
                header_layout = None
                for i in range(card.layout().count()):
                    item = card.layout().itemAt(i)
                    if isinstance(item, QHBoxLayout):
                        header_layout = item
                        break
                
                if header_layout:
                    # The status icon is the last widget in the header layout
                    status_icon = header_layout.itemAt(header_layout.count() - 1).widget()
                    if isinstance(status_icon, QLabel):
                        # Update the icon based on active status
                        is_active = bench.get('id') in self._active_benchmarks_data
                        icon_path = "assets/loading.png" if is_active else "assets/done.png"
                        status_pixmap = QPixmap(icon_path)
                        if not status_pixmap.isNull():
                            status_icon.setPixmap(status_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            status_icon.setToolTip("Running" if is_active else "Completed")

    def _update_table_status_icons(self):
        # Update only the status icons in the table view without recreating the entire table
        for row, bench in enumerate(self._benchmarks_data):
            # Get the status widget in the first column
            status_widget = self.table_widget.cellWidget(row, 0)
            if status_widget:
                # Find the status icon in the widget's layout
                status_layout = status_widget.layout()
                if status_layout and status_layout.count() > 0:
                    status_icon = status_layout.itemAt(0).widget()
                    if isinstance(status_icon, QLabel):
                        # Update the icon based on active status
                        is_active = bench.get('id') in self._active_benchmarks_data
                        icon_path = "assets/loading.png" if is_active else "assets/done.png"
                        status_pixmap = QPixmap(icon_path)
                        if not status_pixmap.isNull():
                            status_icon.setPixmap(status_pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            status_icon.setToolTip("Running" if is_active else "Completed")

    def confirm_delete_benchmark(self, benchmark_id):
        reply = QMessageBox.question(self, "Delete Benchmark", "Are you sure you want to delete this benchmark and all its data?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if delete_benchmark(benchmark_id):
                self.refresh_display()
            else:
                QMessageBox.critical(self, "Delete Failed", "Failed to delete benchmark from database.")


class ComposerPage(QWidget):
    
    def __init__(self):
        super().__init__()
        self.selected_pdf_path: Path | None = None

        # Central widget for centering and max width
        central = QWidget(self)
        central.setObjectName("ComposerCentralWidget")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(32)

        # --- Main horizontal layout (Prompts left, Model+PDF right) ---
        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(32)
        main_hbox.setContentsMargins(0, 0, 0, 0)

        # --- Prompts Table Card (Left, wide) ---
        prompts_card = QWidget()
        prompts_card.setProperty("class", "CardSection")
        prompts_layout = QVBoxLayout(prompts_card)
        prompts_layout.setContentsMargins(0, 0, 0, 0)
        prompts_layout.setSpacing(12)
        # Header row with label and import button
        prompts_header = QHBoxLayout()
        prompts_label = QLabel("Paste or type your test prompts:")
        prompts_header.addWidget(prompts_label)
        prompts_header.addStretch(1)
        self.csv_import_button = QPushButton("Import from CSV")
        self.csv_import_button.setToolTip("Import prompts from a CSV file")
        self.csv_import_button.clicked.connect(self.import_csv)
        prompts_header.addWidget(self.csv_import_button)
        prompts_layout.addLayout(prompts_header)
        self.table = QTableWidget(5, 2)
        self.table.setObjectName("PromptsTable")
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumWidth(500)
        self.table.setMaximumWidth(900)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 420)
        self.table.setColumnWidth(1, 220)
        default_rows = [
            ("what year did this piece get written", "2025"),
            ("what is happening faster, decarbonization or electrification", "decarbonization"),
            ("whats the meaning of the title of this piece", "heliocentrism means the solar and green transition is further away than it appears to optimists, they imagine exponential growth of solar despite the necessity of other energies like natural gas and the fact that energy transitions are linear not exponential"),
        ]
        for r, (p, e) in enumerate(default_rows):
            self.table.setItem(r, 0, QTableWidgetItem(p))
            self.table.setItem(r, 1, QTableWidgetItem(e))
        self.table.setHorizontalHeaderLabels(["Prompt", "Expected" ])
        prompts_layout.addWidget(self.table)
        main_hbox.addWidget(prompts_card, stretch=2)

        # --- Right column: Model Selection + PDF Selection stacked ---
        right_col = QWidget()
        right_col_layout = QVBoxLayout(right_col)
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(24)

        # Model Selection Card
        model_card = QWidget()
        model_card.setProperty("class", "CardSection")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(12)
        model_label = QLabel("Select Model(s) for Benchmark:")
        model_layout.addWidget(model_label)
        self.model_list_widget = QListWidget()
        self.model_list_widget.setObjectName("ModelListWidget")
        self.model_list_widget.setMinimumHeight(100)
        for model_name in AVAILABLE_MODELS:
            item = QListWidgetItem(model_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.model_list_widget.addItem(item)
        if "gpt-4o-mini" in AVAILABLE_MODELS:
            for i in range(self.model_list_widget.count()):
                item = self.model_list_widget.item(i)
                if item.text() == "gpt-4o-mini":
                    item.setCheckState(Qt.Checked)
                    break
        model_layout.addWidget(self.model_list_widget)
        right_col_layout.addWidget(model_card)

        # PDF Selection Card
        pdf_card = QWidget()
        pdf_card.setProperty("class", "CardSection")
        pdf_layout = QHBoxLayout(pdf_card)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.setSpacing(16)
        self.select_pdf_button = QPushButton("Select PDF for Benchmark")
        self.select_pdf_button.clicked.connect(self.select_pdf_file)
        pdf_layout.addWidget(self.select_pdf_button)
        self.selected_pdf_label = QLabel("No PDF selected")
        self.selected_pdf_label.setObjectName("SelectedPDFLabel")
        pdf_layout.addWidget(self.selected_pdf_label)
        pdf_layout.addStretch(1)
        right_col_layout.addWidget(pdf_card)
        right_col_layout.addStretch(1)
        main_hbox.addWidget(right_col, stretch=1)

        central_layout.addLayout(main_hbox)

        # --- Actions Card (centered below) ---
        actions_card = QWidget()
        actions_card.setProperty("class", "CardSection")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(16)
        self.run_btn = QPushButton("Run Benchmark ▸")
        self.run_btn.setStyleSheet("font-size: 15pt; padding: 12px 20px;")
        actions_layout.addWidget(self.run_btn, alignment=Qt.AlignHCenter)
        self.return_home_btn = QPushButton("Return to Home")
        self.return_home_btn.setObjectName("returnButton")
        actions_layout.addWidget(self.return_home_btn, alignment=Qt.AlignHCenter)
        central_layout.addWidget(actions_card, alignment=Qt.AlignHCenter)

        # Set the central layout
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(central, alignment=Qt.AlignHCenter | Qt.AlignTop)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

    def select_pdf_file(self):
        try:
            # Use native=False to avoid macOS-specific issues
            options = QFileDialog.Option.DontUseNativeDialog
            start_dir = str(Path.cwd() / "files")
            
            # Use a more robust file selection approach
            dialog = QFileDialog(self, "Select PDF File", start_dir, "PDF Files (*.pdf)")
            dialog.setOptions(options)
            
            if dialog.exec():
                file_path = dialog.selectedFiles()[0]
                self.selected_pdf_path = Path(file_path)
                self.selected_pdf_label.setText(self.selected_pdf_path.name)
            else:
                self.selected_pdf_path = None
                self.selected_pdf_label.setText("No PDF selected")
                
        except Exception as e:
            print(f"Error selecting file: {e}")
            QMessageBox.critical(self, "File Selection Error", f"Could not open file dialog: {e}")
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
        
    def import_csv(self):
        try:
            # Use native=False to avoid macOS-specific issues
            options = QFileDialog.Option.DontUseNativeDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select CSV File",
                str(Path.cwd()),
                "CSV Files (*.csv)",
                options=options
            )
            
            if not file_path:
                return  # User canceled the operation
                
            # Read CSV file
            import csv
            with open(file_path, 'r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                data = list(csv_reader)
                
            # Clear existing table
            self.table.clearContents()
            
            # Make sure we have enough rows
            required_rows = len(data)
            current_rows = self.table.rowCount()
            if required_rows > current_rows:
                self.table.setRowCount(required_rows)
            
            # Populate table with CSV data
            for row_idx, row_data in enumerate(data):
                if len(row_data) >= 2:  # We need at least 2 columns
                    # Set prompt (1st column)
                    prompt_item = QTableWidgetItem(row_data[0])
                    self.table.setItem(row_idx, 0, prompt_item)
                    
                    # Set expected (2nd column)
                    expected_item = QTableWidgetItem(row_data[1])
                    self.table.setItem(row_idx, 1, expected_item)
            
            QMessageBox.information(self, "CSV Import", f"Successfully imported {len(data)} rows from CSV.")
            
        except Exception as e:
            QMessageBox.critical(self, "CSV Import Error", f"Failed to import CSV: {str(e)}")
            print(f"CSV import error: {e}")

# --- Main window ----------------------------------------------------------
class MainWindow(QMainWindow):
    # Define signals that the app logic can connect to
    new_benchmark_requested = Signal()
    open_csv_requested = Signal()
    run_benchmark_requested = Signal(list, Path, list) # prompts, pdf_path, model_names_list
    show_home_requested = Signal()
    benchmark_selected = Signal(object) # benchmark_id (item.data)
    active_benchmarks_changed = Signal(dict) # New signal for active benchmark updates
    export_benchmark_csv_requested = Signal(int)  # Signal to export current benchmark to CSV

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('assets/icon.png'))
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

        # Connect signals from composer and home page
        self.composer.run_btn.clicked.connect(self._emit_run_benchmark_request)
        self.composer.return_home_btn.clicked.connect(self.show_home_requested.emit)
        self.home.benchmark_selected.connect(self._emit_benchmark_selected)
        self.active_benchmarks_changed.connect(self.home.update_active_benchmarks_display)
        if self.console.return_btn:
            self.console.return_btn.setObjectName("returnButton")
            self.console.return_btn.clicked.connect(self.show_home_requested.emit)
        if self.console.export_csv_btn:
            self.console.export_csv_btn.setObjectName("exportCsvButton")
            # We'll connect this in display_full_benchmark_details_in_console
            # to have access to the benchmark ID
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _emit_run_benchmark_request(self):
        try:
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
                
            # Use QTimer.singleShot to ensure we return to the event loop before emitting the signal
            QTimer.singleShot(0, lambda: self.run_benchmark_requested.emit(prompts, pdf_path, selected_models))
        except Exception as e:
            print(f"Error in run benchmark request: {e}")
            QMessageBox.critical(self, "Error", f"Failed to prepare benchmark: {e}")

    def _emit_benchmark_selected(self, benchmark_id: int):
        if benchmark_id is not None:
            # Use QTimer.singleShot to ensure we return to the event loop before emitting the signal
            QTimer.singleShot(0, lambda: self.benchmark_selected.emit(benchmark_id))
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
        self.show_console_page()
        
        # Store benchmark ID to use with export button
        benchmark_id = details.get('id')
        
        # Connect export button with the current benchmark ID
        # Disconnect previous connections first to avoid multiple signals
        try:
            self.console.export_csv_btn.clicked.disconnect()
        except TypeError:
            # No connections to disconnect
            pass
            
        if benchmark_id:
            # Enable export button and connect to signal with benchmark ID
            self.console.export_csv_btn.setEnabled(True)
            self.console.export_csv_btn.clicked.connect(
                lambda: self.export_benchmark_csv_requested.emit(benchmark_id))
        else:
            # Disable button if no valid benchmark ID
            self.console.export_csv_btn.setEnabled(False)
        
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