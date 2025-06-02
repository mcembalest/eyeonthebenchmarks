from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union, List
import os
import pathlib
from pathlib import Path
from dotenv import load_dotenv
from google import genai  # Google Generative AI Python SDK
from google.genai import types
import time
import logging
from file_store import register_file, get_provider_file_id, register_provider_upload
import base64

# Load environment variables from .env file
load_dotenv()

# Get API key from environment - but don't fail if missing
api_key = os.environ.get("GOOGLE_API_KEY")

# Only initialize client if API key is available
client = None
if api_key:
    # Configure Google Generative AI client
    client = genai.Client(api_key=api_key)
else:
    print("[Google] No API key found - will initialize when key is provided")

def ensure_google_client():
    """Ensure Google client is initialized with current API key"""
    global client, api_key
    current_api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not current_api_key:
        raise ValueError("Google API key not found. Please configure it in Settings.")
    
    # Re-initialize client if API key has changed
    if current_api_key != api_key:
        api_key = current_api_key
        client = genai.Client(api_key=api_key)
        print("[Google] Client initialized with new API key")
    elif not client:
        client = genai.Client(api_key=current_api_key)
        print("[Google] Client initialized")
    
    return client

# Available Google models for benchmarking
AVAILABLE_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
]


COSTS = {
    "gemini-2.5-flash-preview-05-20": {
        "input": 0.15,  # $0.15 per 1M tokens for text/image/video
        "input_audio": 1.00,  # $1.00 per 1M tokens for audio
        "cached": 0.0375,  # $0.0375 per 1M tokens for text/image/video
        "cached_audio": 0.25,  # $0.25 per 1M tokens for audio
        "output_non_thinking": 0.60,  # $0.60 per 1M tokens for non-thinking output
        "output_thinking": 3.50,  # $3.50 per 1M tokens for thinking output
        "search_cost": 0.035,  # $35 per 1k requests
        "cache_storage": 1.00  # $1.00 per 1M tokens per hour
    },
    "gemini-2.5-pro-preview-05-06": {
        "input_small": 1.25,  # $1.25 per 1M tokens for prompts <= 200k tokens
        "input_large": 2.50,  # $2.50 per 1M tokens for prompts > 200k tokens
        "cached_small": 0.31,  # $0.31 per 1M tokens for prompts <= 200k tokens
        "cached_large": 0.625,  # $0.625 per 1M tokens for prompts > 200k tokens
        "output_small": 10.00,  # $10.00 per 1M tokens for prompts <= 200k tokens
        "output_large": 15.00,  # $15.00 per 1M tokens for prompts > 200k tokens
        "search_cost": 0.035,  # $35 per 1k requests
        "cache_storage": 4.50  # $4.50 per 1M tokens per hour
    }
}


def ensure_file_uploaded(file_path: Path, db_path: Path = Path.cwd()) -> str:
    """
    Ensure a file is uploaded to Google and return the provider file ID.
    Uses the new multi-provider file system to avoid duplicate uploads.
    
    Args:
        file_path: Path to the file to upload
        db_path: Path to the database directory
        
    Returns:
        provider_file_id: The Google file ID for this file
    """
    # Register file in our central registry
    file_id = register_file(file_path, db_path)
    
    # Check if this file has already been uploaded to Google
    provider_file_id = get_provider_file_id(file_id, "google", db_path)
    
    if provider_file_id:
        logging.info(f"File {file_path.name} already uploaded to Google with ID {provider_file_id}")
        return provider_file_id
    
    # File hasn't been uploaded to Google yet, upload it now
    logging.info(f"Uploading {file_path.name} to Google for the first time")
    provider_file_id = google_upload(file_path)
    
    # Register the upload in our database
    register_provider_upload(file_id, "google", provider_file_id, db_path)
    
    return provider_file_id

