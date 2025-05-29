from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
import logging
from dotenv import load_dotenv
import openai
from file_store import register_file, get_provider_file_id, register_provider_upload
import tiktoken

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

"""web search
Web search
Allow models to search the web for the latest information before generating a response.
Using the Responses API, you can enable web search by configuring it in the tools array in an API request to generate content. Like any other tool, the model can choose to search the web or not based on the content of the input prompt.

Web search tool example
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4.1",
    tools=[{"type": "web_search_preview"}],
    input="What was a positive news story from today?"
)

print(response.output_text)
Web search tool versions
You can also force the use of the web_search_preview tool by using the tool_choice parameter, and setting it to {type: "web_search_preview"} - this can help ensure lower latency and more consistent results.

Output and citations
Model responses that use the web search tool will include two parts:

A web_search_call output item with the ID of the search call.
A message output item containing:
The text result in message.content[0].text
Annotations message.content[0].annotations for the cited URLs
By default, the model's response will include inline citations for URLs found in the web search results. In addition to this, the url_citation annotation object will contain the URL, title and location of the cited source.

When displaying web results or information contained in web results to end users, inline citations must be made clearly visible and clickable in your user interface.

[
  {
    "type": "web_search_call",
    "id": "ws_67c9fa0502748190b7dd390736892e100be649c1a5ff9609",
    "status": "completed"
  },
  {
    "id": "msg_67c9fa077e288190af08fdffda2e34f20be649c1a5ff9609",
    "type": "message",
    "status": "completed",
    "role": "assistant",
    "content": [
      {
        "type": "output_text",
        "text": "On March 6, 2025, several news...",
        "annotations": [
          {
            "type": "url_citation",
            "start_index": 2606,
            "end_index": 2758,
            "url": "https://...",
            "title": "Title..."
          }
        ]
      }
    ]
  }
]

Search context size
When using this tool, the search_context_size parameter controls how much context is retrieved from the web to help the tool formulate a response. The tokens used by the search tool do not affect the context window of the main model specified in the model parameter in your response creation request. These tokens are also not carried over from one turn to another — they're simply used to formulate the tool response and then discarded.

Choosing a context size impacts:

Cost: Pricing of our search tool varies based on the value of this parameter. Higher context sizes are more expensive. See tool pricing here.
Quality: Higher search context sizes generally provide richer context, resulting in more accurate, comprehensive answers.
Latency: Higher context sizes require processing more tokens, which can slow down the tool's response time.
Available values:

high: Most comprehensive context, highest cost, slower response.
medium (default): Balanced context, cost, and latency.
low: Least context, lowest cost, fastest response, but potentially lower answer quality.
Again, tokens used by the search tool do not impact main model's token usage and are not carried over from turn to turn. Check the pricing page for details on costs associated with each context size.

Customizing search context size
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4.1",
    tools=[{
        "type": "web_search_preview",
        "search_context_size": "low",
    }],
    input="What movie won best picture in 2025?",
)

print(response.output_text)"""

"""openai context windows

GPT 4.1 and 4.1-mini
1,047,576 context window

GPT 4o and 4o-mini
128,000 context window

o3 and o4-mini
200,000 context window

token counting with tiktoken

>>> import tiktoken
>>> encoding = tiktoken.get_encoding("o200k_base")
>>> tokens = encoding.encode("asdfasdfasdfasdfasdfasdfasdfasdf")
>>> tokens
[178858, 178858, 178858, 178858, 178858, 178858, 178858, 178858]
>>> num_tokens = len(tokens)
>>> num_tokens
8
"""

"""gpt 4o pricing
Model	Input	Cached input	Output
gpt-4o
gpt-4o-2024-08-06
$2.50
$1.25
$10.00"""

"""gpt 4o-mini pricing
Model	Input	Cached input	Output
gpt-4o-mini
gpt-4o-mini-2024-07-18
$0.15
$0.075
$0.60"""

"""gpt 4.1 pricing
Model	Input	Cached input	Output
gpt-4.1
gpt-4.1-2025-04-14
$2.00
$0.50
$8.00"""

"""gpt 4.1 mini pricing
Model	Input	Cached input	Output
gpt-4.1-mini
gpt-4.1-mini-2025-04-14
$0.40
$0.10
$1.60"""

"""o3 pricing
Model	Input	Cached input	Output
o3
o3-2025-04-16
$10.00
$2.50
$40.00"""

