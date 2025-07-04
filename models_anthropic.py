from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
import logging
from dotenv import load_dotenv
import anthropic
from file_store import register_file, get_provider_file_id, register_provider_upload
import time
import traceback

# Load environment variables from .env file
load_dotenv()

# Get API key from environment - but don't fail if missing
api_key = os.environ.get("ANTHROPIC_API_KEY")

# Only initialize client if API key is available
client = None
if api_key:
    # Configure Anthropic client with beta features for file support
    client = anthropic.Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "files-api-2025-04-14"}
    )
else:
    print("[Anthropic] No API key found - will initialize when key is provided")

def ensure_anthropic_client():
    """Ensure Anthropic client is initialized with current API key"""
    global client, api_key
    current_api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not current_api_key:
        raise ValueError("Anthropic API key not found. Please configure it in Settings.")
    
    # Re-initialize client if API key has changed
    if current_api_key != api_key:
        api_key = current_api_key
        client = anthropic.Anthropic(
            api_key=api_key,
            default_headers={"anthropic-beta": "files-api-2025-04-14"}
        )
        print("[Anthropic] Client initialized with new API key")
    elif not client:
        client = anthropic.Anthropic(
            api_key=current_api_key,
            default_headers={"anthropic-beta": "files-api-2025-04-14"}
        )
        print("[Anthropic] Client initialized")
    
    return client

AVAILABLE_MODELS = [
    "claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet-20250219-thinking",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-20250514-thinking",
    "claude-opus-4-20250514",
    "claude-opus-4-20250514-thinking",
    "claude-3-5-haiku-20241022"
]

COSTS = {
    "claude-opus-4-20250514": {
        "input": 15.00,
        "cached_write": 18.75,
        "cached_read": 1.50,
        "output": 75.00
    },
    "claude-opus-4-20250514-thinking": {
        "input": 15.00,
        "cached_write": 18.75,
        "cached_read": 1.50,
        "output": 75.00
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "cached_write": 3.75,
        "cached_read": 0.30,
        "output": 15.00
    },
    "claude-sonnet-4-20250514-thinking": {
        "input": 3.00,
        "cached_write": 3.75,
        "cached_read": 0.30,
        "output": 15.00
    },
    "claude-3-7-sonnet-20250219": {
        "input": 3.00,
        "cached_write": 3.75,
        "cached_read": 0.30,
        "output": 15.00
    },
    "claude-3-7-sonnet-20250219-thinking": {
        "input": 3.00,
        "cached_write": 3.75,
        "cached_read": 0.30,
        "output": 15.00
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "cached_write": 1.00,
        "cached_read": 0.08,
        "output": 4.00
    }
}

WEB_SEARCH_COST = 10.00  # $10 per 1K searches

def ensure_file_uploaded(file_path: Path, db_path: Path = Path.cwd()) -> str:
    """
    Ensure a file is uploaded to Anthropic and return the provider file ID.
    Uses the new multi-provider file system to avoid duplicate uploads.
    
    Args:
        file_path: Path to the file to upload
        db_path: Path to the database directory
        
    Returns:
        provider_file_id: The Anthropic file ID for this file
    """
    # Register file in our central registry
    file_id = register_file(file_path, db_path)
    
    # Check if this file has already been uploaded to Anthropic
    provider_file_id = get_provider_file_id(file_id, "anthropic", db_path)
    
    if provider_file_id:
        logging.info(f"File {file_path.name} already uploaded to Anthropic with ID {provider_file_id}")
        return provider_file_id
    
    # File hasn't been uploaded to Anthropic yet, upload it now
    logging.info(f"Uploading {file_path.name} to Anthropic for the first time")
    provider_file_id = anthropic_upload(file_path)
    
    # Register the upload in our database
    register_provider_upload(file_id, "anthropic", provider_file_id, db_path)
    
    return provider_file_id

