#!/usr/bin/env python3
"""
Simple test script to verify Electron-Python communication.
"""
import json
import os
import sys
from datetime import datetime

# Write some debug info to a file
with open('test_output.log', 'w') as f:
    f.write(f"Test script executed at {datetime.now()}\n")
    f.write(f"Current working directory: {os.getcwd()}\n")
    f.write(f"Python version: {sys.version}\n")
    f.write(f"Command line args: {sys.argv}\n")

# Return a simple fixed result that mimics your benchmark structure
test_data = [
    {
        "id": 1,
        "timestamp": "2025-05-15 10:11",
        "status": "completed",
        "label": "Test Benchmark 1",
        "description": "Test benchmark for debugging",
        "models": ["test-model"],
        "files": ["test-file.pdf"],
        "mean_score": None,
        "total_items": 1,
        "elapsed_seconds": None,
        "total_tokens": 0
    },
    {
        "id": 2,
        "timestamp": "2025-05-15 10:05",
        "status": "completed",
        "label": "Test Benchmark 2",
        "description": "Another test benchmark for debugging",
        "models": ["test-model"],
        "files": ["test-file.pdf"],
        "mean_score": None,
        "total_items": 1,
        "elapsed_seconds": None,
        "total_tokens": 0
    }
]

# Output the result as JSON
print(json.dumps(test_data))
