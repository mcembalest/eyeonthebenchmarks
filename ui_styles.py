APP_STYLESHEET = '''
QWidget {
    /* Default font for all widgets, can be overridden */
    font-family: "Segoe UI", Frutiger, "Frutiger Linotype", "Dejavu Sans", "Helvetica Neue", Arial, sans-serif;
    color: #333; /* Dark gray for text for better readability */
}

QMainWindow {
    background-color: #f8f9fa; /* Light, neutral background */
}

QLabel {
    font-size: 17pt; /* Slightly smaller default, can be overridden */
    color: #454545; /* Slightly softer than pure black */
}

QPushButton {
    font-size: 17pt;
    padding: 10px 18px;
    background-color: #007bff; /* A modern blue */
    color: white;
    border: none; /* Remove default border */
    border-radius: 5px; /* Rounded corners */
    font-weight: bold;
}

QPushButton:hover {
    background-color: #0056b3; /* Darker blue on hover */
}

QPushButton:pressed {
    background-color: #004085; /* Even darker blue when pressed */
}

QTextEdit, QTableWidget {
    font-size: 17pt;
    border: 1px solid #dee2e6; /* Light gray border */
    border-radius: 4px;
    background-color: #ffffff; /* White background for text areas */
}

QTableWidget::item {
    padding: 8px; /* More padding for table cells */
    border-bottom: 1px solid #f1f1f1; /* Separator lines for rows */
}

QTableWidget::item:selected {
    background-color: #e9ecef; /* Subtle selection color */
    color: #000;
}

QHeaderView::section {
    background-color: #e9ecef; /* Light gray for headers */
    padding: 8px;
    border: none; /* Remove default border */
    border-bottom: 1px solid #ced4da; /* Bottom border for header */
    font-size: 17pt;
    font-weight: bold;
}

QToolBar {
    background-color: #e9ecef; /* Consistent with header */
    border: none;
    padding: 5px;
}

QStatusBar {
    background-color: #e9ecef;
    color: #555;
    font-size: 12pt;
}

QScrollArea {
    border: none;
}

/* Style for the 'Return to Home' button if it's specifically named */
#returnButton {
    background-color: #6c757d; /* A secondary, muted color */
    font-weight: normal;
}
#returnButton:hover {
    background-color: #5a6268;
}
#returnButton:pressed {
    background-color: #545b62;
}

/* Styling for QListWidget */
QListWidget {
    font-size: 14pt; /* Slightly smaller for list items */
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background-color: #ffffff;
}

QListWidget::item {
    padding: 10px; /* More padding for list items */
    border-bottom: 1px solid #f1f1f1; /* Separator lines for items */
}

QListWidget::item:selected {
    background-color: #e9ecef; /* Subtle selection color */
    color: #000;
}

QListWidget::item:hover {
    background-color: #f8f9fa; /* Lighter hover for discoverability */
}

/* Styles for QComboBox */
QComboBox {
    font-size: 17pt;
    padding: 8px;
    border: 1px solid #ced4da;
    border-radius: 4px;
    background-color: #ffffff;
    min-height: 30px; /* Adjust as needed based on font & padding */
}

QComboBox:hover {
    border-color: #007bff; /* Highlight on hover */
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left-width: 1px;
    border-left-color: #ced4da;
    border-left-style: solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

/* QComboBox::down-arrow: { image: url(path/to/your/arrow.png); } */
/* Qt usually provides a default arrow, so explicit styling might not be needed */

/* Style for the popup list of items */
QComboBox QAbstractItemView {
    font-size: 14pt;
    background-color: #ffffff; /* Light background for dropdown list */
    color: #333333;           /* Dark text for readability */
    border: 1px solid #ced4da; /* Border for the dropdown list */
    selection-background-color: #007bff; /* Selection background */
    selection-color: #ffffff;           /* Text color for selected item */
    padding: 4px; /* Padding around the list itself */
}

QComboBox QAbstractItemView::item {
    padding: 8px; /* Padding for individual items in the list */
    min-height: 25px; /* Ensure items are not too cramped */
}

/* Example of styling a specific named widget if you set its objectName */
/*
#mySpecialButton {
    background-color: #ff0000;
    color: white;
}
*/
''' 