def google_upload(pdf_path: Path) -> str:
    """
    Upload a PDF file to Google Generative AI and return the file ID.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        str: File ID for the uploaded PDF
        
    Raises:
        Exception: If upload fails
    """    
    # Ensure client is available
    try:
        client = ensure_google_client()
    except ValueError as e:
        logging.error(str(e))
        raise
    
    try:
        # Upload file to Google
        uploaded_file = client.files.upload(
            file=pdf_path,
            config=dict(mime_type='application/pdf')
        )
        
        # Get the file name (which serves as the ID)
        file_id = uploaded_file.name
        
        logging.info(f"Successfully uploaded {pdf_path.name} to Google. File ID: {file_id}")
        return file_id
    
    except Exception as e:
        logging.error(f"Error uploading {pdf_path} to Google: {e}")
        raise Exception(f"Failed to upload PDF to Google: {str(e)}")

def prepare_google_content_for_files(prompt_text: str, file_paths: List[Path]):
    """
    Prepare Google Content structure for token counting and model calls.
    Matches the logic in google_ask_with_files.
    
    Args:
        prompt_text: The prompt text
        file_paths: List of file paths
        
    Returns:
        List of Content objects for Google API
    """
    import base64
    from google.generativeai import types
    
    # Build content parts list
    content_parts = []
    csv_content = []
    
    if file_paths:
        for file_path in file_paths:
            if file_path.suffix.lower() == '.csv':
                # Parse CSV to markdown format
                try:
                    from file_store import parse_csv_to_markdown_format
                    csv_data = parse_csv_to_markdown_format(file_path)
                    csv_content.append(f"\n--- CSV Data from {file_path.name} ({csv_data['total_rows']} rows) ---\n{csv_data['markdown_data']}\n")
                except Exception as e:
                    logging.error(f"Error parsing CSV {file_path}: {e}")
                    csv_content.append(f"\n--- Error reading CSV {file_path.name}: {str(e)} ---\n")
            else:
                # Handle PDF and other files normally as binary
                try:
                    # Read file and encode as base64
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # Encode to base64
                    base64_data = base64.b64encode(file_data).decode('utf-8')
                    
                    # Create Part from bytes with proper MIME type
                    if file_path.suffix.lower() == '.pdf':
                        mime_type = "application/pdf"
                    elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    else:
                        mime_type = "application/octet-stream"
                    
                    # Add as Part.from_bytes
                    part = types.Part.from_bytes(
                        mime_type=mime_type,
                        data=base64.b64decode(base64_data)
                    )
                    content_parts.append(part)
                    
                except Exception as e:
                    logging.error(f"Error reading file {file_path}: {e}")
                    raise Exception(f"Failed to read file {file_path}: {e}")

    # Combine CSV content with prompt text
    enhanced_prompt = prompt_text
    if csv_content:
        csv_data_text = ''.join(csv_content)
        enhanced_prompt = f"{prompt_text}\n\n{csv_data_text}"
    
    # Add prompt text as Part
    content_parts.append(types.Part.from_text(text=enhanced_prompt))
    
    # Create Content object with all parts
    contents = [
        types.Content(
            role="user",
            parts=content_parts
        )
    ]
    
    return contents

