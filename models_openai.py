from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
import logging
from dotenv import load_dotenv
import openai
from file_store import register_file, get_provider_file_id, register_provider_upload
import tiktoken

# Import vector search functionality
from vector_search import VectorSearchManager, FileSearchResponse

# Load environment variables from .env file
load_dotenv()

# Get API key from environment - but don't fail if missing
api_key = os.environ.get("OPENAI_API_KEY")

# Only initialize client if API key is available
client = None
if api_key:
    # Configure OpenAI client
    client = openai.OpenAI(api_key=api_key)
else:
    print("[OpenAI] No API key found - will initialize when key is provided")


def ensure_openai_client():
    """Ensure OpenAI client is initialized with current API key"""
    global client, api_key
    current_api_key = os.environ.get("OPENAI_API_KEY")
    
    if not current_api_key:
        raise ValueError("OpenAI API key not found. Please configure it in Settings.")
    
    # Re-initialize client if API key has changed
    if current_api_key != api_key:
        api_key = current_api_key
        client = openai.OpenAI(api_key=api_key)
        print("[OpenAI] Client initialized with new API key")
    elif not client:
        client = openai.OpenAI(api_key=current_api_key)
        print("[OpenAI] Client initialized")
    
    return client


AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "o3",
    "o4-mini"
]


COSTS = {
    "gpt-4.1": {"input": 2.00, "cached": 0.50, "output": 8.00, "search_cost": 0.035},
    "gpt-4.1-mini": {"input": 0.40, "cached": 0.10, "output": 1.60, "search_cost": 0.0275},
    "gpt-4o": {"input": 2.50, "cached": 1.25, "output": 10.00, "search_cost": 0.035},
    "gpt-4o-mini": {"input": 0.15, "cached": 0.075, "output": 0.60, "search_cost": 0.0275},
    "o3": {"input": 10.00, "cached": 2.50, "output": 40.00, "search_cost": 0.035},
    "o4-mini": {"input": 1.10, "cached": 0.55, "output": 4.40, "search_cost": 0.0275},
    "gpt-3.5-turbo": {"input": 0.50, "cached": 0.25, "output": 1.50, "search_cost": 0.0275}
}

SEARCH_CONTEXT_COSTS = {
    "low": 0.03,    # $30/1k searches
    "medium": 0.035,  # $35/1k searches (default)
    "high": 0.05,   # $50/1k searches
}

def _should_use_vector_search(file_path: Path) -> bool:
    """
    Determine if a PDF file should use vector search instead of direct upload.
    Based on file size and estimated complexity.
    """
    try:
        # Check file size - files over 10MB typically cause token issues
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 10:
            return True
        
        # For very large page counts, also use vector search
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                # If more than 50 pages, likely to hit token limits
                if page_count > 50:
                    return True
        except Exception:
            # If we can't read the PDF, be conservative and use vector search for large files
            pass
        
        return False
    except Exception:
        # If any error occurs, default to direct upload
        return False

def ensure_file_uploaded(file_path: Path, db_path: Path = Path.cwd()) -> str:
    """
    Ensure a file is uploaded to OpenAI and return the provider file ID.
    Uses the new multi-provider file system to avoid duplicate uploads.
    
    Args:
        file_path: Path to the file to upload
        db_path: Path to the database directory
        
    Returns:
        provider_file_id: The OpenAI file ID for this file
    """
    # Register file in our central registry
    file_id = register_file(file_path, db_path)
    
    # Check if this file has already been uploaded to OpenAI
    provider_file_id = get_provider_file_id(file_id, "openai", db_path)
    
    if provider_file_id:
        logging.info(f"File {file_path.name} already uploaded to OpenAI with ID {provider_file_id}")
        return provider_file_id
    
    # File hasn't been uploaded to OpenAI yet, upload it now
    logging.info(f"Uploading {file_path.name} to OpenAI for the first time")
    provider_file_id = openai_upload(file_path)
    
    # Register the upload in our database
    register_provider_upload(file_id, "openai", provider_file_id, db_path)
    
    return provider_file_id

def openai_upload(pdf_path: Path) -> str:
    """
    Upload a PDF file to OpenAI and return the file ID.
    Purpose is set to 'user_data' for general use with the new API structure.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        file_id: The ID of the uploaded file
    """
    logging.info(f"Starting OpenAI file upload for {pdf_path}")
    
    # Ensure client is available
    try:
        client = ensure_openai_client()
    except ValueError as e:
        logging.error(str(e))
        raise
    
    # Validate file exists and is readable
    if not pdf_path.exists():
        error_msg = f"File does not exist: {pdf_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Validate file is a PDF
    if pdf_path.suffix.lower() != '.pdf':
        error_msg = f"File is not a PDF: {pdf_path}"
        logging.error(error_msg)
        raise ValueError(error_msg)
        
    try:
        logging.info(f"Opening file: {pdf_path}")
        with open(pdf_path, "rb") as file_stream:
            logging.info(f"Sending file to OpenAI API: {pdf_path.name}")
            response = client.files.create(
                file=file_stream,
                purpose="user_data"  
            )
        
        if not hasattr(response, 'id'):
            error_msg = f"OpenAI API response missing file ID. Response: {response}"
            logging.error(error_msg)
            raise ValueError(error_msg)
            
        file_id = response.id
        logging.info(f"Successfully uploaded {pdf_path.name} to OpenAI with purpose 'user_data'. File ID: {file_id}")
        return file_id
    
    except openai.APIError as e:
        error_msg = f"OpenAI API Error uploading {pdf_path}: {e}"
        logging.error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Error uploading {pdf_path} to OpenAI: {e}"
        logging.error(error_msg)
        raise

