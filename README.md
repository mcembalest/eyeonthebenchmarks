# EOTM Benchmark

A desktop application for benchmarking language models against PDF documents.

## Installation (macOS)

1. Ensure you have Python 3.8+ installed:
```bash
python3 --version
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your OpenAI API key:
```bash
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

1. Activate the virtual environment (if not already activated):
```bash
source venv/bin/activate
```

2. Run the application:
```bash
python main_qt.py
```

## Features

- Create new benchmarks with PDF documents
- Define custom test prompts and expected answers
- Run multiple models on the same benchmark
- View and compare results across different models
- Support for multiple benchmarks with the same PDF
- Grid and table view for benchmark management

## Development

The application uses:
- PySide6 for the native UI
- SQLite for data storage
- PyPDF2 for PDF processing
- OpenAI API for model interactions
