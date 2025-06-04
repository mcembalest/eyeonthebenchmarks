"""
File Management Module

This module handles file upload, registration, retrieval, and deletion operations.
It manages file metadata and validates file types for the application.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any


class FileManager:
    """Manages file operations including upload, retrieval, and deletion."""
    
    def __init__(self, db_path: Path):
        """
        Initialize the FileManager.
        
        Args:
            db_path: Path to the database directory
        """
        self.db_path = db_path
    
    def handle_upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload and register a file in the system."""
        try:
            from file_store import register_file
            
            file_path_obj = Path(file_path)
            
            # Validate file exists
            if not file_path_obj.exists():
                return {"success": False, "error": "File does not exist"}
            
            # Validate file type (PDF, CSV, XLSX)
            allowed_extensions = {'.pdf', '.csv', '.xlsx'}
            if file_path_obj.suffix.lower() not in allowed_extensions:
                return {"success": False, "error": f"File type not supported. Allowed: {', '.join(allowed_extensions)}"}
            
            # Register file
            file_id = register_file(file_path_obj, self.db_path)
            
            if file_id:
                return {
                    "success": True,
                    "file_id": file_id,
                    "message": f"File '{file_path_obj.name}' uploaded successfully"
                }
            else:
                return {"success": False, "error": "Failed to register file"}
                
        except Exception as e:
            logging.error(f"Error uploading file {file_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_get_files(self) -> List[Dict[str, Any]]:
        """Get all registered files."""
        try:
            from file_store import get_all_files
            
            return get_all_files(self.db_path)
            
        except Exception as e:
            logging.error(f"Error getting files: {e}")
            return []
    
    def handle_get_file_details(self, file_id: int) -> Dict[str, Any]:
        """Get details of a specific file."""
        try:
            from file_store import get_file_details
            
            file_details = get_file_details(file_id, self.db_path)
            
            if file_details:
                return {"success": True, "file": file_details}
            else:
                return {"success": False, "error": "File not found"}
                
        except Exception as e:
            logging.error(f"Error getting file details {file_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_delete_file(self, file_id: int) -> Dict[str, Any]:
        """Delete a file from the system."""
        try:
            from file_store import delete_file
            
            success = delete_file(file_id, self.db_path)
            
            if success:
                return {"success": True, "message": f"File {file_id} deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete file (may be in use by benchmarks)"}
                
        except Exception as e:
            logging.error(f"Error deleting file {file_id}: {e}")
            return {"success": False, "error": str(e)}