def openai_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str = "gpt-4o-mini", db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Ask OpenAI a question with multimodal content (file uploads + text prompt).
    
    Args:
        file_paths: List of file paths to upload
        prompt_text: The text prompt to send
        model_name: OpenAI model to use
        db_path: Database path for file management
        web_search: Whether to enable web search
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Standard input tokens used
            - cached_input_tokens (int): Cached input tokens used
            - output_tokens (int): Output tokens used (includes reasoning tokens)
            - reasoning_tokens (int): Reasoning tokens used (for tracking, included in output_tokens)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Check if the model supports web search
    web_search_supported_models = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o3", "o4-mini"]
    if web_search and model_name not in web_search_supported_models:
        print(f"⚠️ WARNING: Model {model_name} does not support web search. Disabling web search for this request.")
        web_search = False
    
    # Separate CSV files from other files and build content
    file_ids = []
    csv_content = []
    large_pdfs = []
    
    # Always include files if they're provided - let the model decide how to use both file data and web search
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
            elif file_path.suffix.lower() == '.pdf' and _should_use_vector_search(file_path):
                # Large PDFs should use vector search instead of direct upload
                large_pdfs.append(file_path)
                print(f"🔍 Large PDF detected: {file_path.name}, will use vector search")
                logging.info(f"Large PDF detected: {file_path.name}, will use vector search")
            else:
                # Handle normal-sized files with direct upload
                try:
                    file_id = ensure_file_uploaded(file_path, db_path)
                    file_ids.append(file_id)
                except Exception as e:
                    # If direct upload fails due to size, try vector search for PDFs
                    if file_path.suffix.lower() == '.pdf' and "context_length_exceeded" in str(e).lower():
                        logging.info(f"PDF {file_path.name} too large for direct upload, falling back to vector search")
                        large_pdfs.append(file_path)
                    else:
                        raise
    
    # Build content with all non-CSV files
    content = []
    for file_id in file_ids:
        content.append({
            "type": "input_file",
            "file_id": file_id,
        })
    
    # Enhance prompt for web search if enabled and combine with CSV content
    enhanced_prompt = prompt_text
    if web_search:
        # Use OpenAI's official recommended approach for o3/o4-mini models
        if any(model in model_name.lower() for model in ["o3", "o4"]):
            # Following o3/o4-mini best practices: be direct and explicit about tool usage
            # The developer message already instructs about tool usage, so just provide the query clearly
            enhanced_prompt = prompt_text
        else:
            # For other models, add a lighter encouragement
            enhanced_prompt = f"Please use web search if needed to provide current, accurate information for this query.\n\n{prompt_text}"
    
    # Combine CSV content with prompt text
    if csv_content:
        csv_data_text = ''.join(csv_content)
        enhanced_prompt = f"{enhanced_prompt}\n\n{csv_data_text}"
    
    content.append({
        "type": "input_text",
        "text": enhanced_prompt,
    })
    
    # Set up tools for web search if enabled
    tools = []
    if web_search:
        # For o3/o4-mini models, web search is not yet supported by OpenAI
        if any(model in model_name.lower() for model in ["o3", "o4"]):
            print(f"⚠️ Web search is not yet supported for o3/o4-mini models")
            print(f"   Running '{model_name}' without web search...")
            logging.warning(f"Web search disabled for o3/o4-mini model: {model_name}")
            return openai_ask_internal(content, model_name, tools=None)
        else:
            # For other models, fall back to the preview version if still supported
            web_search_tool = {
                "type": "web_search_preview",
                "search_context_size": "medium",
            }
            print(f"🔍 Using web_search_preview tool for model: {model_name}")
            logging.info(f"Using web_search_preview tool for model: {model_name}")
        
        tools.append(web_search_tool)
        print(f"🔧 Tool configuration: {web_search_tool}")
        logging.info(f"Tool configuration: {web_search_tool}")
    
    # If we have large PDFs, use vector search instead of direct upload
    if large_pdfs:
        print(f"🚀 Using vector search for {len(large_pdfs)} large PDF(s): {[p.name for p in large_pdfs]}")
        logging.info(f"Using vector search for {len(large_pdfs)} large PDF(s): {[p.name for p in large_pdfs]}")
        return _handle_large_pdfs_with_vector_search(large_pdfs, content, enhanced_prompt, model_name, db_path, web_search)
    
    return openai_ask_internal(content, model_name, tools)