def anthropic_upload(pdf_path: Path) -> str:
    """
    Upload a PDF file to Anthropic and return the file ID.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        file_id: The ID of the uploaded file
    """
    logging.info(f"Starting Anthropic file upload for {pdf_path}")
    
    # Ensure client is available
    try:
        client = ensure_anthropic_client()
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
            logging.info(f"Sending file to Anthropic API: {pdf_path.name}")
            response = client.beta.files.upload(
                file=(pdf_path.name, file_stream, "application/pdf")
            )
        
        if not hasattr(response, 'id'):
            error_msg = f"Anthropic API response missing file ID. Response: {response}"
            logging.error(error_msg)
            raise ValueError(error_msg)
            
        file_id = response.id
        logging.info(f"Successfully uploaded {pdf_path.name} to Anthropic. File ID: {file_id}")
        return file_id
    
    except anthropic.APIError as e:
        error_msg = f"Anthropic API Error uploading {pdf_path}: {e}"
        logging.error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Error uploading {pdf_path} to Anthropic: {e}"
        logging.error(error_msg)
        raise

def is_thinking_model(model_name: str) -> bool:
    """Check if this is a thinking variant of a model."""
    return model_name.endswith("-thinking")

def get_base_model_name(model_name: str) -> str:
    """Get the base model name (without -thinking suffix)."""
    if is_thinking_model(model_name):
        return model_name.replace("-thinking", "")
    return model_name

def anthropic_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str = "claude-3-5-haiku-20241022", db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Send a query to Anthropic with multiple file attachments using intelligent token budget management.
    
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
    # Ensure client is available
    try:
        anthropic_client = ensure_anthropic_client()
    except ValueError as e:
        logging.error(str(e))
        raise
    
    # Use intelligent token budget management for file processing
    try:
        from anthropic_token_manager import AnthropicTokenManager
        
        # Initialize token manager
        token_manager = AnthropicTokenManager(model_name, anthropic_client, db_path=db_path)
        
        # Create execution plan
        plan = token_manager.plan_request(file_paths, prompt_text, web_search)
        
        # Log plan details
        logging.info(f"Token management plan: {plan.strategy}")
        logging.info(f"Files to include: {len(plan.files_to_include)}")
        logging.info(f"Estimated tokens: {plan.estimated_total_tokens}")
        
        if plan.warnings:
            for warning in plan.warnings:
                logging.warning(f"Token manager: {warning}")
                print(f"   ⚠️  {warning}")
        
        # Execute plan to get content
        content = token_manager.execute_plan(plan, db_path)
        
        # Add prompt text
        content.append({
            "type": "text",
            "text": prompt_text
        })
        
        # Proceed with API call using managed content
        return anthropic_ask_internal(content, model_name, web_search, db_path)
        
    except ImportError:
        # Fallback to simple processing if token manager not available
        logging.warning("Token manager not available, falling back to simple file processing")
        return anthropic_ask_with_files_simple(file_paths, prompt_text, model_name, db_path, web_search)
    except Exception as e:
        logging.error(f"Token manager failed: {e}, falling back to simple processing")
        return anthropic_ask_with_files_simple(file_paths, prompt_text, model_name, db_path, web_search)

