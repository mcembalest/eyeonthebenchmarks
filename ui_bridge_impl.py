"""
ScriptUiBridge implementation for command-line execution.

This module provides a UI bridge that prints UI events as JSON to stdout 
for script-based execution, enabling command-line tools to receive UI updates.
"""

import json
import sys
import logging
from typing import Optional, Dict, List, Any

from ui_bridge import AppUIBridge, DataChangeType


class ScriptUiBridge(AppUIBridge):
    """A UI bridge that prints UI events as JSON to stdout for script-based execution."""
    
    def _send_event(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        """Send a UI event as JSON to stdout."""
        # Print a blank line before JSON to ensure clean separation
        print("")
        # Format the JSON event and ensure it's on its own line
        print(json.dumps({"ui_bridge_event": event_name, "data": data or {}}))
        # Print another blank line after to further separate output
        print("")
        # Force immediate flush to prevent buffering issues
        sys.stdout.flush()

    def show_message(self, level: str, title: str, message: str):
        """Show a message to the user."""
        self._send_event('show_message', {"level": level, "title": title, "message": message})

    def populate_composer_table(self, rows: list):
        """Populate the composer table with rows."""
        # For script execution, this might not be directly useful unless the calling script handles it.
        # self._send_event('populate_composer_table', {"rows": rows})
        pass  # Or log that it was called

    def show_composer_page(self):
        """Show the composer page."""
        # self._send_event('show_composer_page', {})
        pass

    def get_csv_file_path_via_dialog(self) -> Optional[str]:
        """Get CSV file path via dialog - not supported in script mode."""
        # Cannot open dialogs in script mode. This should not be called by methods invoked via script.
        # If it is, it indicates a logic error or a method not suitable for script invocation.
        logging.warning("ScriptUiBridge: get_csv_file_path_via_dialog called, returning None.")
        return None

    def notify_benchmark_progress(self, job_id: int, progress_data: Dict[str, Any]):
        """Notify about benchmark progress."""
        self._send_event('benchmark-progress', {"job_id": job_id, **progress_data})

    def notify_benchmark_complete(self, job_id: int, result_summary: Dict[str, Any]):
        """Notify about benchmark completion."""
        self._send_event('benchmark-complete', {"job_id": job_id, **result_summary})

    def notify_active_benchmarks_updated(self, active_benchmarks: List[Dict[str, Any]]):
        """Notify about active benchmarks updates."""
        self._send_event('active_benchmarks_updated', {"active_benchmarks": active_benchmarks})

    def populate_home_benchmarks_table(self, benchmarks_data: Optional[List[Dict[str, Any]]]):
        """Populate the home benchmarks table."""
        # This typically triggers a full refresh in the UI, which might be signaled differently.
        # For now, signal that a refresh is needed.
        self._send_event('refresh_benchmark_list_needed', {})

    def register_data_callback(self, data_type: DataChangeType, callback: callable):
        """Register a data callback - not applicable in script mode."""
        # Callbacks are typically for direct UI interaction, less relevant for script mode.
        pass

    def start_auto_refresh(self):
        """Start auto-refresh - not applicable in script mode."""
        # Auto-refresh is a UI concern, not applicable to script mode.
        pass

    def stop_auto_refresh(self):
        """Stop auto-refresh - not applicable in script mode."""
        pass