def _handle_large_pdfs_with_vector_search(large_pdfs: List[Path], existing_content: List[Dict], 
                                         prompt_text: str, model_name: str, 
                                         db_path: Path, web_search: bool) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Handle large PDFs using vector search instead of direct upload.
    """
    import time
    
    try:
        # Create a temporary vector store for these large PDFs
        vector_manager = VectorSearchManager()
        vector_store_id = vector_manager.create_vector_store(
            name=f"temp_large_pdfs_{int(time.time())}", 
            file_paths=large_pdfs,
            expires_after_days=1  # Auto-cleanup after 1 day
        )
        
        print(f"📚 Created vector store {vector_store_id} for large PDFs")
        logging.info(f"Created vector store {vector_store_id} for large PDFs")
        
        # Use the vector search to answer the question
        response = vector_manager.file_search_with_responses_api(
            vector_store_ids=[vector_store_id],
            query=prompt_text,
            model=model_name,
            max_results=20,
            include_search_results=False
        )
        
        # Return in the same format as openai_ask_internal
        answer = response.response_text
        # Estimate token usage (we don't have exact counts from responses API)
        estimated_input_tokens = len(prompt_text) // 4 + 5000  # Rough estimate including PDF content
        estimated_output_tokens = len(answer) // 4
        
        logging.info(f"Vector search completed. Answer length: {len(answer)} chars")
        
        return (
            answer,
            estimated_input_tokens,  # standard_input_tokens
            0,                       # cached_input_tokens (not available)
            estimated_output_tokens, # output_tokens
            0,                       # reasoning_tokens (not tracked in vector search)
            web_search,              # web_search_used (passed through)
            ""                       # web_search_sources (not available in vector search)
        )
        
    except Exception as e:
        logging.error(f"Vector search failed for large PDFs: {e}")
        # Return error response in expected format
        error_msg = f"Error processing large PDFs with vector search: {str(e)}"
        return (error_msg, 0, 0, 0, 0, False, "")

def openai_ask_internal(content: List[Dict], model_name: str, tools: List[Dict] = None) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Internal function to send a query to OpenAI with prepared content.
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output (includes reasoning tokens)
            - reasoning_tokens (int): Reasoning tokens used (for tracking, included in output_tokens)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Add direct console output for high visibility
    print(f"\n🔄 OPENAI API CALL STARTING - MODEL: {model_name}")
    print(f"   Content blocks: {len(content)}")
    
    # Count files in content
    file_count = sum(1 for item in content if item.get("type") == "input_file")
    text_blocks = [item for item in content if item.get("type") == "input_text"]
    prompt_preview = text_blocks[0]["text"][:50] + "..." if text_blocks else "No text"
    
    print(f"   Files: {file_count}, Prompt: '{prompt_preview}'")
    
    logging.info(f"===== OPENAI_ASK_INTERNAL FUNCTION CALLED =====")
    logging.info(f"Arguments: content_blocks={len(content)}, model_name={model_name}")
    
    try:
        import os
        import traceback
        from dotenv import load_dotenv
        
        # Reload environment variables to ensure we have the latest
        load_dotenv()
        
        # Ensure client is available
        try:
            client = ensure_openai_client()
        except ValueError as e:
            logging.error(str(e))
            raise
            
        # Log client info
        logging.info(f"OpenAI client initialized successfully")
        logging.info(f"Content blocks: {len(content)}, Model: {model_name}")

        # Format the API input for Responses API
        # For web search to work properly, we need to use a simpler input format
        if tools:  
            # Extract just the text content for web search compatibility
            text_content = ""
            for item in content:
                if item.get("type") == "input_text":
                    text_content = item.get("text", "")
                    break
            
            # For web search, we can't include files in the same request
            # This is a limitation of OpenAI's web search tool
            if any(item.get("type") == "input_file" for item in content):
                print("   ⚠️ WARNING: Files cannot be used with web search. Using text-only input.")
            
            # For o3/o4-mini models with tools, use developer message format for better tool usage
            if any(model in model_name.lower() for model in ["o3", "o4"]):
                api_input = [
                    {
                        "role": "developer",
                        "content": """You are a research assistant with access to web search tools.

Be proactive in using tools to accomplish the user's goal. Use tools when:
- The user asks for current information that might change over time
- You need to verify facts or find recent developments
- The query would benefit from up-to-date data from the web

Do NOT promise to call a function later. If a function call is required, emit it now; otherwise respond normally.