"""o4 mini pricing
Model	Input	Cached input	Output
o4-mini
o4-mini-2025-04-16
$1.10
$0.275
$4.40"""


"""tools pricing

Built-in tools
The tokens used for built-in tools are billed at the chosen model's per-token rates.
GB refers to binary gigabytes of storage (also known as gibibyte), where 1GB is 2^30 bytes.

Tool	Cost
Code Interpreter
$0.03
container
File Search Storage
$0.10
GB/day (1GB free)
File Search Tool Call (Responses API only*)
$2.50
1k calls (*Does not apply on Assistants API)
Web Search
Web search tool pricing is inclusive of tokens used to synthesize information
from the web. Pricing depends on model and search context size. See below."""


"""Web search pricing
Web search is a built-in tool with pricing that depends on both the model used and the search context size. The billing dashboard will report these line items as 'web search tool calls | gpt-4o' and 'web search tool calls | gpt-4o-mini'.

Model	Search context size	Cost
gpt-4.1, gpt-4o, or gpt-4o-search-preview
low
$30.00
1k calls
medium (default)
$35.00
1k calls
high
$50.00
1k calls
gpt-4.1-mini, gpt-4o-mini, or gpt-4o-mini-search-preview
low
$25.00
1k calls
medium (default)
$27.50
1k calls
high
$30.00
1k calls
"""



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


"""openai model response structure

USE THIS TO GET THE STRUCTURE OF THE RESPONSE FROM THE OPENAI API

FOCUS ON OUTPUT TEXT, TOKEN USAGE, AND THE RESPONSE STRUCTURE

{
  "id": "resp_67ccd3a9da748190baa7f1570fe91ac604becb25c45c1d41",
  "object": "response",
  "created_at": 1741476777,
  "status": "completed",
  "error": null,
  "incomplete_details": null,
  "instructions": null,
  "max_output_tokens": null,
  "model": "gpt-4o-2024-08-06",
  "output": [
    {
      "type": "message",
      "id": "msg_67ccd3acc8d48190a77525dc6de64b4104becb25c45c1d41",
      "status": "completed",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "The image depicts a scenic landscape with a wooden boardwalk or pathway leading through lush, green grass under a blue sky with some clouds. The setting suggests a peaceful natural area, possibly a park or nature reserve. There are trees and shrubs in the background.",
          "annotations": []
        }
      ]
    }
  ],
  "parallel_tool_calls": true,
  "previous_response_id": null,
  "reasoning": {
    "effort": null,
    "summary": null
  },
  "store": true,
  "temperature": 1,
  "text": {
    "format": {
      "type": "text"
    }
  },
  "tool_choice": "auto",
  "tools": [],
  "top_p": 1,
  "truncation": "disabled",
  "usage": {
    "input_tokens": 328,
    "input_tokens_details": {
      "cached_tokens": 0
    },
    "output_tokens": 52,
    "output_tokens_details": {
      "reasoning_tokens": 0
    },
    "total_tokens": 380
  },
  "user": null,
  "metadata": {}
}"""

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
                purpose="user_data"  # Changed from "assistants"
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
    web_search_supported_models = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"]
    if web_search and model_name not in web_search_supported_models:
        print(f"⚠️ WARNING: Model {model_name} does not support web search. Disabling web search for this request.")
        web_search = False
    
    # Separate CSV files from other files and build content
    file_ids = []
    csv_content = []
    
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
            else:
                # Handle PDF and other files normally
                file_id = ensure_file_uploaded(file_path, db_path)
                file_ids.append(file_id)
    
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
            # Straightforward prompt as recommended by OpenAI - avoid complex instructions
            enhanced_prompt = f"Search for the latest information about {prompt_text}. Provide current data and sources."
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
        tools.append({
            "type": "web_search_preview",
            "search_context_size": "medium",  # Default to medium context size
        })
    
    return openai_ask_internal(content, model_name, tools)

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
        if tools:  # If web search is enabled, use simpler format
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
            
            api_input = text_content
        else:
            # Use the complex format for non-web-search requests
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
                if "web_search" in error_str or "tool" in error_str:
                    print(f"\n❌ WEB SEARCH ERROR: {api_error}")
                    print(f"   Model {model_name} may not support web search or the tool configuration is invalid")
                    print(f"   Retrying without web search...")
                    # Retry without web search tools
                    if tools:
                        response = client.responses.create(
                            model=model_name, 
                            input=api_input,
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
                if i > 0:  # Skip the first line which just says 'Traceback'
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