def google_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str, db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Send a query to a Google Gemini model with multiple file attachments.
    
    Args:
        file_paths: List of paths to files to include
        prompt_text: The question to ask the model
        model_name: The model to use
        db_path: Path to the database directory
        web_search: Whether to enable web search for this prompt
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output (excludes thinking tokens)
            - thinking_tokens (int): Thinking tokens used (for tracking, included in billing)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Build content parts list
    content_parts = []
    
    # Separate CSV files from other files
    csv_content = []
    
    # Always include files if they're provided - let the model decide how to use both file data and web search
    # Add files as base64-encoded bytes directly
    if file_paths:
        for file_path in file_paths:
            if file_path.suffix.lower() == '.csv':
                # Parse CSV to markdown format
                try:
                    from file_store import parse_csv_to_markdown_format
                    csv_data = parse_csv_to_markdown_format(file_path)
                    csv_content.append(f"\n--- CSV Data from {file_path.name} ({csv_data['total_rows']} rows) ---\n{csv_data['markdown_data']}\n")
                    logging.info(f"Parsed CSV {file_path.name} to markdown: {csv_data['total_rows']} rows")
                except Exception as e:
                    logging.error(f"Error parsing CSV {file_path}: {e}")
                    csv_content.append(f"\n--- Error reading CSV {file_path.name}: {str(e)} ---\n")
            else:
                # Handle PDF and other files normally as binary
                try:
                    # Read file and encode as base64
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # Encode to base64
                    base64_data = base64.b64encode(file_data).decode('utf-8')
                    
                    # Create Part from bytes with proper MIME type
                    if file_path.suffix.lower() == '.pdf':
                        mime_type = "application/pdf"
                    elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    else:
                        mime_type = "application/octet-stream"
                    
                    # Add as Part.from_bytes
                    part = types.Part.from_bytes(
                        mime_type=mime_type,
                        data=base64.b64decode(base64_data)
                    )
                    content_parts.append(part)
                    
                    logging.info(f"Added file {file_path.name} as base64 bytes ({len(file_data)} bytes)")
                    
                except Exception as e:
                    logging.error(f"Error reading file {file_path}: {e}")
                    raise Exception(f"Failed to read file {file_path}: {e}")
    
    # Combine CSV content with prompt text
    enhanced_prompt = prompt_text
    if csv_content:
        csv_data_text = ''.join(csv_content)
        enhanced_prompt = f"{prompt_text}\n\n{csv_data_text}"
    
    # Add prompt text as Part
    content_parts.append(types.Part.from_text(text=enhanced_prompt))
    
    # Create Content object with all parts
    contents = [
        types.Content(
            role="user",
            parts=content_parts
        )
    ]
    
    return google_ask_internal(contents, model_name, web_search)