Always use the web search tool when the user's query requires current information or when your knowledge might be outdated."""
                    },
                    {
                        "role": "user",
                        "content": text_content
                    }
                ]
            else:
                api_input = text_content
        else:
            # Use the complex format for non-web-search requests
            # For o3/o4-mini models, add developer context when no tools are present
            if any(model in model_name.lower() for model in ["o3", "o4"]):
                # Add developer context for o3/o4-mini following best practices
                developer_context = {
                    "role": "developer", 
                    "content": "You are a helpful AI assistant. Analyze the provided files and information carefully. Provide accurate, comprehensive responses based on the content provided. Be thorough in your analysis and cite specific information from the files when relevant."
                }
                api_input = [
                    developer_context,
                    {
                        "role": "user", 
                        "content": content
                    }
                ]
            else:
                api_input = [
                    {
                        "role": "user",
                        "content": content
                    }
                ]
        
        logging.info(f"Preparing to make OpenAI API call with model {model_name}")
        
        try:
            # Verify openai client is properly initialized
            client_info = f"Client initialized: {client is not None}"
            logging.info(client_info)
            print(f"   OpenAI client initialized: {client is not None}")
            
            # Show model and file details
            print(f"   Model name: {model_name}")
            print(f"   Files: {file_count}")
            
            # Use the OpenAI Responses API
            logging.info("Making API call now...")
            print(f"\n⏳ INITIATING OPENAI API CALL...")
            print(f"   This may take several seconds, watching for response...")
            
            # Wrapping the actual API call with timing information
            import time
            start_time = time.time()
            print(f"   API call starting at {time.strftime('%H:%M:%S')}")
            
            # THE ACTUAL API CALL HAPPENS HERE
            try:
                response = client.responses.create(
                    model=model_name, 
                    input=api_input,
                    tools=tools
                )
            except openai.APIError as api_error:
                # Handle specific OpenAI API errors
                error_str = str(api_error).lower()
                if "web_search" in error_str or "tool" in error_str or "hosted tool" in error_str:
                    print(f"\n❌ WEB SEARCH ERROR: {api_error}")
                    print(f"   Model {model_name} doesn't support the current web search configuration")
                    print(f"   Retrying without web search...")
                    # Retry without web search tools
                    if tools:
                        # Also need to adjust the input format since we're removing tools
                        if any(model in model_name.lower() for model in ["o3", "o4"]):
                            # For o3/o4 models without tools, adjust the developer message
                            adjusted_input = [
                                {
                                    "role": "developer",
                                    "content": "You are a helpful AI assistant. Provide accurate, comprehensive responses based on your knowledge."
                                },
                                {
                                    "role": "user",
                                    "content": api_input[1]["content"] if isinstance(api_input, list) and len(api_input) > 1 else str(api_input)
                                }
                            ]
                        else:
                            adjusted_input = api_input
                        
                        response = client.responses.create(
                            model=model_name, 
                            input=adjusted_input,
                            tools=None
                        )
                        print(f"✅ Retry successful without web search")
                    else:
                        raise api_error
                elif "model" in error_str and ("not found" in error_str or "doesn't exist" in error_str):
                    raise ValueError(f"Model '{model_name}' not found or not accessible. Please check the model name and your account permissions.")
                elif "rate limit" in error_str:
                    raise ValueError(f"Rate limit exceeded for OpenAI API. Please wait before making more requests.")
                elif "authentication" in error_str or "api key" in error_str:
                    raise ValueError(f"Authentication failed. Please check your OpenAI API key.")
                else:
                    raise api_error
            except Exception as general_error:
                # Handle other types of errors (timeouts, network issues, etc.)
                error_str = str(general_error).lower()
                if "timeout" in error_str:
                    raise ValueError(f"Request timed out. The model may be taking too long to respond.")
                else:
                    raise general_error
            
            elapsed_time = time.time() - start_time
            print(f"\n✅ OPENAI API RESPONSE RECEIVED AFTER {elapsed_time:.2f} SECONDS")
            print(f"   Model: {model_name}")
            print(f"   Response received at {time.strftime('%H:%M:%S')}")
            logging.info(f"API call completed successfully in {elapsed_time:.2f} seconds!")
            logging.info(f"Response type: {type(response).__name__}")
            print(f"   Response type: {type(response).__name__}")
        except Exception as e:
            error_details = f"Error during OpenAI API call: {str(e)}"
            stack_trace = traceback.format_exc()
            logging.error(f"{error_details}\n{stack_trace}")
            
            # Print highly visible error message to console
            print(f"\n❌ OPENAI API CALL FAILED")
            print(f"   Error message: {str(e)}")
            print(f"   Model: {model_name}")
            
            # Check for common error types and provide more helpful messages
            error_str = str(e).lower()
            if "api key" in error_str or "apikey" in error_str or "authentication" in error_str:
                print(f"\n⚠️ AUTHENTICATION ERROR: This appears to be an API key problem")
                print(f"   1. Check that your OPENAI_API_KEY is correctly set in the .env file")
                print(f"   2. Verify the API key is valid and has not expired")
                print(f"   3. Make sure the API key has access to the {model_name} model")
            elif "rate limit" in error_str or "ratelimit" in error_str:
                print(f"\n⚠️ RATE LIMIT ERROR: Too many requests to OpenAI API")
                print(f"   1. You may need to wait before making more requests")
                print(f"   2. Consider using a different API key with higher limits")
            elif "model" in error_str and ("not found" in error_str or "doesn't exist" in error_str):
                print(f"\n⚠️ MODEL ERROR: The model '{model_name}' may not exist or you don't have access to it")
                print(f"   1. Check that '{model_name}' is spelled correctly")
                print(f"   2. Verify your account has access to this model")
                print(f"   3. Try using a different model like 'gpt-4' or 'gpt-3.5-turbo'")
                
            # Print stack trace summary - first 3 lines
            print(f"\n   Error traceback (first 3 lines):")
            for i, line in enumerate(stack_trace.split("\n")[:4]):
                if i > 0:  
                    print(f"   {line[:100]}..." if len(line) > 100 else f"   {line}")
                    
            raise ValueError(f"OpenAI API call failed: {str(e)}")
        
        # Initialize default values
        answer = None
        standard_input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0
        reasoning_tokens = 0
        web_search_used = False
        web_search_sources = ""

        # Extract the answer text
        try:
            # First try: direct response.output_text (preferred API pattern)
            if hasattr(response, 'output_text') and response.output_text:
                answer = response.output_text
                logging.info("Successfully extracted answer from response.output_text")
            # Second try: iterate through response.output blocks
            elif hasattr(response, 'output') and response.output:
                for block in response.output:
                    if hasattr(block, 'type') and block.type == "text" and hasattr(block, 'text'):
                        answer = block.text
                        logging.info("Successfully extracted answer from response.output blocks")
                        break
            # Third try: attempt to access as dictionary (some versions might return dict-like objects)
            elif hasattr(response, 'get') and callable(response.get):
                output_text = response.get('output_text')
                if output_text:
                    answer = output_text
                    logging.info("Successfully extracted answer using dictionary access")
            
            # If we still don't have an answer, try a more generic approach
            if not answer and hasattr(response, '__dict__'):
                logging.info(f"Response structure: {response.__dict__}")
        except Exception as e:
            logging.error(f"Error extracting answer: {str(e)}", exc_info=True)
        
        # If no answer could be extracted by any method, raise an exception
        if not answer:
            logging.error(f"Failed to extract answer from response. Response structure: {response}")
            raise ValueError("Failed to extract answer from OpenAI response. Please check API response structure.")

        # Detect web search usage by checking for web_search_call blocks
        try:
            if hasattr(response, 'output') and response.output:
                for block in response.output:
                    if hasattr(block, 'type') and block.type == "web_search_call":
                        web_search_used = True
                        logging.info(f"Web search detected: {block.id if hasattr(block, 'id') else 'unknown'}")
                        print(f"   🌐 Web search used: {block.id if hasattr(block, 'id') else 'unknown'}")
                        break
        except Exception as e:
            logging.error(f"Error detecting web search usage: {str(e)}", exc_info=True)
        
        # Extract token usage statistics
        try:
            # Log minimal response info
            logging.info(f"Response received from OpenAI API")
            if hasattr(response, 'usage'):
                logging.info(f"Usage info present in response")
                
                # Standard approach: access attributes directly
                if hasattr(response.usage, 'input_tokens'):
                    standard_input_tokens = response.usage.input_tokens or 0
                    logging.info(f"Extracted standard_input_tokens: {standard_input_tokens}")
                
                # Check for cached tokens in input_tokens_details
                if hasattr(response.usage, 'input_tokens_details'):
                    logging.info(f"input_tokens_details present: {response.usage.input_tokens_details}")
                    if hasattr(response.usage.input_tokens_details, 'cached_tokens'):
                        cached_input_tokens = response.usage.input_tokens_details.cached_tokens or 0
                        logging.info(f"Extracted cached_input_tokens: {cached_input_tokens}")
                
                # Output tokens directly from usage
                if hasattr(response.usage, 'output_tokens'):
                    output_tokens = response.usage.output_tokens or 0
                    logging.info(f"Extracted output_tokens: {output_tokens}")
                
                # CRITICAL: Extract reasoning tokens from output_tokens_details
                reasoning_tokens = 0
                if hasattr(response.usage, 'output_tokens_details'):
                    logging.info(f"output_tokens_details present: {response.usage.output_tokens_details}")
                    if hasattr(response.usage.output_tokens_details, 'reasoning_tokens'):
                        reasoning_tokens = response.usage.output_tokens_details.reasoning_tokens or 0
                        logging.info(f"Extracted reasoning_tokens: {reasoning_tokens}")
                
                # Log comprehensive token breakdown
                logging.info(f"OpenAI token breakdown:")
                logging.info(f"  - Input tokens: {standard_input_tokens}")
                logging.info(f"  - Cached tokens: {cached_input_tokens}")
                logging.info(f"  - Output tokens: {output_tokens}")
                logging.info(f"  - Reasoning tokens: {reasoning_tokens}")
                
                # Check if we have total_tokens for verification
                total_from_api = getattr(response.usage, 'total_tokens', None)
                calculated_total = standard_input_tokens + cached_input_tokens + output_tokens
                
                if total_from_api and abs(calculated_total - total_from_api) > 5:
                    logging.warning(f"Token calculation mismatch: calculated {calculated_total} vs API total {total_from_api}")
                    print(f"   ⚠️ Token calculation mismatch: {calculated_total} vs {total_from_api}")
                
                # Print detailed token breakdown
                print(f"   📊 OpenAI token details:")
                print(f"       Input: {standard_input_tokens}, Cached: {cached_input_tokens}")
                print(f"       Output: {output_tokens}")
                if reasoning_tokens > 0:
                    print(f"       Reasoning: {reasoning_tokens} (included in output)")
                if total_from_api:
                    print(f"       API Total: {total_from_api}")
                
                # If no tokens found via direct access, this is an API structure issue
                if standard_input_tokens == 0 and output_tokens == 0:
                    raise ValueError(f"OpenAI API response missing expected token usage fields. Response structure may have changed.")
                    
            else:
                raise ValueError(f"OpenAI API response missing usage metadata. Cannot determine token counts.")
            
            # Ensure all token counts are valid integers
            standard_input_tokens = int(standard_input_tokens) if standard_input_tokens is not None else 0
            cached_input_tokens = int(cached_input_tokens) if cached_input_tokens is not None else 0
            output_tokens = int(output_tokens) if output_tokens is not None else 0
            reasoning_tokens = int(reasoning_tokens) if reasoning_tokens is not None else 0
            
            if standard_input_tokens == 0 and output_tokens == 0:
                raise ValueError(f"All token counts are zero. This indicates an API response parsing issue.")
            
            logging.info(f"Final token counts - Input: {standard_input_tokens}, Cached: {cached_input_tokens}, Output: {output_tokens}, Reasoning: {reasoning_tokens}")
        except Exception as e:
            logging.error(f"Error extracting token usage: {str(e)}", exc_info=True)
            raise Exception(f"Failed to extract token usage from OpenAI response: {str(e)}") from e

        # Print prominent results for high visibility in the console
        print(f"\n💬 ANSWER FROM {model_name.upper()}:")
        print(f"   '{str(answer)[:150]}...'" if len(str(answer)) > 150 else f"   '{str(answer)}'")
        print(f"   Tokens - Input: {standard_input_tokens}, Cached: {cached_input_tokens}, Output: {output_tokens}")
        print(f"=================================================")
        
        logging.info(f"Received answer (truncated): '{str(answer)[:100]}...'")

        # Extract web search sources
        if web_search_used:
            web_search_sources = ""
            for block in response.output:
                if hasattr(block, 'type') and block.type == "web_search_call":
                    web_search_sources += f"Web search call ID: {block.id if hasattr(block, 'id') else 'unknown'}\n"
                    for message_block in response.output:
                        if hasattr(message_block, 'type') and message_block.type == "message" and hasattr(message_block, 'content'):
                            for content_block in message_block.content:
                                if hasattr(content_block, 'type') and content_block.type == "output_text" and hasattr(content_block, 'text'):
                                    web_search_sources += f"Web search result: {content_block.text}\n"
                                    break
        
        return answer, standard_input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, web_search_used, web_search_sources
            
    except openai.APIError as e:
        logging.error(f"OpenAI API Error: {str(e)}", exc_info=True)
        raise Exception(f"OpenAI API Error: {str(e)}") from e
    except Exception as e:
        logging.error(f"Error in openai_ask_internal: {str(e)}", exc_info=True)
        raise Exception(f"Error in openai_ask_internal: {str(e)}") from e

