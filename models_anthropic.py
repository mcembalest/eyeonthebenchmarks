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

# Get API key from environment
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set. Please check your .env file.")

# Configure Anthropic client with beta features for file support
client = anthropic.Anthropic(
    api_key=api_key,
    default_headers={"anthropic-beta": "files-api-2025-04-14"}
)

AVAILABLE_MODELS = [
    "claude-3-7-sonnet-20250219",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-5-haiku-20241022"
]

COSTS = {
    "claude-opus-4-20250514": {
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
    "claude-3-7-sonnet-20250219": {
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

"""web search

response = client.messages.create(
    model="claude-3-7-sonnet-latest",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "How do I update a web app to TypeScript 5.5?"
        }
    ],
    tools=[{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5
    }]
)
print(response)

Here's an example response structure:


Copy
{
  "role": "assistant",
  "content": [
    // 1. Claude's decision to search
    {
      "type": "text",
      "text": "I'll search for when Claude Shannon was born."
    },
    // 2. The search query used
    {
      "type": "server_tool_use",
      "id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "name": "web_search",
      "input": {
        "query": "claude shannon birth date"
      }
    },
    // 3. Search results
    {
      "type": "web_search_tool_result",
      "tool_use_id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "content": [
        {
          "type": "web_search_result",
          "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
          "title": "Claude Shannon - Wikipedia",
          "encrypted_content": "EqgfCioIARgBIiQ3YTAwMjY1Mi1mZjM5LTQ1NGUtODgxNC1kNjNjNTk1ZWI3Y...",
          "page_age": "April 30, 2025"
        }
      ]
    },
    {
      "text": "Based on the search results, ",
      "type": "text"
    },
    // 4. Claude's response with citations
    {
      "text": "Claude Shannon was born on April 30, 1916, in Petoskey, Michigan",
      "type": "text",
      "citations": [
        {
          "type": "web_search_result_location",
          "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
          "title": "Claude Shannon - Wikipedia",
          "encrypted_index": "Eo8BCioIAhgBIiQyYjQ0OWJmZi1lNm..",
          "cited_text": "Claude Elwood Shannon (April 30, 1916 – February 24, 2001) was an American mathematician, electrical engineer, computer scientist, cryptographer and i..."
        }
      ]
    }
  ],
  "id": "msg_a930390d3a",
  "usage": {
    "input_tokens": 6039,
    "output_tokens": 931,
    "server_tool_use": {
      "web_search_requests": 1
    }
  },
  "stop_reason": "end_turn"
}
​
Search results
Search results include:

url: The URL of the source page
title: The title of the source page
page_age: When the site was last updated
encrypted_content: Encrypted content that must be passed back in multi-turn conversations for citations
​
Citations
Citations are always enabled for web search, and each web_search_result_location includes:

url: The URL of the cited source
title: The title of the cited source
encrypted_index: A reference that must be passed back for multi-turn conversations.
cited_text: Up to 150 characters of the cited content
The web search citation fields cited_text, title, and url do not count towards input or output token usage.

When displaying web results or information contained in web results to end users, inline citations must be made clearly visible and clickable in your user interface.

​
Errors
If an error occurs during web search, you'll receive a response that takes the following form:


Copy
{
  "type": "web_search_tool_result",
  "tool_use_id": "servertoolu_a93jad",
  "content": {
    "type": "web_search_tool_result_error",
    "error_code": "max_uses_exceeded"
  }
}"""

"""todo token counting

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    system="You are a scientist",
    messages=[{
        "role": "user",
        "content": "Hello, Claude"
    }],
)

print(response.json())


How to count message tokens
The token counting endpoint accepts the same structured list of inputs for creating a message, including support for system prompts, tools, images, and PDFs. The response contains the total number of input tokens.

The token count should be considered an estimate. In some cases, the actual number of input tokens used when creating a message may differ by a small amount.

​
Supported models
The token counting endpoint supports the following models:

Claude Opus 4
Claude Sonnet 4
Claude Sonnet 3.7
Claude Sonnet 3.5
Claude Haiku 3.5
Claude Haiku 3
Claude Opus 3
​
Count tokens in basic messages

Python

TypeScript

Shell

Java

Copy
import anthropic

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    system="You are a scientist",
    messages=[{
        "role": "user",
        "content": "Hello, Claude"
    }],
)

print(response.json())
JSON

Copy
{ "input_tokens": 14 }
​
Count tokens in messages with tools
Server tool token counts only apply to the first sampling call.


Python

TypeScript

Shell

Java

Copy
import anthropic

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    tools=[
        {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    }
                },
                "required": ["location"],
            },
        }
    ],
    messages=[{"role": "user", "content": "What's the weather like in San Francisco?"}]
)

print(response.json())
JSON

Copy
{ "input_tokens": 403 }
​
Count tokens in messages with images

Shell

Python

TypeScript

Java

Copy
import anthropic
import base64
import httpx

image_url = "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
image_media_type = "image/jpeg"
image_data = base64.standard_b64encode(httpx.get(image_url).content).decode("utf-8")

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "Describe this image"
                }
            ],
        }
    ],
)
print(response.json())
JSON

Copy
{ "input_tokens": 1551 }
​
Count tokens in messages with extended thinking
See here for more details about how the context window is calculated with extended thinking

Thinking blocks from previous assistant turns are ignored and do not count toward your input tokens
Current assistant turn thinking does count toward your input tokens

Shell

Python

TypeScript

Java

Copy
import anthropic

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    thinking={
        "type": "enabled",
        "budget_tokens": 16000
    },
    messages=[
        {
            "role": "user",
            "content": "Are there an infinite number of prime numbers such that n mod 4 == 3?"
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "This is a nice number theory question. Let's think about it step by step...",
                    "signature": "EuYBCkQYAiJAgCs1le6/Pol5Z4/JMomVOouGrWdhYNsH3ukzUECbB6iWrSQtsQuRHJID6lWV..."
                },
                {
                  "type": "text",
                  "text": "Yes, there are infinitely many prime numbers p such that p mod 4 = 3..."
                }
            ]
        },
        {
            "role": "user",
            "content": "Can you write a formal proof?"
        }
    ]
)

print(response.json())
JSON

Copy
{ "input_tokens": 88 }
​
Count tokens in messages with PDFs
Token counting supports PDFs with the same limitations as the Messages API.


Shell

Python

TypeScript

Java

Copy
import base64
import anthropic

client = anthropic.Anthropic()

with open("document.pdf", "rb") as pdf_file:
    pdf_base64 = base64.standard_b64encode(pdf_file.read()).decode("utf-8")

response = client.messages.count_tokens(
    model="claude-opus-4-20250514",
    messages=[{
        "role": "user",
        "content": [
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
                "text": "Please summarize this document."
            }
        ]
    }]
)

print(response.json())
JSON

Copy
{ "input_tokens": 2188 }"""

"""Claude context windows

All claude models have input context window of 200K tokens

we need to use the anthropic count_tokens() function to get token counts before launching a benchmark and getting model response objects
"""

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
    
    # Validate API key first
    if not api_key:
        error_msg = "ANTHROPIC_API_KEY environment variable not set. Cannot upload file."
        logging.error(error_msg)
        raise ValueError(error_msg)
    
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

def anthropic_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str = "claude-3-5-haiku-20241022", db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, bool, str]:
    """
    Send a query to an Anthropic Claude model with multiple file attachments.
    
    Args:
        file_paths: List of paths to files to include
        prompt_text: The question to ask the model
        model_name: The model to use (e.g., "claude-3-5-haiku-20241022")
        db_path: Path to the database directory
        web_search: Whether to enable web search for this prompt
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Build content with all files and prompt
    content = []
    
    # Add files
    for file_path in file_paths:
        file_id = ensure_file_uploaded(file_path, db_path)
        content.append({
            "type": "file",
            "id": file_id
        })
    
    # Add prompt text
    content.append({
        "type": "text",
        "text": prompt_text
    })
    
    return anthropic_ask_internal(content, model_name, web_search)

def anthropic_ask_internal(content: List[Dict], model_name: str, web_search: bool = False) -> Tuple[str, int, int, int, bool, str]:
    """
    Internal function to send a query to Anthropic with prepared content.
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Add direct console output for high visibility
    print(f"\n🔄 ANTHROPIC API CALL STARTING - MODEL: {model_name}")
    
    # Count files in content
    file_count = sum(1 for item in content if item.get("type") == "file")
    text_blocks = [item for item in content if item.get("type") == "text"]
    prompt_preview = text_blocks[0]["text"][:50] + "..." if text_blocks else "No text"
    
    print(f"   Files: {file_count}, Prompt: '{prompt_preview}'")
    if web_search:
        print("   Web search enabled")
    
    logging.info(f"===== ANTHROPIC_ASK_INTERNAL FUNCTION CALLED =====")
    logging.info(f"Arguments: content_blocks={len(content)}, model_name={model_name}, web_search={web_search}")
    
    try:
        import os
        import traceback
        from dotenv import load_dotenv
        
        # Reload environment variables to ensure we have the latest
        load_dotenv()
        
        # Check API key
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            error_msg = "ANTHROPIC_API_KEY environment variable is not set"
            logging.error(error_msg)
            raise ValueError(error_msg)
            
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
                "max_uses": 5
            }]
        
        # Estimate token count for input
        try:
            token_count_response = client.messages.count_tokens(
                model=model_name,
                messages=messages
            )
            input_token_count = token_count_response.input_tokens
            logging.info(f"Estimated input tokens: {input_token_count}")
        except Exception as e:
            logging.warning(f"Could not count tokens: {e}")
            # Rough token count estimation based on text length and file count
            input_token_count = 0
            for item in content:
                if item.get("type") == "text":
                    # Rough estimate: ~1 token per 4 characters
                    input_token_count += len(item.get("text", "")) // 4
                elif item.get("type") == "file":
                    # For files, we'll need to estimate since we can't count tokens
                    # for uploaded files without making the actual API call
                    # Use file size as rough estimate: ~1 token per 4 bytes
                    input_token_count += 1000  # Assume 1000 tokens per file as a base estimate
            
            logging.info(f"Roughly estimated input tokens: {input_token_count}")
        
        # Track request start time for performance monitoring
        start_time = time.time()
        
        # Send message to Anthropic
        try:
            # Prepare API call parameters
            api_params = {
                "model": model_name,
                "max_tokens": 2048,
                "temperature": 0.2,
                "messages": messages
            }
            
            # Only add tools if web search is enabled
            if web_search and tools:
                api_params["tools"] = tools
            
            response = client.messages.create(**api_params)
            
            # Extract text response from Claude
            answer = ""
            web_search_used = False
            web_search_queries = 0
            web_search_sources = ""
            
            if hasattr(response, 'content') and response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text') and content_block.text:
                        answer += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'text':
                        answer += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'tool_use':
                        # Check if this is a web search tool use
                        if hasattr(content_block, 'name') and 'web_search' in content_block.name:
                            web_search_used = True
                            web_search_queries += 1
                    elif hasattr(content_block, 'type') and content_block.type == 'web_search_tool_result':
                        # Extract web search results
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
            
            if web_search_used:
                logging.info(f"Web search detected: {web_search_queries} queries")
                print(f"   🌐 Web search used: {web_search_queries} queries")
                print(f"   📊 Anthropic includes web search tokens in standard counts")
            
            # Extract token usage
            usage = getattr(response, 'usage', {})
            input_tokens = getattr(usage, 'input_tokens', input_token_count)
            output_tokens = getattr(usage, 'output_tokens', len(answer) // 4)  # Rough estimate if not available
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            print(f"\n✅ ANTHROPIC API RESPONSE RECEIVED AFTER {elapsed_time:.2f} SECONDS")
            print(f"   Model: {model_name}")
            print(f"   Tokens - Input: {input_tokens}, Output: {output_tokens}")
            
            # Return the results
            return answer, input_tokens, 0, output_tokens, web_search_used, web_search_sources
            
        except Exception as e:
            error_details = traceback.format_exc()
            logging.error(f"Anthropic API Error: {e}\n{error_details}")
            
            # Check for token limit errors and provide more readable message
            error_str = str(e).lower()
            if "token" in error_str and ("limit" in error_str or "exceed" in error_str or "context" in error_str):
                return f"ERROR: Token limit exceeded. The input is too large for {model_name}.", input_token_count, 0, 0, False, ""
            
            return f"ERROR: {str(e)}", input_token_count, 0, 0, False, ""

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
           input_tokens, 0, output_tokens, web_search_used, web_search_sources

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

def count_tokens_anthropic(content: List[Dict], model_name: str) -> int:
    """
    Count tokens for Anthropic models using their count_tokens API.
    
    Args:
        content: List of content blocks (text and documents)
        model_name: Anthropic model name
        
    Returns:
        Estimated token count
    """
    try:
        # Convert content to Anthropic format for token counting
        anthropic_content = []
        
        for item in content:
            if item.get("type") == "text":
                anthropic_content.append({
                    "type": "text",
                    "text": item.get("text", "")
                })
            elif item.get("type") == "file":
                # For files, we'll need to estimate since we can't count tokens
                # for uploaded files without making the actual API call
                # Use file size as rough estimate: ~1 token per 4 bytes
                file_path = Path(item.get("file_path", ""))
                if file_path.exists():
                    file_size_bytes = file_path.stat().st_size
                    estimated_tokens = file_size_bytes // 4
                    # Add to a text block for counting purposes
                    anthropic_content.append({
                        "type": "text", 
                        "text": "x" * estimated_tokens  # Placeholder text for token estimation
                    })
        
        if not anthropic_content:
            return 0
            
        # Use Anthropic's count_tokens API
        response = client.messages.count_tokens(
            model=model_name,
            messages=[{
                "role": "user",
                "content": anthropic_content
            }]
        )
        
        return response.input_tokens
        
    except Exception as e:
        logging.warning(f"Error counting tokens for Anthropic model {model_name}: {e}")
        # Return a conservative high estimate if we can't count properly
        return 150000

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

