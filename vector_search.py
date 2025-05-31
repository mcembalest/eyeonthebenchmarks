"""
Vector Search implementation using OpenAI's file search with vector stores.
Provides semantic and keyword search capabilities over uploaded documents.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import time

import openai
from file_store import register_file, get_provider_file_id, register_provider_upload

# Get OpenAI client locally to avoid circular imports
def _get_openai_client():
    """Get OpenAI client, ensuring it's properly initialized"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure it in Settings.")
    return openai.OpenAI(api_key=api_key)


@dataclass
class VectorStoreInfo:
    """Information about a vector store"""
    id: str
    name: str
    created_at: int
    file_count: int
    usage_bytes: int
    status: str


@dataclass
class SearchResult:
    """Result from vector search"""
    file_id: str
    filename: str
    score: float
    content: str
    attributes: Dict[str, Any] = None


@dataclass
class FileSearchResponse:
    """Response from file search tool"""
    search_call_id: str
    query: str
    response_text: str
    citations: List[Dict[str, Any]]
    search_results: List[SearchResult] = None


class VectorSearchManager:
    """Manages vector stores and file search operations"""
    
    def __init__(self):
        self.client = None
        self._vector_stores_cache = {}
        
    def _get_client(self):
        """Get or initialize OpenAI client"""
        if not self.client:
            self.client = _get_openai_client()
        return self.client
    
    def create_vector_store(self, name: str, file_paths: List[Path] = None, 
                          expires_after_days: int = None) -> str:
        """
        Create a new vector store and optionally upload files to it.
        
        Args:
            name: Name for the vector store
            file_paths: Optional list of files to upload
            expires_after_days: Optional expiration in days
            
        Returns:
            Vector store ID
        """
        client = self._get_client()
        
        # Prepare creation parameters
        create_params = {"name": name}
        
        if expires_after_days:
            create_params["expires_after"] = {
                "anchor": "last_active_at",
                "days": expires_after_days
            }
        
        # If files provided, upload them first
        file_ids = []
        if file_paths:
            for file_path in file_paths:
                file_id = self._upload_file(file_path)
                if file_id:
                    file_ids.append(file_id)
        
        if file_ids:
            create_params["file_ids"] = file_ids
        
        # Create vector store
        vector_store = client.vector_stores.create(**create_params)
        
        logging.info(f"Created vector store '{name}' with ID: {vector_store.id}")
        if file_ids:
            logging.info(f"Uploaded {len(file_ids)} files to vector store")
        
        return vector_store.id
    
    def _upload_file(self, file_path: Path) -> Optional[str]:
        """
        Upload a file to OpenAI and register it in our file store.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            OpenAI file ID if successful, None otherwise
        """
        try:
            client = self._get_client()
            
            # Register file in our local database
            local_file_id = register_file(file_path)
            
            # Check if already uploaded to OpenAI
            existing_openai_id = get_provider_file_id(local_file_id, "openai")
            if existing_openai_id:
                logging.info(f"File {file_path.name} already uploaded to OpenAI: {existing_openai_id}")
                return existing_openai_id
            
            # Upload to OpenAI
            with open(file_path, 'rb') as f:
                uploaded_file = client.files.create(
                    file=f,
                    purpose='assistants'
                )
            
            # Register the upload in our database
            register_provider_upload(local_file_id, "openai", uploaded_file.id)
            
            logging.info(f"Uploaded {file_path.name} to OpenAI: {uploaded_file.id}")
            return uploaded_file.id
            
        except Exception as e:
            logging.error(f"Failed to upload file {file_path}: {e}")
            return None
    
    def add_files_to_vector_store(self, vector_store_id: str, file_paths: List[Path],
                                 attributes: Dict[str, Any] = None) -> List[str]:
        """
        Add files to an existing vector store.
        
        Args:
            vector_store_id: ID of the vector store
            file_paths: List of files to add
            attributes: Optional metadata for the files
            
        Returns:
            List of file IDs that were successfully added
        """
        client = self._get_client()
        added_files = []
        
        for file_path in file_paths:
            try:
                # Upload file to OpenAI first
                file_id = self._upload_file(file_path)
                if not file_id:
                    continue
                
                # Add to vector store
                create_params = {
                    "vector_store_id": vector_store_id,
                    "file_id": file_id
                }
                
                if attributes:
                    create_params["attributes"] = attributes
                
                vector_store_file = client.vector_stores.files.create(**create_params)
                added_files.append(file_id)
                
                logging.info(f"Added {file_path.name} to vector store {vector_store_id}")
                
            except Exception as e:
                logging.error(f"Failed to add {file_path.name} to vector store: {e}")
        
        return added_files
    
    def list_vector_stores(self) -> List[VectorStoreInfo]:
        """List all vector stores"""
        client = self._get_client()
        
        try:
            stores = client.vector_stores.list()
            return [
                VectorStoreInfo(
                    id=store.id,
                    name=store.name or "Unnamed",
                    created_at=store.created_at,
                    file_count=store.file_counts.total if hasattr(store, 'file_counts') else 0,
                    usage_bytes=store.usage_bytes if hasattr(store, 'usage_bytes') else 0,
                    status=store.status if hasattr(store, 'status') else "unknown"
                )
                for store in stores.data
            ]
        except Exception as e:
            logging.error(f"Failed to list vector stores: {e}")
            return []
    
    def get_vector_store_info(self, vector_store_id: str) -> Optional[VectorStoreInfo]:
        """Get information about a specific vector store"""
        client = self._get_client()
        
        try:
            store = client.vector_stores.retrieve(vector_store_id)
            return VectorStoreInfo(
                id=store.id,
                name=store.name or "Unnamed",
                created_at=store.created_at,
                file_count=store.file_counts.total if hasattr(store, 'file_counts') else 0,
                usage_bytes=store.usage_bytes if hasattr(store, 'usage_bytes') else 0,
                status=store.status if hasattr(store, 'status') else "unknown"
            )
        except Exception as e:
            logging.error(f"Failed to get vector store info: {e}")
            return None
    
    def search_vector_store(self, vector_store_id: str, query: str, 
                           max_results: int = 10, 
                           filters: Dict[str, Any] = None) -> List[SearchResult]:
        """
        Search a vector store directly (not through the Responses API).
        
        Args:
            vector_store_id: ID of the vector store to search
            query: Search query
            max_results: Maximum number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of search results
        """
        client = self._get_client()
        
        try:
            search_params = {
                "query": query,
                "max_num_results": max_results
            }
            
            if filters:
                search_params["filters"] = filters
            
            response = client.vector_stores.search(
                vector_store_id=vector_store_id,
                **search_params
            )
            
            results = []
            for item in response.data:
                content_text = ""
                if hasattr(item, 'content') and item.content:
                    for content_item in item.content:
                        if content_item.type == "text":
                            content_text += content_item.text
                
                results.append(SearchResult(
                    file_id=item.file_id,
                    filename=item.filename if hasattr(item, 'filename') else "Unknown",
                    score=item.score if hasattr(item, 'score') else 0.0,
                    content=content_text,
                    attributes=item.attributes if hasattr(item, 'attributes') else {}
                ))
            
            return results
            
        except Exception as e:
            logging.error(f"Failed to search vector store: {e}")
            return []
    
    def file_search_with_responses_api(self, vector_store_ids: List[str], query: str,
                                     model: str = "gpt-4o-mini",
                                     max_results: int = 20,
                                     include_search_results: bool = False,
                                     filters: Dict[str, Any] = None) -> FileSearchResponse:
        """
        Use the Responses API with file search tool to answer queries based on vector store content.
        
        Args:
            vector_store_ids: List of vector store IDs to search
            query: User's question/query
            model: Model to use for generating response
            max_results: Maximum number of search results to consider
            include_search_results: Whether to include raw search results in response
            filters: Optional metadata filters
            
        Returns:
            FileSearchResponse with answer and citations
        """
        client = self._get_client()
        
        try:
            # Prepare file search tool configuration
            file_search_tool = {
                "type": "file_search",
                "vector_store_ids": vector_store_ids,
                "max_num_results": max_results
            }
            
            if filters:
                file_search_tool["filters"] = filters
            
            # For o3/o4-mini models, enable strict mode when available
            if any(model_name in model.lower() for model_name in ["o3", "o4"]):
                # Note: file_search tool doesn't support strict mode yet
                # But we can optimize other parameters
                pass
            
            # Prepare request parameters
            request_params = {
                "model": model,
                "input": query,
                "tools": [file_search_tool]
            }
            
            # For o3/o4-mini, always include reasoning for better performance
            if any(model_name in model.lower() for model_name in ["o3", "o4"]):
                request_params["include"] = ["reasoning.encrypted_content"]
                if include_search_results:
                    request_params["include"].append("file_search_call.results")
            elif include_search_results:
                request_params["include"] = ["file_search_call.results"]
            
            # Make the request
            response = client.responses.create(**request_params)
            
            # Parse the response
            search_call_id = None
            response_text = ""
            citations = []
            search_results = []
            
            for output in response.output:
                if output.type == "file_search_call":
                    search_call_id = output.id
                    if include_search_results and hasattr(output, 'search_results') and output.search_results:
                        for result in output.search_results:
                            search_results.append(SearchResult(
                                file_id=result.file_id,
                                filename=result.filename if hasattr(result, 'filename') else "Unknown",
                                score=result.score if hasattr(result, 'score') else 0.0,
                                content=result.content[0].text if result.content and result.content[0].type == "text" else "",
                                attributes=result.attributes if hasattr(result, 'attributes') else {}
                            ))
                
                elif output.type == "message":
                    if output.content and len(output.content) > 0:
                        content_item = output.content[0]
                        if hasattr(content_item, 'text'):
                            response_text = content_item.text
                        if hasattr(content_item, 'annotations'):
                            citations = content_item.annotations
            
            return FileSearchResponse(
                search_call_id=search_call_id or "unknown",
                query=query,
                response_text=response_text,
                citations=citations,
                search_results=search_results if include_search_results else None
            )
            
        except Exception as e:
            logging.error(f"Failed to perform file search with responses API: {e}")
            return FileSearchResponse(
                search_call_id="error",
                query=query,
                response_text=f"Error performing search: {str(e)}",
                citations=[],
                search_results=[]
            )
    
    def delete_vector_store(self, vector_store_id: str) -> bool:
        """Delete a vector store"""
        client = self._get_client()
        
        try:
            client.vector_stores.delete(vector_store_id)
            logging.info(f"Deleted vector store: {vector_store_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete vector store {vector_store_id}: {e}")
            return False
    
    def list_vector_store_files(self, vector_store_id: str) -> List[Dict[str, Any]]:
        """List files in a vector store"""
        client = self._get_client()
        
        try:
            files = client.vector_stores.files.list(vector_store_id)
            return [
                {
                    "id": file.id,
                    "status": file.status,
                    "created_at": file.created_at,
                    "usage_bytes": file.usage_bytes if hasattr(file, 'usage_bytes') else 0
                }
                for file in files.data
            ]
        except Exception as e:
            logging.error(f"Failed to list vector store files: {e}")
            return []