def calculate_cost(
    model_name: str,
    standard_input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    search_queries: int = 0,
    search_context: str = "medium"
) -> Dict[str, Any]:
    """
    Calculate the cost of using an OpenAI model.
    
    Args:
        model_name: The model to use (e.g., "gpt-4o", "gpt-4o-mini")
        standard_input_tokens: Number of standard input tokens
        cached_input_tokens: Number of cached input tokens
        output_tokens: Number of output tokens (includes reasoning tokens for OpenAI)
        reasoning_tokens: Number of reasoning tokens (for tracking, but included in output_tokens)
        search_queries: Number of web search queries
        search_context: Search context size ("low", "medium", "high")
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name not in COSTS:
        return {"error": f"Model {model_name} not found in cost database"}
    
    model_costs = COSTS[model_name]
    
    # Calculate token costs (prices are per 1M tokens, so divide by 1,000,000)
    input_cost = (standard_input_tokens * model_costs["input"]) / 1_000_000
    cached_cost = (cached_input_tokens * model_costs["cached"]) / 1_000_000
    output_cost = (output_tokens * model_costs["output"]) / 1_000_000
    
    # Calculate search costs if applicable
    search_cost = 0
    if search_queries > 0 and "search_cost" in model_costs:
        search_cost = search_queries * model_costs["search_cost"]
    
    total_cost = input_cost + cached_cost + output_cost + search_cost
    
    return {
        "model": model_name,
        "input_cost": round(input_cost, 6),
        "cached_cost": round(cached_cost, 6),
        "output_cost": round(output_cost, 6),
        "search_cost": round(search_cost, 6),
        "total_cost": round(total_cost, 6),
        "tokens": {
            "standard_input": standard_input_tokens,
            "cached_input": cached_input_tokens,
            "output": output_tokens,
            "reasoning": reasoning_tokens,
            "total": standard_input_tokens + cached_input_tokens + output_tokens
        }
    }

def count_tokens_openai(content: List[Dict], model_name: str) -> int:
    """
    OpenAI token counting for multimodal content (files + text).
    
    IMPORTANT: OpenAI does not provide a pre-request token counting API for multimodal content.
    Token counts can only be obtained AFTER the response via usage metadata.
    
    This function raises an exception to indicate that pre-request token counting
    is not available, but actual token counts will be captured after the response.
    
    Args:
        content: List of content blocks (text and files)
        model_name: OpenAI model name
        
    Returns:
        This function will raise an exception for multimodal content
        
    Raises:
        Exception: Always raised to indicate limitation
    """
    # Check if we have any files in the content
    has_files = any(item.get("type") in ["input_file", "file"] for item in content)
    
    if has_files:
        # OpenAI doesn't support pre-request token counting for files
        # But actual tokens will be counted after response completion
        raise Exception(
            f"OpenAI does not support pre-request token counting for multimodal content. "
            f"Actual token counts will be available after response completion via usage metadata. "
            f"This is a known limitation of the OpenAI API."
        )
    
    # For text-only content, we can use tiktoken
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model_name)
        
        total_tokens = 0
        for item in content:
            if item.get("type") == "input_text":
                text = item.get("text", "")
                total_tokens += len(enc.encode(text))
        
        logging.info(f"OpenAI text-only token count for {model_name}: {total_tokens}")
        return total_tokens
        
    except Exception as e:
        logging.error(f"Error counting text tokens for OpenAI model {model_name}: {e}")
        raise Exception(f"Text-only token counting failed for OpenAI model {model_name}: {e}") from e

def get_context_limit_openai(model_name: str) -> int:
    """
    Get the context window limit for an OpenAI model.
    
    Args:
        model_name: OpenAI model name
        
    Returns:
        Context window size in tokens
    """
    model_lower = model_name.lower()
    
    if any(x in model_lower for x in ["gpt-4.1", "gpt-4-1"]):
        return 1047576  # GPT 4.1 series (excluding nano which is deprecated)
    elif any(x in model_lower for x in ["gpt-4o", "gpt-4-o"]):
        return 128000   # GPT 4o series
    elif any(x in model_lower for x in ["o3", "o4"]):
        return 200000   # o3/o4 series
    else:
        raise ValueError(f"Unknown OpenAI model: {model_name}. Cannot determine context limit.")


# ===== VECTOR SEARCH INTEGRATION =====

def openai_ask_with_vector_search(vector_store_ids: List[str], prompt_text: str, 
                                 model_name: str = "gpt-4o-mini", 
                                 max_results: int = 20,
                                 include_search_results: bool = False,
                                 filters: Dict[str, Any] = None) -> Tuple[str, int, int, int, int, bool, str, List[Dict[str, Any]]]:
    """
    Ask OpenAI using vector search over knowledge bases.
    
    Args:
        vector_store_ids: List of vector store IDs to search
        prompt_text: The question/prompt
        model_name: OpenAI model to use
        max_results: Maximum number of search results
        include_search_results: Whether to include raw search results
        filters: Optional metadata filters
        
    Returns:
        Tuple of (answer, standard_input_tokens, cached_input_tokens, output_tokens, 
                 reasoning_tokens, file_search_used, search_sources, citations)
    """
    try:
        print(f"\n🔍 VECTOR SEARCH WITH {model_name.upper()}:")
        print(f"   Vector stores: {vector_store_ids}")
        print(f"   Query: '{prompt_text[:100]}...'" if len(prompt_text) > 100 else f"   Query: '{prompt_text}'")
        print(f"   Max results: {max_results}")
        
        # Initialize vector search manager
        vector_manager = VectorSearchManager()
        
        # Enhance prompt for o3/o4-mini models following best practices
        enhanced_query = prompt_text
        if any(model in model_name.lower() for model in ["o3", "o4"]):
            enhanced_query = f"""You are a research assistant with access to document search capabilities.

