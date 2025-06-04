"""
Prompt Management Module

This module handles prompt set creation, retrieval, updating, and deletion operations.
It manages prompt set metadata and provides CRUD operations for prompt collections.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional


class PromptManager:
    """Manages prompt set operations including CRUD operations."""
    
    def __init__(self, db_path: Path):
        """
        Initialize the PromptManager.
        
        Args:
            db_path: Path to the database directory
        """
        self.db_path = db_path
    
    def create_prompt_set(self, name: str, description: str, prompts: List[str]) -> Dict[str, Any]:
        """Create a new prompt set."""
        try:
            from file_store import create_prompt_set
            
            prompt_set_id = create_prompt_set(name, description, prompts, self.db_path)
            
            if prompt_set_id:
                return {
                    "success": True, 
                    "prompt_set_id": prompt_set_id,
                    "message": f"Prompt set '{name}' created successfully"
                }
            else:
                return {"success": False, "error": "Failed to create prompt set"}
                
        except Exception as e:
            logging.error(f"Error creating prompt set: {e}")
            return {"success": False, "error": str(e)}
    
    def get_prompt_sets(self) -> List[Dict[str, Any]]:
        """Get all prompt sets."""
        try:
            from file_store import get_all_prompt_sets
            
            return get_all_prompt_sets(self.db_path)
            
        except Exception as e:
            logging.error(f"Error getting prompt sets: {e}")
            return []
    
    def get_prompt_set_details(self, prompt_set_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific prompt set."""
        try:
            from file_store import get_prompt_set
            
            return get_prompt_set(prompt_set_id, self.db_path)
            
        except Exception as e:
            logging.error(f"Error getting prompt set {prompt_set_id}: {e}")
            return None
    
    def update_prompt_set(self, prompt_set_id: int, name: str = None, 
                         description: str = None, prompts: List[str] = None) -> Dict[str, Any]:
        """Update a prompt set."""
        try:
            from file_store import update_prompt_set
            
            success = update_prompt_set(prompt_set_id, name, description, prompts, self.db_path)
            
            if success:
                return {"success": True, "message": f"Prompt set {prompt_set_id} updated successfully"}
            else:
                return {"success": False, "error": "Failed to update prompt set"}
                
        except Exception as e:
            logging.error(f"Error updating prompt set {prompt_set_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_prompt_set(self, prompt_set_id: int) -> Dict[str, Any]:
        """Delete a prompt set."""
        try:
            from file_store import delete_prompt_set
            
            success = delete_prompt_set(prompt_set_id, self.db_path)
            
            if success:
                return {"success": True, "message": f"Prompt set {prompt_set_id} deleted successfully"}
            else:
                return {"success": False, "error": "Failed to delete prompt set (may be in use by benchmarks)"}
                
        except Exception as e:
            logging.error(f"Error deleting prompt set {prompt_set_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_next_prompt_set_number(self) -> int:
        """Get the next available prompt set number for auto-naming."""
        try:
            from file_store import get_next_prompt_set_number
            
            return get_next_prompt_set_number(self.db_path)
            
        except Exception as e:
            logging.error(f"Error getting next prompt set number: {e}")
            return 1
    
    # Handler methods for API interface
    def handle_create_prompt_set(self, name: str, description: str, prompts: List[str]) -> Dict[str, Any]:
        """Handle prompt set creation request."""
        return self.create_prompt_set(name, description, prompts)
    
    def handle_get_prompt_sets(self) -> List[Dict[str, Any]]:
        """Handle request to get all prompt sets."""
        return self.get_prompt_sets()
    
    def handle_get_prompt_set_details(self, prompt_set_id: int) -> Dict[str, Any]:
        """Handle request to get detailed information about a specific prompt set."""
        result = self.get_prompt_set_details(prompt_set_id)
        if result:
            return {"success": True, "prompt_set": result}
        else:
            return {"success": False, "error": "Prompt set not found"}
    
    def handle_update_prompt_set(self, prompt_set_id: int, name: str = None, 
                                description: str = None, prompts: List[str] = None) -> Dict[str, Any]:
        """Handle prompt set update request."""
        return self.update_prompt_set(prompt_set_id, name, description, prompts)
    
    def handle_delete_prompt_set(self, prompt_set_id: int) -> Dict[str, Any]:
        """Handle prompt set deletion request."""
        return self.delete_prompt_set(prompt_set_id)
    
    def handle_get_next_prompt_set_number(self) -> Dict[str, Any]:
        """Handle request to get the next available prompt set number."""
        return {"next_number": self.get_next_prompt_set_number()}