# Convenience functions for common operations

def create_knowledge_base(name: str, file_paths: List[Path], 
                         expires_after_days: int = None) -> str:
    """
    Convenience function to create a vector store with files.
    
    Args:
        name: Name for the knowledge base
        file_paths: List of files to include
        expires_after_days: Optional expiration
        
    Returns:
        Vector store ID
    """
    manager = VectorSearchManager()
    return manager.create_vector_store(name, file_paths, expires_after_days)


def ask_knowledge_base(vector_store_ids: List[str], question: str,
                      model: str = "gpt-4o-mini",
                      include_sources: bool = True) -> Dict[str, Any]:
    """
    Convenience function to ask questions against a knowledge base.
    
    Args:
        vector_store_ids: List of vector store IDs to search
        question: Question to ask
        model: Model to use
        include_sources: Whether to include search results
        
    Returns:
        Dictionary with answer, citations, and optional search results
    """
    manager = VectorSearchManager()
    response = manager.file_search_with_responses_api(
        vector_store_ids=vector_store_ids,
        query=question,
        model=model,
        include_search_results=include_sources
    )
    
    return {
        "answer": response.response_text,
        "citations": response.citations,
        "search_results": response.search_results,
        "search_call_id": response.search_call_id
    }


def search_knowledge_base(vector_store_id: str, query: str, 
                         max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Convenience function for direct vector store search.
    
    Args:
        vector_store_id: Vector store to search
        query: Search query
        max_results: Maximum results to return
        
    Returns:
        List of search results as dictionaries
    """
    manager = VectorSearchManager()
    results = manager.search_vector_store(vector_store_id, query, max_results)
    
    return [
        {
            "file_id": result.file_id,
            "filename": result.filename,
            "score": result.score,
            "content": result.content,
            "attributes": result.attributes
        }
        for result in results
    ] 