def anthropic_ask_with_files_simple(file_paths: List[Path], prompt_text: str, model_name: str = "claude-3-5-haiku-20241022", db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Simple fallback version of file processing without intelligent token management.
    """
    # Build content parts list
    content = []
    
    # Separate CSV files from other files
    csv_content = []
    
    # Always include files if they're provided - let the model decide how to use both file data and web search
    if file_paths:
        # Add files using the Files API (upload and reference by file_id)
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
                # Handle PDF and other files normally
                try:
                    # Upload file and get file_id
                    file_id = ensure_file_uploaded(file_path, db_path)
                    
                    # Add document reference using file_id
                    content.append({
                        "type": "document",
                        "source": {
                            "type": "file",
                            "file_id": file_id
                        }
                    })
                    logging.info(f"Added {file_path.name} using Files API with file_id: {file_id}")
                except Exception as e:
                    logging.error(f"Error uploading file {file_path}: {e}")
                    raise Exception(f"Failed to upload file {file_path}: {e}")
    
    # Combine CSV content with prompt text
    enhanced_prompt = prompt_text
    if csv_content:
        csv_data_text = ''.join(csv_content)
        enhanced_prompt = f"{prompt_text}\n\n{csv_data_text}"
    
    # Add prompt text
    content.append({
        "type": "text",
        "text": enhanced_prompt
    })
    
    return anthropic_ask_internal(content, model_name, web_search, db_path)

def anthropic_ask_internal(content: List[Dict], model_name: str, web_search: bool = False, db_path: Path = Path.cwd()) -> Tuple[str, int, int, int, int, bool, str]:
    """
    Internal function to send a query to Anthropic with prepared content.
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output
            - thinking_tokens (int): Thinking tokens used (for tracking, included in output_tokens)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Detect if this is a thinking model
    thinking_enabled = is_thinking_model(model_name)
    base_model_name = get_base_model_name(model_name)
    
    # Add direct console output for high visibility
    print(f"\n🔄 ANTHROPIC API CALL STARTING - MODEL: {model_name}")
    if thinking_enabled:
        print(f"   🧠 Thinking enabled (base model: {base_model_name})")
    
    # Count files in content
    file_count = sum(1 for item in content if item.get("type") in ["file", "document"])
    text_blocks = [item for item in content if item.get("type") == "text"]
    prompt_preview = text_blocks[0]["text"][:50] + "..." if text_blocks else "No text"
    
    print(f"   Files: {file_count}, Prompt: '{prompt_preview}'")
    if web_search:
        print("   Web search enabled")
    
    logging.info(f"===== ANTHROPIC_ASK_INTERNAL FUNCTION CALLED =====")
    logging.info(f"Arguments: content_blocks={len(content)}, model_name={model_name}, thinking_enabled={thinking_enabled}, web_search={web_search}")
    
    try:
        import os
        import traceback
        from dotenv import load_dotenv
        
        # Reload environment variables to ensure we have the latest
        load_dotenv()
        
        # Ensure client is available
        try:
            client = ensure_anthropic_client()
        except ValueError as e:
            logging.error(str(e))
            raise
        
        # Create the messages structure
        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        
        # Set up tools for web search if enabled
        tools = []
        if web_search:
            tools = [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 1
            }]
        
        # Estimate token count for input using the proper token counting function
        try:
            input_token_count = count_tokens_anthropic(content, model_name, db_path)
            logging.info(f"Estimated input tokens: {input_token_count}")
            
            # Check if we're approaching context limits
            if input_token_count > 190000:  # 200k - 10k buffer
                logging.warning(f"High token count detected: {input_token_count} tokens (approaching 200k limit)")
                print(f"   ⚠️  High token usage: {input_token_count} tokens (limit: 200k)")
                
        except Exception as e:
            logging.error(f"Token counting failed: {e}")
            # Re-raise the error - we don't want to continue with unknown token counts
            # as this could lead to failed API calls
            raise Exception(f"Cannot estimate token count for Anthropic request: {e}") from e
        
        # Track request start time for performance monitoring
        start_time = time.time()
        
        # Send message to Anthropic
        try:
            # Prepare API call parameters (use base model name for API)
            api_params = {
                "model": base_model_name,  # Use base model name for API call
                "max_tokens": 8000,
                "temperature": 1.0 if thinking_enabled else 0.2,  # Anthropic requires temperature=1 for thinking
                "messages": messages
            }
            
            # Add thinking configuration if thinking is enabled
            if thinking_enabled:
                api_params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": 4000
                }

            # Only add tools if web search is enabled
            if web_search and tools:
                api_params["tools"] = tools
            
            response = client.messages.create(**api_params)
            
            # Extract text response from Claude - DON'T manually count thinking tokens
            answer = ""
            web_search_used = False
            web_search_queries = 0
            web_search_sources = ""
            
            # Track thinking for informational purposes only (not for billing)
            thinking_content_found = False
            summarized_thinking_chars = 0
            
            if hasattr(response, 'content') and response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text') and content_block.text:
                        answer += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'text':
                        answer += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'thinking':
                        # Found thinking content - this is summarized for Claude 4, full for Claude 3.7
                        thinking_content_found = True
                        thinking_text = getattr(content_block, 'thinking', '')
                        if thinking_text:
                            summarized_thinking_chars += len(thinking_text)
                            logging.info(f"Found thinking block with {len(thinking_text)} characters (summarized for Claude 4, full for Claude 3.7)")
                    elif hasattr(content_block, 'type') and content_block.type == 'redacted_thinking':
                        # Found redacted thinking content
                        thinking_content_found = True
                        logging.info(f"Found redacted thinking block (encrypted for safety)")
                    elif hasattr(content_block, 'type') and content_block.type == 'tool_use':
                        # Check if this is a web search tool use
                        if hasattr(content_block, 'name') and 'web_search' in content_block.name:
                            web_search_used = True
                            web_search_queries += 1
                    elif hasattr(content_block, 'type') and content_block.type == 'web_search_tool_result':
                        # Extract web search results
                        web_search_used = True
                        web_search_sources += f"Web search tool result: {str(content_block)}\n"
                        if hasattr(content_block, 'content'):
                            for result in content_block.content:
                                if hasattr(result, 'url'):
                                    web_search_sources += f"URL: {result.url}\n"
                                if hasattr(result, 'title'):
                                    web_search_sources += f"Title: {result.title}\n"
                                if hasattr(result, 'cited_text'):
                                    web_search_sources += f"Cited text: {result.cited_text}\n"
                                web_search_sources += "---\n"
            
            # Also check if web search was used by looking for citations or search indicators in the text
            if web_search and answer and not web_search_used:
                # Look for common web search indicators in the response
                search_indicators = ['http', 'www.', 'source:', 'according to', 'based on recent', 'search results']
                if any(indicator in answer.lower() for indicator in search_indicators):
                    web_search_used = True
                    web_search_queries = 1  # Assume 1 search query
            
            # Final fallback: if we have web search sources but web_search_used is still False, set it to True
            if web_search and web_search_sources and not web_search_used:
                web_search_used = True
                web_search_queries = 1
                logging.info("Web search sources detected but web_search_used was False - correcting this")
            
            if web_search_used:
                logging.info(f"Web search detected: {web_search_queries} queries")
                print(f"   🌐 Web search used: {web_search_queries} queries")
                print(f"   📊 Anthropic includes web search tokens in standard counts")
            
            # Extract token usage - demand exact counts from API
            usage = getattr(response, 'usage', None)
            if not usage:
                raise Exception("Anthropic API response missing usage data. Cannot proceed without exact token counts.")
            
            input_tokens = getattr(usage, 'input_tokens', None)
            output_tokens = getattr(usage, 'output_tokens', None)
            
            if input_tokens is None or output_tokens is None:
                raise Exception("Anthropic API response missing input_tokens or output_tokens. Cannot proceed with token estimates.")
            
            # Get thinking tokens from API response if available
            thinking_tokens_estimated = 0
            if thinking_enabled:
                # Check if API provides thinking token count directly
                thinking_tokens_from_api = getattr(usage, 'cache_creation_input_tokens', None)  # Some models report this
                if thinking_tokens_from_api:
                    thinking_tokens_estimated = thinking_tokens_from_api
                    logging.info(f"Thinking tokens from API: {thinking_tokens_estimated}")
                else:
                    logging.warning(f"Thinking model used but API didn't provide thinking token count. Cannot estimate accurately.")
                    # Note: For billing purposes, thinking tokens are included in output_tokens for some models
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            print(f"\n✅ ANTHROPIC API RESPONSE RECEIVED AFTER {elapsed_time:.2f} SECONDS")
            print(f"   Model: {model_name}")
            print(f"   Tokens - Input: {input_tokens}, Output: {output_tokens}")
            if thinking_enabled and thinking_content_found:
                print(f"   🧠 Thinking content found: {summarized_thinking_chars} chars visible")
                print(f"   🧠 Estimated thinking tokens: {thinking_tokens_estimated}")
                print(f"   💰 Note: Output tokens include FULL thinking tokens (billed), not just summarized content")
            elif thinking_enabled:
                print(f"   🧠 Thinking enabled but no thinking content detected")
            
            # Return the results with estimated thinking tokens
            return answer, input_tokens, 0, output_tokens, thinking_tokens_estimated, web_search_used, web_search_sources
            
        except Exception as e:
            error_details = traceback.format_exc()
            logging.error(f"Anthropic API Error: {e}\n{error_details}")
            
            # Check for token limit errors and provide more readable message
            error_str = str(e).lower()
            if "token" in error_str and ("limit" in error_str or "exceed" in error_str or "context" in error_str):
                return f"ERROR: Token limit exceeded. The input is too large for {model_name}.", input_token_count, 0, 0, 0, False, ""
            
            return f"ERROR: {str(e)}", input_token_count, 0, 0, 0, False, ""

    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Error during Anthropic call process: {e}\n{error_details}")
        
        print(f"\n❌ ANTHROPIC CALL PROCESS FAILED (General Exception)")
        print(f"   Error message: {str(e)}")
        print(f"   Model: {model_name}")
        
        error_str = str(e).lower()
        if "api key" in error_str or "apikey" in error_str or "authentication" in error_str:
            print(f"\n⚠️ AUTHENTICATION ERROR: This appears to be an API key problem")
            print(f"   1. Check that your ANTHROPIC_API_KEY is correctly set in the .env file")
            print(f"   2. Verify the API key is valid and has not expired")
            print(f"   3. Make sure the API key has access to the {model_name} model")
        elif "rate limit" in error_str or "ratelimit" in error_str:
            print(f"\n⚠️ RATE LIMIT ERROR: Too many requests to Anthropic API")
            print(f"   1. You may need to wait before making more requests")
            print(f"   2. Consider using a different API key with higher limits")
        elif "model" in error_str and ("not found" in error_str or "doesn't exist" in error_str):
            print(f"\n⚠️ MODEL ERROR: The model '{model_name}' may not exist or you don't have access to it")
            print(f"   1. Check that '{model_name}' is spelled correctly")
            print(f"   2. Verify your account has access to this model")
            print(f"   3. Try using a different model like 'claude-3-5-haiku-20241022'")
            
        print(f"\n   Error traceback (first 3 lines):")
        for i, line in enumerate(error_details.split("\n")[:4]):
            if i > 0: 
                print(f"   {line[:100]}..." if len(line) > 100 else f"   {line}")
                
        # Ensure we return something, even if it's just default error values
        # The function expects a tuple of (str, int, int, int, bool, str)
        # If an error occurs before 'answer' is set, it will be None.
        # Token counts will be their default (0) if not set.
        # The caller (runner.py) handles exceptions from this function and logs them.
        # We re-raise the exception so it propagates.
        raise Exception(f"Error in anthropic_ask_internal: {str(e)}") from e

    # This block is reached if the main try block completes without an unhandled exception
    # Print prominent results for high visibility in the console
    print(f"\n💬 ANSWER FROM {model_name.upper()}:")
    answer_str = str(answer) if answer is not None else "No answer received"
    print(f"   '{answer_str[:150]}...'" if len(answer_str) > 150 else f"   '{answer_str}'")
    print(f"   Tokens - Input: {input_tokens}, Output: {output_tokens}")
    print(f"=================================================")
    
    logging.info(f"Received answer (truncated): '{answer_str[:100]}...'")
    return (answer if answer is not None else f"ERROR: No answer extracted but no direct API error."), \
           input_tokens, 0, output_tokens, 0, web_search_used, web_search_sources