Use the file search tool to find relevant information from the provided documents. Base your response on the documents found and cite specific sources.

Do NOT promise to search documents later. If document search is needed, use it now; otherwise respond with available knowledge.

User query: {prompt_text}"""
        
        # Perform vector search with responses API
        search_response = vector_manager.file_search_with_responses_api(
            vector_store_ids=vector_store_ids,
            query=enhanced_query,
            model=model_name,
            max_results=max_results,
            include_search_results=include_search_results,
            filters=filters
        )
        
        # Extract response details
        answer = search_response.response_text
        citations = search_response.citations
        search_results = search_response.search_results
        
        # Format search sources
        search_sources = f"Search call ID: {search_response.search_call_id}\n"
        if citations:
            search_sources += f"Citations: {len(citations)} file citations found\n"
            for i, citation in enumerate(citations):
                if hasattr(citation, 'file_id') and hasattr(citation, 'filename'):
                    search_sources += f"  {i+1}. {citation.filename} (ID: {citation.file_id})\n"
        
        # For now, we can't get exact token counts from the Responses API
        # This is a limitation we need to handle
        print(f"   ⚠️ Note: Token counting not available with Responses API file search")
        print(f"   Response length: {len(answer)} characters")
        print(f"   Citations found: {len(citations)}")
        
        # Use proper tokenization for OpenAI models
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model_name)
            estimated_output_tokens = len(encoding.encode(answer))
            estimated_input_tokens = len(encoding.encode(prompt_text))
        except Exception as e:
            logging.warning(f"Could not get exact token count using tiktoken: {e}")
            # Only fall back to estimation if tiktoken fails
            estimated_output_tokens = len(answer) // 4
            estimated_input_tokens = len(prompt_text) // 4
        
        print(f"\n💬 VECTOR SEARCH ANSWER FROM {model_name.upper()}:")
        print(f"   '{answer[:150]}...'" if len(answer) > 150 else f"   '{answer}'")
        print(f"   Estimated tokens - Input: {estimated_input_tokens}, Output: {estimated_output_tokens}")
        print(f"   Citations: {len(citations)}")
        print(f"=================================================")
        
        # Return in the same format as other OpenAI functions
        # Note: Token counts are estimates since Responses API doesn't provide exact counts
        return (
            answer,
            estimated_input_tokens,  # standard_input_tokens (estimated)
            0,  # cached_input_tokens (not available)
            estimated_output_tokens,  # output_tokens (estimated)
            0,  # reasoning_tokens (not available)
            True,  # file_search_used
            search_sources,  # search_sources
            citations  # citations (additional return value)
        )
        
    except Exception as e:
        logging.error(f"Error in vector search: {str(e)}", exc_info=True)
        raise Exception(f"Vector search failed: {str(e)}") from e


def create_vector_store_from_files(name: str, file_paths: List[Path], 
                                  description: str = None,
                                  expires_after_days: int = None,
                                  db_path: Path = Path.cwd()) -> str:
    """
    Create a vector store and upload files to it.
    
    Args:
        name: Name for the vector store
        file_paths: List of files to upload
        description: Optional description
        expires_after_days: Optional expiration in days
        db_path: Database path for local tracking
        
    Returns:
        Vector store ID
    """
    try:
        from file_store import register_vector_store, register_vector_store_file
        
        print(f"\n📚 CREATING VECTOR STORE: {name}")
        print(f"   Files to upload: {len(file_paths)}")
        
        # Initialize vector search manager
        vector_manager = VectorSearchManager()
        
        # Create vector store with files
        vector_store_id = vector_manager.create_vector_store(
            name=name,
            file_paths=file_paths,
            expires_after_days=expires_after_days
        )
        
        # Register in local database
        register_vector_store(
            vector_store_id=vector_store_id,
            name=name,
            description=description,
            expires_at=None,  # Will be set by OpenAI if expires_after_days was specified
            db_path=db_path
        )
        
        # Register each file in the vector store
        for file_path in file_paths:
            try:
                # Get local file ID
                from file_store import register_file, get_provider_file_id
                local_file_id = register_file(file_path, db_path)
                provider_file_id = get_provider_file_id(local_file_id, "openai", db_path)
                
                if provider_file_id:
                    register_vector_store_file(
                        vector_store_id=vector_store_id,
                        file_id=local_file_id,
                        provider_file_id=provider_file_id,
                        db_path=db_path
                    )
            except Exception as e:
                logging.warning(f"Could not register file {file_path.name} in local database: {e}")
        
        print(f"   ✅ Vector store created: {vector_store_id}")
        return vector_store_id
        
    except Exception as e:
        logging.error(f"Error creating vector store: {str(e)}", exc_info=True)
        raise Exception(f"Failed to create vector store: {str(e)}") from e


def search_vector_store_direct(vector_store_id: str, query: str, 
                              max_results: int = 10,
                              filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Search a vector store directly (without response generation).
    
    Args:
        vector_store_id: Vector store ID to search
        query: Search query
        max_results: Maximum results to return
        filters: Optional metadata filters
        
    Returns:
        List of search results
    """
    try:
        print(f"\n🔍 DIRECT VECTOR SEARCH:")
        print(f"   Vector store: {vector_store_id}")
        print(f"   Query: '{query[:100]}...'" if len(query) > 100 else f"   Query: '{query}'")
        
        # Initialize vector search manager
        vector_manager = VectorSearchManager()
        
        # Perform direct search
        results = vector_manager.search_vector_store(
            vector_store_id=vector_store_id,
            query=query,
            max_results=max_results,
            filters=filters
        )
        
        print(f"   Results found: {len(results)}")
        
        # Convert to dictionary format for consistency
        search_results = []
        for result in results:
            search_results.append({
                "file_id": result.file_id,
                "filename": result.filename,
                "score": result.score,
                "content": result.content,
                "attributes": result.attributes
            })
        
        return search_results
        
    except Exception as e:
        logging.error(f"Error in direct vector search: {str(e)}", exc_info=True)
        raise Exception(f"Direct vector search failed: {str(e)}") from e
