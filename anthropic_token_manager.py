"""
Anthropic Token Budget Management System

Handles smart allocation of token budget between files, web search, and output
for Anthropic models with 200k context limits.
"""

import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import PyPDF2
import anthropic
from file_store import register_file, get_pdf_chunks # get_provider_file_id, register_provider_upload removed as unused
import re

@dataclass
class TokenBudget:
    """Token budget allocation for a request"""
    total_context: int
    prompt_tokens: int
    web_search_reserve: int 
    output_reserve: int
    available_for_files: int
    
    @property
    def used_budget(self) -> int:
        return self.prompt_tokens + self.web_search_reserve + self.output_reserve
    
    @property
    def remaining_budget(self) -> int:
        return self.total_context - self.used_budget

@dataclass 
class FileTokenInfo:
    """Token information for a file"""
    file_path: Path
    estimated_tokens: int
    total_pages: Optional[int] = None
    can_fit_full: bool = False

@dataclass
class RequestPlan:
    """Plan for handling a request within token limits"""
    strategy: str  # "full_files", "chunked_files", "summary_first"
    files_to_include: List[Dict[str, Any]]
    estimated_total_tokens: int
    warnings: List[str]
    
class AnthropicTokenManager:
    """Manages token budgets and file processing for Anthropic models"""
    
    # Token reserves for different components
    OUTPUT_RESERVE = 8000  # Reserve for response
    WEB_SEARCH_RESERVE_DEFAULT = 30000  # Conservative estimate for web search
    PROMPT_OVERHEAD = 2000  # Overhead for system messages, formatting
    
    # Chunking parameters
    MAX_PAGES_PER_CHUNK = 5  # Smaller chunks for better selection
    MIN_PAGES_PER_CHUNK = 10  # Minimum viable chunk size
    
    def __init__(self, model_name: str, client: anthropic.Anthropic, db_path: Path):
        self.model_name = model_name
        self.client = client
        self.db_path = db_path
        self.context_limit = 200000  # All Anthropic models have 200k limit
        
    def estimate_prompt_tokens(self, prompt_text: str) -> int:
        """Estimate tokens for prompt text using character-based heuristic"""
        # Conservative estimate: ~3.5 characters per token for English text
        return len(prompt_text) // 3
    
    def estimate_file_tokens_via_base64(self, file_path: Path) -> int:
        """
        Get accurate token count for a file using base64 encoding.
        This is the only reliable way to count tokens for PDFs with Anthropic.
        """
        try:
            # Read and encode file
            with open(file_path, "rb") as f:
                file_data = f.read()
            pdf_base64 = base64.standard_b64encode(file_data).decode("utf-8")
            
            # Create test content for token counting
            test_content = [
                {
                    "type": "document", 
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64
                    }
                },
                {
                    "type": "text",
                    "text": "Count tokens."  # Minimal prompt
                }
            ]
            
            # Count tokens using Anthropic's API
            response = self.client.messages.count_tokens(
                model=self.model_name,
                messages=[{
                    "role": "user",
                    "content": test_content
                }]
            )
            
            token_count = response.input_tokens
            logging.info(f"Accurate token count for {file_path.name}: {token_count}")
            return token_count
            
        except Exception as e:
            logging.error(f"Failed to count tokens for {file_path}: {e}")
            # Fallback: estimate based on file size (very rough)
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            estimated_tokens = int(file_size_mb * 50000)  # ~50k tokens per MB as rough estimate
            logging.warning(f"Using rough estimate for {file_path.name}: {estimated_tokens} tokens")
            return estimated_tokens
    
    def get_pdf_page_count(self, file_path: Path) -> int:
        """Get the number of pages in a PDF"""
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                return len(pdf_reader.pages)
        except Exception as e:
            logging.warning(f"Could not determine page count for {file_path}: {e}")
            return 0
    
    def split_pdf_by_pages(self, original_file_path: Path) -> List[Path]:
        """
        Retrieves pre-generated PDF chunks for a given PDF file.
        If the file is not a PDF or if chunks are not found, returns the original file path in a list.
        """
        if not original_file_path.suffix.lower() == '.pdf':
            logging.debug(f"{original_file_path.name} is not a PDF. Returning original path.")
            return [original_file_path]

        try:
            # Ensure the original file is registered to get its ID.
            # file_store.register_file handles existing files gracefully.
            original_file_id = register_file(original_file_path, db_path=self.db_path)
            
            if not original_file_id:
                logging.error(f"Could not get or register file ID for {original_file_path}. Returning original path.")
                return [original_file_path]
            
            # Retrieve pre-generated chunk paths from the database.
            chunk_paths = get_pdf_chunks(original_file_id, db_path=self.db_path)
            
            if chunk_paths:
                logging.info(f"Retrieved {len(chunk_paths)} pre-generated chunks for {original_file_path.name}.")
                return chunk_paths
            else:
                logging.warning(f"No pre-generated chunks found for {original_file_path.name} (ID: {original_file_id}). Returning original path.")
                return [original_file_path]
                
        except Exception as e:
            logging.error(f"Error retrieving PDF chunks for {original_file_path}: {e}")
            return [original_file_path]  # Fallback to original file path on error
    
    def analyze_files(self, file_paths: List[Path]) -> List[FileTokenInfo]:
        """Analyze files to determine token requirements"""
        file_info = []
        
        for file_path in file_paths:
            if file_path.suffix.lower() == '.pdf':
                # Get accurate token count and page info for PDFs
                token_count = self.estimate_file_tokens_via_base64(file_path)
                page_count = self.get_pdf_page_count(file_path)
                
                file_info.append(FileTokenInfo(
                    file_path=file_path,
                    estimated_tokens=token_count,
                    total_pages=page_count,
                    can_fit_full=token_count < 180000  # Leave room for prompt + web search
                ))
            else:
                # For non-PDF files, estimate based on size
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    token_count = len(content) // 3  # Conservative estimate
                except:
                    token_count = file_path.stat().st_size // 4  # Very rough fallback
                
                file_info.append(FileTokenInfo(
                    file_path=file_path,
                    estimated_tokens=token_count,
                    can_fit_full=token_count < 180000
                ))
        
        return file_info
    
    def create_token_budget(self, prompt_text: str, web_search_enabled: bool) -> TokenBudget:
        """Create a token budget for the request"""
        prompt_tokens = self.estimate_prompt_tokens(prompt_text) + self.PROMPT_OVERHEAD
        
        web_search_reserve = self.WEB_SEARCH_RESERVE_DEFAULT if web_search_enabled else 0
        
        available_for_files = (
            self.context_limit - 
            prompt_tokens - 
            web_search_reserve - 
            self.OUTPUT_RESERVE
        )
        
        return TokenBudget(
            total_context=self.context_limit,
            prompt_tokens=prompt_tokens,
            web_search_reserve=web_search_reserve,
            output_reserve=self.OUTPUT_RESERVE,
            available_for_files=available_for_files
        )
    
    def plan_request(self, file_paths: List[Path], prompt_text: str, 
                    web_search_enabled: bool) -> RequestPlan:
        """
        Create an execution plan for the request within token limits.
        Uses smart chunking with relevance scoring to select the best content.
        """
        budget = self.create_token_budget(prompt_text, web_search_enabled)
        warnings = []
        
        logging.info(f"Smart token budget analysis:")
        logging.info(f"  Total context: {budget.total_context}")
        logging.info(f"  Prompt + overhead: {budget.prompt_tokens}")
        logging.info(f"  Web search reserve: {budget.web_search_reserve}")
        logging.info(f"  Output reserve: {budget.output_reserve}")
        logging.info(f"  Available for files: {budget.available_for_files}")
        
        # Analyze all files to see which ones need chunking
        file_info = self.analyze_files(file_paths)
        total_file_tokens = sum(info.estimated_tokens for info in file_info)
        
        logging.info(f"  Files require: {total_file_tokens}")
        
        # Strategy 1: All files fit as-is
        if total_file_tokens <= budget.available_for_files:
            return RequestPlan(
                strategy="full_files",
                files_to_include=[{"path": info.file_path, "method": "full"} for info in file_info],
                estimated_total_tokens=budget.used_budget + total_file_tokens,
                warnings=warnings
            )
        
        # Strategy 2: Smart chunking with relevance scoring
        print(f"   📄 Files exceed budget, using smart chunk selection...")
        
        all_chunks = []
        
        # Process each PDF file
        for info in file_info:
            if info.file_path.suffix.lower() == '.pdf':
                print(f"   🔍 Analyzing chunks for {info.file_path.name}...")
                chunks = self.split_pdf_into_smart_chunks(info.file_path, prompt_text)
                all_chunks.extend(chunks)
            else:
                # For non-PDF files, include if they fit
                if info.estimated_tokens <= budget.available_for_files:
                    all_chunks.append({
                        "path": info.file_path,
                        "tokens": info.estimated_tokens,
                        "relevance_score": 1.0,  # Assume high relevance for non-PDFs
                        "page_range": "full",
                        "source_file": info.file_path.name,
                        "method": "full"
                    })
        
        # Sort all chunks by relevance score (highest first)
        all_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Select chunks that fit within budget
        selected_chunks = []
        remaining_budget = budget.available_for_files
        
        print(f"   📊 Selecting best chunks within {remaining_budget:,} token budget:")
        
        for chunk in all_chunks:
            if chunk["tokens"] <= remaining_budget:
                selected_chunks.append(chunk)
                remaining_budget -= chunk["tokens"]
                print(f"     ✅ Selected {chunk['source_file']} pages {chunk['page_range']} "
                      f"({chunk['tokens']:,} tokens, relevance: {chunk['relevance_score']:.2f})")
            else:
                print(f"     ❌ Skipped {chunk['source_file']} pages {chunk['page_range']} "
                      f"({chunk['tokens']:,} tokens, relevance: {chunk['relevance_score']:.2f}) - insufficient budget")
        
        if not selected_chunks:
            warnings.append("No chunks could fit within the available token budget")
            return RequestPlan(
                strategy="no_files",
                files_to_include=[],
                estimated_total_tokens=budget.used_budget,
                warnings=warnings
            )
        
        # Convert to files_to_include format
        files_to_include = []
        for chunk in selected_chunks:
            if chunk.get("method") == "full":
                files_to_include.append({
                    "path": chunk["path"],
                    "method": "full",
                    "tokens": chunk["tokens"]
                })
            else:
                files_to_include.append({
                    "path": chunk["path"],
                    "method": "chunk_selected",
                    "tokens": chunk["tokens"],
                    "relevance_score": chunk["relevance_score"],
                    "page_range": chunk["page_range"],
                    "source_file": chunk["source_file"]
                })
        
        total_selected_tokens = sum(chunk["tokens"] for chunk in selected_chunks)
        
        # Add summary to warnings
        chunk_summary = {}
        for chunk in selected_chunks:
            source = chunk["source_file"]
            if source not in chunk_summary:
                chunk_summary[source] = []
            chunk_summary[source].append(chunk["page_range"])
        
        for source_file, ranges in chunk_summary.items():
            warnings.append(f"Using chunks from {source_file}: pages {', '.join(ranges)}")
        
        return RequestPlan(
            strategy="smart_chunked_files",
            files_to_include=files_to_include,
            estimated_total_tokens=budget.used_budget + total_selected_tokens,
            warnings=warnings
        )
    
    def execute_plan(self, plan: RequestPlan, db_path: Path) -> List[Dict[str, Any]]:
        """
        Execute the request plan by preparing files according to the strategy.
        Returns content list ready for Anthropic API.
        """
        content = []
        
        for file_spec in plan.files_to_include:
            file_path = file_spec["path"]
            method = file_spec["method"]
            
            try:
                if method == "full":
                    # Use Files API for full files
                    from models_anthropic import ensure_file_uploaded
                    file_id = ensure_file_uploaded(file_path, db_path)
                    
                    content.append({
                        "type": "document",
                        "source": {
                            "type": "file", 
                            "file_id": file_id
                        }
                    })
                    logging.info(f"Added full file {file_path.name} via Files API")
                    
                elif method == "chunk_selected":
                    # Use pre-selected chunk via base64
                    with open(file_path, "rb") as f:
                        chunk_data = f.read()
                    chunk_base64 = base64.standard_b64encode(chunk_data).decode("utf-8")
                    
                    content.append({
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": chunk_base64
                        }
                    })
                    
                    page_range = file_spec.get("page_range", "unknown")
                    source_file = file_spec.get("source_file", file_path.name)
                    relevance = file_spec.get("relevance_score", 0.0)
                    
                    logging.info(f"Added chunk from {source_file} pages {page_range} "
                               f"(relevance: {relevance:.2f}) via base64")
                    
                    # Clean up chunk file if it's a temporary chunk
                    if "_chunk_" in file_path.name and file_path != Path(source_file):
                        try:
                            file_path.unlink()
                        except:
                            pass
                    
                elif method == "chunk":
                    # Legacy chunking method (fallback)
                    max_pages = file_spec.get("max_pages", self.MAX_PAGES_PER_CHUNK)
                    chunk_files = self.split_pdf_by_pages(file_path, max_pages)
                    
                    if chunk_files:
                        chunk_path = chunk_files[0]
                        
                        with open(chunk_path, "rb") as f:
                            chunk_data = f.read()
                        chunk_base64 = base64.standard_b64encode(chunk_data).decode("utf-8")
                        
                        content.append({
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": chunk_base64
                            }
                        })
                        
                        logging.info(f"Added chunk of {file_path.name} (pages 1-{max_pages}) via base64")
                        
                        # Clean up temporary chunk files
                        for chunk_file in chunk_files:
                            if chunk_file != file_path:
                                try:
                                    chunk_file.unlink()
                                except:
                                    pass
                
            except Exception as e:
                logging.error(f"Failed to process file {file_path} with method {method}: {e}")
                continue
        
        return content

    def _extract_text_from_pdf_chunk(self, pdf_path: Path) -> str:
        """Extracts raw text from a PDF file path."""
        text = ""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + " "
            logging.debug(f"Extracted text from {pdf_path.name} for keyword analysis.")
        except Exception as e:
            logging.warning(f"Could not extract text from {pdf_path.name} for keyword analysis: {e}")
        return text

    def _tokenize_text(self, text: str) -> set:
        """Converts text to a set of unique lowercase words."""
        if not text:
            return set()
        # Remove punctuation and split into words, convert to lowercase
        words = re.findall(r'\b\w+\b', text.lower())
        return set(words)

    def get_chunk_relevance_score(self, chunk_path: Path, query: str) -> float:
        """
        Scores a PDF chunk's relevance to the query using local keyword overlap (Jaccard index).
        Returns a score between 0 and 1.
        """
        try:
            chunk_text = self._extract_text_from_pdf_chunk(chunk_path)
            if not chunk_text:
                logging.warning(f"No text extracted from {chunk_path.name}, assigning default relevance.")
                return 0.1 # Low relevance if no text

            query_keywords = self._tokenize_text(query)
            chunk_keywords = self._tokenize_text(chunk_text)

            if not query_keywords or not chunk_keywords:
                logging.debug(f"No keywords for query or chunk {chunk_path.name}, assigning 0 relevance.")
                return 0.0 # No overlap if one set is empty

            intersection = query_keywords.intersection(chunk_keywords)
            union = query_keywords.union(chunk_keywords)

            if not union: # Should not happen if chunk_keywords wasn't empty
                return 0.0

            jaccard_score = len(intersection) / len(union)
            
            logging.info(f"Chunk {chunk_path.name} keyword overlap score: {jaccard_score:.2f} (Intersection: {len(intersection)}, Union: {len(union)})")
            return jaccard_score
            
        except Exception as e:
            logging.error(f"Failed to score chunk {chunk_path.name} with keyword overlap: {e}")
            return 0.1  # Default to low relevance on error
    
    def split_pdf_into_smart_chunks(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """
        Split a PDF into chunks and score their relevance to the query.
        Returns list of chunk info with relevance scores.
        """
        chunk_files = self.split_pdf_by_pages(file_path, self.MAX_PAGES_PER_CHUNK)
        chunk_info = []
        
        for chunk_path in chunk_files:
            try:
                # Get token count for this chunk
                with open(chunk_path, "rb") as f:
                    chunk_data = f.read()
                chunk_base64 = base64.standard_b64encode(chunk_data).decode("utf-8")
                
                # Count tokens
                test_content = [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64", 
                            "media_type": "application/pdf",
                            "data": chunk_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": "Count tokens."
                    }
                ]
                
                token_response = self.client.messages.count_tokens(
                    model=self.model_name,
                    messages=[{
                        "role": "user",
                        "content": test_content
                    }]
                )
                
                chunk_tokens = token_response.input_tokens
                
                # Get relevance score
                relevance_score = self.get_chunk_relevance_score(chunk_path, query)
                
                # Get page range from filename
                if "_chunk_" in chunk_path.name:
                    page_range = chunk_path.name.split("_chunk_")[1].replace(".pdf", "")
                else:
                    page_range = "1-20"  # Default for original file
                
                chunk_info.append({
                    "path": chunk_path,
                    "tokens": chunk_tokens,
                    "relevance_score": relevance_score,
                    "page_range": page_range,
                    "source_file": file_path.name
                })
                
                logging.info(f"Chunk {chunk_path.name}: {chunk_tokens} tokens, relevance {relevance_score:.2f}")
                
            except Exception as e:
                logging.error(f"Failed to analyze chunk {chunk_path}: {e}")
                continue
        
        # Sort by relevance score (highest first)
        chunk_info.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return chunk_info 