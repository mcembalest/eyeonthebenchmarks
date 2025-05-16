APP_STYLESHEET = '''
QWidget {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #222; /* Nearly black for primary text */
    background-color: #f4f5f7;
}

QMainWindow {
    background-color: #f4f5f7;
}

QLabel {
    font-size: 15pt;
    color: #2d3a4a; /* Deep navy for headers */
}

QPushButton {
    font-size: 15pt;
    padding: 10px 22px;
    background-color: #3a4657; /* Slate blue/gray */
    color: #fff;
    border: 1px solid #2d3a4a;
    border-radius: 6px;
    font-weight: 500;
    margin: 6px 0;
}
QPushButton:hover {
    background-color: #232b36;
    border-color: #232b36;
}
QPushButton:pressed {
    background-color: #181d23;
    border-color: #181d23;
}

QTextEdit, QTableWidget {
    font-size: 15pt;
    border: 1px solid #c2c6cc;
    border-radius: 4px;
    background-color: #fcfcfd;
    color: #222;
}

QTableWidget::item {
    padding: 7px;
    border-bottom: 1px solid #e0e3e8;
}
QTableWidget::item:alternate {
    background: #f0f1f3;
}
QTableWidget::item:selected {
    background-color: #e0e3e8;
    color: #2d3a4a;
}

QHeaderView::section {
    background-color: #e0e3e8;
    color: #2d3a4a;
    font-size: 15pt;
    font-weight: bold;
    border: none;
    border-bottom: 1px solid #c2c6cc;
    padding: 8px 6px;
}

QToolBar {
    background-color: #e0e3e8;
    border: none;
    padding: 5px;
}

QStatusBar {
    background-color: #e0e3e8;
    color: #5a5a5a;
    font-size: 12pt;
}

QScrollArea {
    border: none;
}

#returnButton {
    background-color: #6c757d;
    color: #fff;
    font-weight: 400;
    border: 1px solid #5a6268;
}
#returnButton:hover {
    background-color: #5a6268;
}
#returnButton:pressed {
    background-color: #545b62;
}

QListWidget {
    font-size: 14pt;
    border: 1px solid #c2c6cc;
    border-radius: 4px;
    background-color: #fcfcfd;
    color: #222;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #e0e3e8;
}
QListWidget::item:selected {
    background-color: #e0e3e8;
    color: #2d3a4a;
}
QListWidget::item:hover {
    background-color: #f0f1f3;
}

QComboBox {
    font-size: 15pt;
    padding: 7px;
    border: 1px solid #c2c6cc;
    border-radius: 4px;
    background-color: #fcfcfd;
    min-height: 28px;
    color: #222;
}
QComboBox:hover {
    border-color: #3a4657;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left-width: 1px;
    border-left-color: #c2c6cc;
    border-left-style: solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}
QComboBox QAbstractItemView {
    font-size: 14pt;
    background-color: #fcfcfd;
    color: #222;
    border: 1px solid #c2c6cc;
    selection-background-color: #e0e3e8;
    selection-color: #2d3a4a;
    padding: 3px;
}
QComboBox QAbstractItemView::item {
    padding: 7px;
    min-height: 22px;
}

.CardSection {
    background: #f7f8fa;
    border: 1.5px solid #c2c6cc;
    border-radius: 14px;
    padding: 24px 24px 18px 24px;
    margin-bottom: 24px;
}

#ComposerCentralWidget {
    max-width: 720px;
    margin-left: auto;
    margin-right: auto;
    margin-top: 24px;
    margin-bottom: 24px;
}

QTableWidget#PromptsTable {
    background: #fcfcfd;
    border: 1.5px solid #c2c6cc;
    border-radius: 8px;
    gridline-color: #e0e3e8;
    font-size: 15pt;
}
QTableWidget#PromptsTable::item {
    border-bottom: 1px solid #e0e3e8;
    padding: 8px 6px;
}
QTableWidget#PromptsTable::item:alternate {
    background: #f0f1f3;
}
QTableWidget#PromptsTable::item:selected {
    background: #e0e3e8;
    color: #2d3a4a;
}
QHeaderView::section {
    background: #e0e3e8;
    color: #2d3a4a;
    font-size: 15pt;
    font-weight: bold;
    border-bottom: 1px solid #c2c6cc;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 6px;
}

#SelectedPDFLabel {
    font-style: italic;
    color: #5a5a5a;
    padding-left: 12px;
    font-size: 14pt;
}
QListWidget#ModelListWidget {
    font-size: 14pt;
    background: #fcfcfd;
    border: 1.5px solid #c2c6cc;
    border-radius: 8px;
    margin-top: 6px;
    margin-bottom: 6px;
}
QListWidget#ModelListWidget::item {
    padding: 10px 6px;
    border-bottom: 1px solid #e0e3e8;
}
QListWidget#ModelListWidget::item:selected {
    background: #e0e3e8;
    color: #2d3a4a;
}

.CardSection QLabel {
    font-size: 16pt;
    font-weight: 600;
    color: #2d3a4a;
    margin-bottom: 8px;
}
''' 