def google_ask_internal(contents: List, model_name: str, web_search: bool = False) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Internal function to send a query to Google with prepared contents.
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output (excludes thinking tokens)
            - thinking_tokens (int): Thinking tokens used (for tracking, included in billing)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Add direct console output for high visibility
    print(f"\n🔄 GOOGLE API CALL STARTING - MODEL: {model_name}")
    print(f"   Contents: {len(contents)} items")
    if web_search:
        print("   Web search enabled")
    
    logging.info(f"===== GOOGLE_ASK_INTERNAL FUNCTION CALLED =====")
    logging.info(f"Arguments: model_name={model_name}, web_search={web_search}")
    
    try:
        # Ensure client is available
        try:
            client = ensure_google_client()
        except ValueError as e:
            logging.error(str(e))
            raise
        
        # Prepare tools for web search if enabled
        tools = []
        
        if web_search:
            from google.genai.types import Tool, GoogleSearch
            tools.append(Tool(google_search=GoogleSearch()))
        
        # Send request to Google API
        try:
            # Create generation config
            generate_content_config = types.GenerateContentConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=10000,
                tools=tools if web_search else None,
                response_mime_type="text/plain"
            )
            
            # Generate content using the new structure
            response = client.models.generate_content(
                model=model_name,
                contents=contents, 
                config=generate_content_config
            )
            
            # Parse response - USE TOTAL_TOKEN_COUNT FOR ACCURATE BILLING
            tokens_metadata = response.usage_metadata
            
            # Use total_token_count as the authoritative source for billing
            total_tokens_used = tokens_metadata.total_token_count or 0
            
            # Get individual components for detailed reporting with None checks
            standard_input_tokens = tokens_metadata.prompt_token_count or 0
            output_tokens = tokens_metadata.candidates_token_count or 0
            
            # Calculate any additional tokens (thinking, tool use, etc.)
            additional_tokens = total_tokens_used - (standard_input_tokens + output_tokens)
            
            # Check for specific token types we might be missing
            thinking_tokens = getattr(tokens_metadata, 'thoughts_token_count', 0) or 0
            tool_use_tokens = getattr(tokens_metadata, 'tool_use_prompt_token_count', 0) or 0
            cached_content_tokens = getattr(tokens_metadata, 'cached_content_token_count', 0) or 0
            
            # Log detailed token breakdown for transparency
            logging.info(f"Google token breakdown:")
            logging.info(f"  - Prompt tokens: {standard_input_tokens}")
            logging.info(f"  - Output tokens: {output_tokens}")
            logging.info(f"  - Thinking tokens: {thinking_tokens}")
            logging.info(f"  - Tool use tokens: {tool_use_tokens}")
            logging.info(f"  - Cached content tokens: {cached_content_tokens}")
            logging.info(f"  - Additional tokens: {additional_tokens}")
            logging.info(f"  - TOTAL (authoritative): {total_tokens_used}")
            
            print(f"   📊 Google token details:")
            print(f"       Prompt: {standard_input_tokens}, Output: {output_tokens}")
            if thinking_tokens > 0:
                print(f"       Thinking: {thinking_tokens}")
            if tool_use_tokens > 0:
                print(f"       Tool use: {tool_use_tokens}")
            if cached_content_tokens > 0:
                print(f"       Cached: {cached_content_tokens}")
            if additional_tokens > 0:
                print(f"       Other: {additional_tokens}")
            print(f"       TOTAL: {total_tokens_used}")
            
            # For our return values, we need to split the total appropriately
            # Google's total_token_count includes cached content, so we need to be careful not to double-count
            
            # Cached content tokens are already included in total_token_count but reported separately
            cached_input_tokens = cached_content_tokens or 0
            
            # The non-cached prompt tokens
            non_cached_prompt_tokens = standard_input_tokens - cached_input_tokens
            
            # Keep thinking tokens separate for tracking
            output_tokens_without_thinking = output_tokens  # Original output tokens without thinking
            
            # Add tool use tokens to non-cached input
            adjusted_input_tokens = non_cached_prompt_tokens + (tool_use_tokens or 0)
            
            # Verify our adjusted totals match the authoritative total
            calculated_total = adjusted_input_tokens + cached_input_tokens + output_tokens_without_thinking + thinking_tokens
            if abs(calculated_total - total_tokens_used) > 5:  # Allow small rounding differences
                logging.warning(f"Token calculation mismatch: calculated {calculated_total} vs actual {total_tokens_used}")
                print(f"   ⚠️ Token calculation mismatch: {calculated_total} vs {total_tokens_used}")
                
                # If there's still a significant mismatch, distribute the difference
                difference = total_tokens_used - calculated_total
                output_tokens_without_thinking += difference
                
                # Recalculate
                calculated_total = adjusted_input_tokens + cached_input_tokens + output_tokens_without_thinking + thinking_tokens
                print(f"   🔧 Adjusted: {calculated_total} (added {difference} to output)")
            
            # Update our variables for the rest of the function
            standard_input_tokens = adjusted_input_tokens
            cached_input_tokens = cached_input_tokens
            output_tokens = output_tokens_without_thinking
            
            # Detect web search usage by checking if tools were used
            web_search_used = False
            web_search_queries = 0
            web_search_content = ""
            
            # Only count as web search if we explicitly enabled it AND grounding was found
            # Google models may automatically use grounding, but we only count it as "web search"
            # if the user explicitly requested it
            if web_search:
                # Check if the response contains web search results and extract content
                if hasattr(response, 'candidates') and response.candidates is not None:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                            web_search_used = True
                            web_search_queries = 1
                            
                            # Extract grounding content for token counting and sources
                            if hasattr(candidate.grounding_metadata, 'grounding_chunks') and candidate.grounding_metadata.grounding_chunks:
                                for chunk in candidate.grounding_metadata.grounding_chunks:
                                    if hasattr(chunk, 'web') and hasattr(chunk.web, 'title'):
                                        web_search_content += f"Title: {chunk.web.title}\n"
                                        if hasattr(chunk.web, 'uri'):
                                            web_search_content += f"URL: {chunk.web.uri}\n"
                                        web_search_content += "---\n"
                            
                            # Extract search entry point content (this contains most of the grounding data)
                            if hasattr(candidate.grounding_metadata, 'search_entry_point') and candidate.grounding_metadata.search_entry_point:
                                entry_point = candidate.grounding_metadata.search_entry_point
                                if hasattr(entry_point, 'rendered_content'):
                                    web_search_content += f"Search entry point:\n{entry_point.rendered_content}\n---\n"
                            
                            # Extract web search queries with comprehensive error handling
                            if hasattr(candidate.grounding_metadata, 'web_search_queries'):
                                try:
                                    queries = candidate.grounding_metadata.web_search_queries
                                    if queries is not None:
                                        # Safely get length - handle case where queries might not be iterable
                                        if hasattr(queries, '__len__'):
                                            web_search_queries = len(queries)
                                        elif hasattr(queries, '__iter__'):
                                            web_search_queries = sum(1 for _ in queries)
                                        else:
                                            web_search_queries = 1  # Assume 1 query if we can't count
                                        
                                        # Safely join queries for display
                                        if hasattr(queries, '__iter__') and not isinstance(queries, str):
                                            try:
                                                query_list = list(queries)
                                                web_search_content += f"Search queries: {', '.join(str(q) for q in query_list)}\n---\n"
                                            except Exception as join_e:
                                                logging.warning(f"Could not join web search queries: {join_e}")
                                                web_search_content += f"Search queries detected but could not be listed\n---\n"
                                        else:
                                            web_search_content += f"Search query: {str(queries)}\n---\n"
                                    else:
                                        web_search_queries = 1  # Default if queries is None
                                        web_search_content += f"Search queries detected but were None\n---\n"
                                except Exception as e:
                                    logging.warning(f"Could not process web search queries: {e}")
                                    web_search_queries = 1  # Assume 1 query if we can't count
                                    web_search_content += f"Search queries detected but could not be processed: {str(e)}\n---\n"
                        elif hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                            for part in candidate.content.parts:
                                # Look for function calls or tool usage indicators
                                if hasattr(part, 'function_call') or (hasattr(part, 'text') and part.text and 'search' in str(part.text).lower()[:200]):
                                    web_search_used = True
                                    web_search_queries = 1  # Assume 1 search query for now
                                    web_search_content += f"Function call or search detected in response\n"
                                    break
            
            # Count tokens on web search content if available
            web_search_tokens = 0
            if web_search_used and web_search_content:
                try:
                    # Use Google's token counting for the search content
                    search_token_response = client.models.count_tokens(
                        model=model_name,
                        contents=web_search_content
                    )
                    web_search_tokens = search_token_response.total_tokens
                except Exception as e:
                    logging.warning(f"Could not count web search tokens: {e}")
                    # Rough estimate: ~1 token per 4 characters
                    web_search_tokens = len(web_search_content) // 4
            
            # Log web search detection
            if web_search_used:
                if web_search_tokens > 0:
                    logging.info(f"Web search detected: {web_search_queries} queries, {web_search_tokens} grounding tokens (already included in total)")
                    print(f"   🌐 Web search used: {web_search_queries} queries")
                    print(f"   📊 Grounding tokens: {web_search_tokens} (already included in total_token_count)")
                else:
                    logging.info(f"Web search detected: {web_search_queries} queries")
                    print(f"   🌐 Web search used: {web_search_queries} queries")
                    print(f"   📊 Grounding tokens could not be counted")
            elif not web_search:
                # If web search was disabled but Google still used automatic grounding,
                # we should note this but not count it as intentional web search
                if hasattr(response, 'candidates') and response.candidates is not None:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                            print(f"   ℹ️  Google used automatic grounding (not counted as web search)")
                            break
            
            # Extract clean response text (not response.text which includes metadata)
            clean_response_text = ""
            if hasattr(response, 'candidates') and response.candidates is not None:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                clean_response_text += part.text
            
            # Ensure clean_response_text is never None
            if clean_response_text is None:
                clean_response_text = ""
            
            # Debug logging to understand what we're getting - safely handle None
            response_length = len(clean_response_text) if clean_response_text is not None else 0
            logging.info(f"Clean response text extracted: {response_length} characters")
            if hasattr(response, 'text'):
                raw_text_length = len(response.text) if response.text is not None else 0
                logging.info(f"Raw response.text length: {raw_text_length} characters")
                if response.text:
                    logging.info(f"Raw response.text preview: {response.text[:200]}...")
            
            # If we couldn't extract clean text, there's a problem with the response structure
            if not clean_response_text:
                logging.error("Could not extract clean text from Google response")
                logging.error(f"Response structure: {type(response)}")
                if hasattr(response, 'candidates'):
                    logging.error(f"Candidates: {len(response.candidates) if response.candidates else 0}")
                    if response.candidates:
                        for i, candidate in enumerate(response.candidates):
                            logging.error(f"Candidate {i}: {type(candidate)}")
                            if hasattr(candidate, 'finish_reason'):
                                logging.error(f"  Finish Reason: {candidate.finish_reason}")
                            if hasattr(candidate, 'safety_ratings'):
                                logging.error(f"  Safety Ratings: {candidate.safety_ratings}")
                            if hasattr(candidate, 'content') and candidate.content:
                                logging.error(f"  Content: {type(candidate.content)}")
                                if hasattr(candidate.content, 'parts'):
                                    logging.error(f"  Parts: {len(candidate.content.parts) if candidate.content.parts else 0}")
                
                # Try alternative extraction methods
                if hasattr(response, 'text') and response.text:
                    # If response.text exists but contains metadata, try to clean it
                    raw_text = response.text
                    
                    # Remove common metadata patterns that appear in Google responses
                    # Look for patterns like "SEARCH QUERIES:" and remove everything before the actual content
                    import re
                    
                    # Try to find where the actual content starts after metadata
                    # Common patterns to remove:
                    patterns_to_remove = [
                        r'^.*?SEARCH QUERIES:.*?\n',  # Remove search query metadata
                        r'^.*?WEB SEARCH.*?\n',       # Remove web search metadata
                        r'^.*?GROUNDING.*?\n',        # Remove grounding metadata
                    ]
                    
                    cleaned_text = raw_text
                    for pattern in patterns_to_remove:
                        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
                    
                    # If we removed some metadata, use the cleaned version
                    if len(cleaned_text) < len(raw_text) and cleaned_text.strip():
                        clean_response_text = cleaned_text.strip()
                        logging.info(f"Used cleaned response.text: {len(clean_response_text)} characters")
                    else:
                        # Last resort: use raw text but log the issue
                        clean_response_text = raw_text
                        logging.warning("Using raw response.text as fallback - may contain metadata")
                else:
                    # If we still have no response text, return a helpful error message
                    clean_response_text = "ERROR: Gemini API returned invalid response structure. This typically happens when the model encounters an internal error or when the content violates content policies. Please try running this prompt again."
                    logging.error("No response text could be extracted from Gemini response")
            
            return clean_response_text, standard_input_tokens, cached_input_tokens, output_tokens, thinking_tokens, web_search_used, web_search_content
            
        except Exception as e:
            error_details = str(e)
            logging.error(f"Google API Error: {error_details}")
            # Check for token limit errors and provide more readable message
            if "exceeds maximum input size" in error_details or "exceeds the context size" in error_details:
                return f"ERROR: Token limit exceeded. Please reduce the input size.", 0, 0, 0, 0, False, ""
            return f"ERROR: {error_details}", 0, 0, 0, 0, False, ""
            
    except Exception as e:
        print(f"\n❌ GOOGLE API CALL FAILED")
        print(f"   Error message: {str(e)}")
        print(f"   Model: {model_name}")
        
        logging.error(f"Error asking Google model with model {model_name}: {e}")
        # Re-raise the exception to be caught by the runner
        raise Exception(f"Google API Error: {e}") from e