def calculate_cost(
    model_name: str,
    standard_input_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    search_queries: int = 0
) -> Dict[str, Any]:
    """
    Calculate the cost of using an Anthropic model.
    
    Args:
        model_name: The model to use (e.g., "claude-sonnet-4-20250514")
        standard_input_tokens: Number of standard input tokens
        cache_write_tokens: Number of tokens written to cache
        cache_read_tokens: Number of tokens read from cache
        output_tokens: Number of output tokens (includes thinking tokens for Anthropic)
        thinking_tokens: Number of thinking tokens (for tracking, but included in output_tokens)
        search_queries: Number of web search queries
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name not in COSTS:
        return {"error": f"Model {model_name} not found in cost database"}
    
    model_costs = COSTS[model_name]
    
    # Calculate token costs (prices are per 1M tokens, so divide by 1,000,000)
    input_cost = (standard_input_tokens * model_costs["input"]) / 1_000_000
    cache_write_cost = (cache_write_tokens * model_costs["cached_write"]) / 1_000_000
    cache_read_cost = (cache_read_tokens * model_costs["cached_read"]) / 1_000_000
    output_cost = (output_tokens * model_costs["output"]) / 1_000_000
    
    # Calculate search costs if applicable
    search_cost = 0
    if search_queries > 0:
        search_cost = (search_queries * WEB_SEARCH_COST) / 1_000
    
    total_cost = input_cost + cache_write_cost + cache_read_cost + output_cost + search_cost
    
    return {
        "model": model_name,
        "input_cost": round(input_cost, 6),
        "cache_write_cost": round(cache_write_cost, 6),
        "cache_read_cost": round(cache_read_cost, 6),
        "output_cost": round(output_cost, 6),
        "search_cost": round(search_cost, 6),
        "total_cost": round(total_cost, 6),
        "tokens": {
            "standard_input": standard_input_tokens,
            "cache_write": cache_write_tokens,
            "cache_read": cache_read_tokens,
            "output": output_tokens,
            "thinking": thinking_tokens,
            "total": standard_input_tokens + cache_write_tokens + cache_read_tokens + output_tokens
        }
    }

def get_pdf_page_count(file_path: Path) -> int:
    """Get the number of pages in a PDF"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except Exception as e:
        logging.warning(f"Could not determine page count for {file_path}: {e}")
        return 0

def check_pdf_page_limit(file_paths: List[Path]) -> int:
    """Check total pages across all PDF files"""
    total_pages = 0
    for file_path in file_paths:
        if file_path.suffix.lower() == '.pdf':
            page_count = get_pdf_page_count(file_path)
            total_pages += page_count
            logging.info(f"PDF {file_path.name}: {page_count} pages")
    return total_pages

def count_tokens_anthropic(content: List[Dict], model_name: str, db_path: Path = Path.cwd()) -> int:
    """
    Count tokens for Anthropic models using their count_tokens API.
    Note: Anthropic's token counting API does NOT support file sources, only base64.
    Handles the 100-page PDF limit by reporting chunked token estimate.
    
    Args:
        content: List of content blocks (text and documents)
        model_name: Anthropic model name (may include -thinking suffix)
        
    Returns:
        Actual token count from Anthropic's API
    """
    try:
        # Ensure client is available
        client = ensure_anthropic_client()
        
        # Handle thinking models
        thinking_enabled = is_thinking_model(model_name)
        base_model_name = get_base_model_name(model_name)
        
        # Extract text and files from content for page limit checking
        text_content = []
        file_paths = []
        
        for item in content:
            if item.get("type") == "text":
                text_content.append(item.get("text", ""))
            elif item.get("type") == "file":
                file_path = item.get("file_path")
                if file_path:
                    file_paths.append(Path(file_path))
        
        # Check if files would exceed 100-page limit
        if file_paths:
            total_pages = check_pdf_page_limit(file_paths)
            logging.info(f"Total PDF pages: {total_pages}")
            
            # If we exceed 100 pages, we cannot count tokens accurately without chunking
            if total_pages > 100:
                logging.error(f"PDF pages ({total_pages}) exceed Anthropic's 100-page limit. Token counting not possible without chunking.")
                raise Exception(f"Cannot count tokens for {total_pages} pages. Anthropic limit is 100 pages per request. Please use chunking logic instead of token counting.")
        
        # Convert content to Anthropic format for token counting (original logic)
        anthropic_content = []
        
        for item in content:
            if item.get("type") == "text":
                anthropic_content.append({
                    "type": "text",
                    "text": item.get("text", "")
                })
            elif item.get("type") == "document":
                source = item.get("source", {})
                if source.get("type") == "base64":
                    # Document with base64 source - already in correct format
                    anthropic_content.append(item)
                elif source.get("type") == "file":
                    # Document with file source - need to convert to base64 for token counting
                    file_id = source.get("file_id")
                    if file_id:
                        # Get file path from provider file ID
                        from file_store import get_file_path_from_provider_id
                        file_path = get_file_path_from_provider_id(file_id, "anthropic", db_path)
                        if file_path and Path(file_path).exists():
                            # Read file and encode as base64 for token counting
                            import base64
                            with open(file_path, "rb") as f:
                                pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
                            
                            anthropic_content.append({
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            })
                        else:
                            raise FileNotFoundError(f"Cannot find file path for provider file ID: {file_id}")
                    else:
                        raise ValueError("Document with file source missing file_id")
                else:
                    raise ValueError(f"Unsupported document source type: {source.get('type')}")
            elif item.get("type") == "file":
                # For token counting, we MUST use base64 (file sources not supported)
                file_path = item.get("file_path")
                if file_path:
                    file_path_obj = Path(file_path)
                    if file_path_obj.exists():
                        # Read file and encode as base64 for token counting
                        import base64
                        with open(file_path_obj, "rb") as f:
                            pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
                        
                        anthropic_content.append({
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64
                            }
                        })
                    else:
                        raise FileNotFoundError(f"File not found: {file_path}")
                elif item.get("id"):
                    # File ID provided but we can't use it for token counting
                    # We need the original file path to read and encode as base64
                    raise ValueError("Token counting requires file_path, not just file_id. Anthropic's count_tokens API doesn't support file sources.")
                else:
                    raise ValueError("File content missing file_path")
            else:
                raise ValueError(f"Unsupported content type: {item.get('type')}")
        
        if not anthropic_content:
            return 0
            
        # Use Anthropic's count_tokens API with base64 content
        token_count_params = {
            "model": base_model_name,  # Use base model name for API call
            "messages": [{
                "role": "user",
                "content": anthropic_content
            }]
        }
        
        # Add thinking configuration if thinking is enabled
        if thinking_enabled:
            token_count_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": 4096  # Match API call budget
            }
            logging.info(f"Token counting with thinking enabled for {model_name}")
        
        response = client.messages.count_tokens(**token_count_params)
        
        logging.info(f"Anthropic token count for {model_name}: {response.input_tokens}")
        return response.input_tokens
        
    except Exception as e:
        logging.error(f"Error counting tokens for Anthropic model {model_name}: {e}")
        # DO NOT FALLBACK - fail fast instead
        raise Exception(f"Token counting failed for Anthropic model {model_name}: {e}") from e

def get_context_limit_anthropic(model_name: str) -> int:
    """
    Get the context window limit for an Anthropic model.
    
    Args:
        model_name: Anthropic model name
        
    Returns:
        Context window size in tokens
    """
    # All Claude models currently have 200K token context windows
    return 200000