def calculate_cost(
    model_name: str,
    standard_input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    search_queries: int = 0,
    prompt_size_category: str = "small"  # "small" for <=200k, "large" for >200k
) -> Dict[str, Any]:
    """
    Calculate the cost of using a Google model.
    
    Args:
        model_name: The model to use (e.g., "gemini-2.5-flash-preview-05-20")
        standard_input_tokens: Number of standard input tokens
        cached_input_tokens: Number of cached input tokens
        output_tokens: Number of non-thinking output tokens
        thinking_tokens: Number of thinking output tokens (charged differently)
        search_queries: Number of web search queries
        prompt_size_category: "small" for <=200k tokens, "large" for >200k tokens
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name not in COSTS:
        return {"error": f"Model {model_name} not found in cost database"}
    
    model_costs = COSTS[model_name]
    
    # Calculate input costs (prices are per 1M tokens)
    if "input_small" in model_costs:  # Pro model with size-based pricing
        input_rate = model_costs[f"input_{prompt_size_category}"]
        cached_rate = model_costs[f"cached_{prompt_size_category}"]
        output_rate = model_costs[f"output_{prompt_size_category}"]
    else:  # Flash model with flat pricing
        input_rate = model_costs["input"]
        cached_rate = model_costs["cached"]
        output_rate = model_costs["output_non_thinking"]
    
    input_cost = (standard_input_tokens * input_rate) / 1_000_000
    cached_cost = (cached_input_tokens * cached_rate) / 1_000_000
    
    # Calculate output costs
    if "output_thinking" in model_costs and thinking_tokens > 0:
        # Flash model with separate thinking token pricing
        output_cost = (output_tokens * model_costs["output_non_thinking"]) / 1_000_000
        thinking_cost = (thinking_tokens * model_costs["output_thinking"]) / 1_000_000
    else:
        # Pro model or no thinking tokens
        output_cost = (output_tokens * output_rate) / 1_000_000
        thinking_cost = 0
    
    # Calculate search costs if applicable
    search_cost = 0
    if search_queries > 0 and "search_cost" in model_costs:
        search_cost = search_queries * model_costs["search_cost"]
    
    total_cost = input_cost + cached_cost + output_cost + thinking_cost + search_cost
    
    return {
        "model": model_name,
        "input_cost": round(input_cost, 6),
        "cached_cost": round(cached_cost, 6),
        "output_cost": round(output_cost, 6),
        "thinking_cost": round(thinking_cost, 6),
        "search_cost": round(search_cost, 6),
        "total_cost": round(total_cost, 6),
        "tokens": {
            "standard_input": standard_input_tokens,
            "cached_input": cached_input_tokens,
            "output": output_tokens,
            "thinking": thinking_tokens,
            "total": standard_input_tokens + cached_input_tokens + output_tokens + thinking_tokens
        }
    }

def count_tokens_google(contents: List, model_name: str) -> int:
    """
    Count tokens for Google models using their count_tokens API.
    Works with the new Content structure using base64 bytes.
    
    Args:
        contents: List of Content objects or simple content
        model_name: Google model name
        
    Returns:
        Actual token count from Google's API
    """
    try:
        # Ensure client is available
        client = ensure_google_client()
        
        # Use Google's count_tokens API directly with the content structure
        response = client.models.count_tokens(
            model=model_name,
            contents=contents
        )
        
        logging.info(f"Google token count for {model_name}: {response.total_tokens}")
        return response.total_tokens
            
    except Exception as e:
        logging.error(f"Error counting tokens for Google model {model_name}: {e}")
        # DO NOT FALLBACK - fail fast instead
        raise Exception(f"Token counting failed for Google model {model_name}: {e}") from e

def get_context_limit_google(model_name: str) -> int:
    """
    Get the context window limit for a Google model.
    
    Args:
        model_name: Google model name
        
    Returns:
        Context window size in tokens
    """
    # All Gemini models currently have ~1M token context windows
    return 1048576
