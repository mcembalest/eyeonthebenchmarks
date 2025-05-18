from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import os
import logging
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set. Please check your .env file.")

# Configure OpenAI client
client = openai.OpenAI(api_key=api_key)

# Import cost calculator
from cost_calculator import calculate_cost, calculate_image_cost

AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-image-1"
]

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
    
    # Validate API key first
    if not api_key:
        error_msg = "OPENAI_API_KEY environment variable not set. Cannot upload file."
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

def estimate_cost(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    search_queries: int = 0,
    images: int = 0,
    image_size: str = "1024x1024",
    image_quality: str = "standard"
) -> Dict[str, Any]:
    """
    Estimate the cost of using this model.
    
    Args:
        model_name: The model to use
        input_tokens: Number of input tokens (for text models)
        output_tokens: Number of output tokens (for text models)
        search_queries: Number of web search queries
        images: Number of images to generate (for image models)
        image_size: Size of generated images (for image models)
        image_quality: Quality of generated images
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name.startswith('gpt-image'):
        # For image generation
        return calculate_cost(
            model_name=model_name,
            standard_input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            search_queries=0,
            image_generation={
                'model': model_name,
                'count': images,
                'size': image_size,
                'quality': image_quality
            } if images > 0 else None
        )
    else:
        # For text generation
        return calculate_cost(
            model_name=model_name,
            standard_input_tokens=input_tokens,
            cached_input_tokens=0,  # OpenAI doesn't report cached tokens separately
            output_tokens=output_tokens,
            search_queries=search_queries
        )


def openai_ask(file_id: str, prompt_text: str, model_name: str = "gpt-4o-mini") -> Tuple[str, int, int, int]:
    """
    Send a query to an OpenAI model with a file attachment.
    
    Args:
        file_id: ID of the uploaded file (obtained via openai_upload).
        prompt_text: The question to ask the model.
        model_name: The model to use (e.g., "gpt-4o-mini", "gpt-4o").
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response.
            - standard_input_tokens (int): Tokens used in the input.
            - cached_input_tokens (int): Always 0 for OpenAI (not separately reported).
            - output_tokens (int): Tokens used in the output.
    """
    # Add direct console output for high visibility
    print(f"\n🔄 OPENAI API CALL STARTING - MODEL: {model_name}")
    print(f"   Prompt: '{prompt_text[:50]}...'")
    print(f"   File ID: {file_id}")
    
    logging.info(f"===== OPENAI_ASK FUNCTION CALLED =====")
    logging.info(f"Arguments: file_id={file_id}, model_name={model_name}")
    logging.info(f"Prompt text (first 100 chars): {prompt_text[:100]}...")
    
    try:
        import os
        import traceback
        from dotenv import load_dotenv
        
        # Reload environment variables to ensure we have the latest
        load_dotenv()
        
        # Check API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            error_msg = "OPENAI_API_KEY environment variable is not set"
            logging.error(error_msg)
            raise ValueError(error_msg)
            
        # Log key info without revealing sensitive data
        key_info = f"Length: {len(api_key)}, First 3 chars: {api_key[:3]}, Last 3 chars: {api_key[-3:]}"
        logging.info(f"API Key verified: {key_info}")
        logging.info(f"File ID: {file_id}, Model: {model_name}")

        # Format the API input for Responses API
        api_input = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file_id,
                    },
                    {
                        "type": "input_text",
                        "text": prompt_text,
                    },
                ]
            }
        ]
        
        logging.info(f"Preparing to make OpenAI API call with model {model_name}")
        
        try:
            # Verify openai client is properly initialized
            client_info = f"Client initialized: {client is not None}"
            logging.info(client_info)
            print(f"   OpenAI client initialized: {client is not None}")
            
            # Check OpenAI API key first few and last few characters
            if api_key:
                key_preview = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
                print(f"   API Key found: {key_preview} (length: {len(api_key)})")
            else:
                print(f"   ⚠️ WARNING: No API key found! API call will fail.")
                
            # Show model and file details
            print(f"   Model name: {model_name}")
            print(f"   File ID: {file_id}")
            print(f"   Request details: 1 message, {len(prompt_text)} chars in prompt")
            
            # Use the OpenAI Responses API
            logging.info("Making API call now...")
            print(f"\n⏳ INITIATING OPENAI API CALL...")
            print(f"   This may take several seconds, watching for response...")
            
            # Wrapping the actual API call with timing information
            import time
            start_time = time.time()
            print(f"   API call starting at {time.strftime('%H:%M:%S')}")
            
            # THE ACTUAL API CALL HAPPENS HERE
            response = client.responses.create(
                model=model_name, 
                input=api_input
            )
            
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
            print(f"   File ID: {file_id}")
            
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
                
                # Fall back to dictionary-style access if attributes aren't found
                if standard_input_tokens == 0 and hasattr(response.usage, 'get') and callable(response.usage.get):
                    standard_input_tokens = response.usage.get('input_tokens', 0) or 0
                    output_tokens = response.usage.get('output_tokens', 0) or 0
                    logging.info(f"Used dictionary access for token counts: input={standard_input_tokens}, output={output_tokens}")
                    
                # Additional fallback for new API version structure
                if standard_input_tokens == 0 and hasattr(response.usage, '__dict__'):
                    usage_dict = response.usage.__dict__
                    logging.info(f"Usage dictionary: {usage_dict}")
                    if 'prompt_tokens' in usage_dict:  # Legacy field name
                        standard_input_tokens = usage_dict.get('prompt_tokens', 0) or 0
                        logging.info(f"Extracted prompt_tokens from dict: {standard_input_tokens}")
                    if 'completion_tokens' in usage_dict:  # Legacy field name
                        output_tokens = usage_dict.get('completion_tokens', 0) or 0
                        logging.info(f"Extracted completion_tokens from dict: {output_tokens}")
                    if 'total_tokens' in usage_dict and standard_input_tokens == 0 and output_tokens == 0:
                        # If we only have total tokens, assume split of 75% input, 25% output
                        total = usage_dict.get('total_tokens', 0) or 0
                        standard_input_tokens = int(total * 0.75)
                        output_tokens = total - standard_input_tokens
                        logging.info(f"Estimated from total_tokens: input={standard_input_tokens}, output={output_tokens}")
            else:
                # Try to extract token info from the entire response if no usage field
                if hasattr(response, '__dict__'):
                    resp_dict = response.__dict__
                    logging.info(f"Response dictionary keys: {resp_dict.keys()}")
                    # Look for any field that might contain token counts
                    for key in resp_dict.keys():
                        if 'token' in key.lower() or 'usage' in key.lower():
                            logging.info(f"Potential token info field: {key} = {resp_dict[key]}")
                            
                # Last resort: try to estimate tokens from answer length
                if standard_input_tokens == 0 and output_tokens == 0 and answer:
                    # Very rough estimation - about 4 chars per token for English text
                    output_tokens = max(1, int(len(answer) / 4))
                    logging.info(f"Estimated output tokens from answer length: {output_tokens}")
                    # We have no way to estimate input tokens without the prompt text
            
            # Ensure all token counts are valid integers
            standard_input_tokens = int(standard_input_tokens) if standard_input_tokens is not None else 0
            cached_input_tokens = int(cached_input_tokens) if cached_input_tokens is not None else 0
            output_tokens = int(output_tokens) if output_tokens is not None else 0
            
            logging.info(f"Final token counts - Standard Input: {standard_input_tokens}, Cached Input: {cached_input_tokens}, Output: {output_tokens}")
        except Exception as e:
            logging.error(f"Error extracting token usage: {str(e)}", exc_info=True)
            # Continue with default values (0) on error, but log the exception

        # Print prominent results for high visibility in the console
        print(f"\n💬 ANSWER FROM {model_name.upper()}:")
        print(f"   '{str(answer)[:150]}...'" if len(str(answer)) > 150 else f"   '{str(answer)}'")
        print(f"   Tokens - Input: {standard_input_tokens}, Cached: {cached_input_tokens}, Output: {output_tokens}")
        print(f"=================================================")
        
        logging.info(f"Received answer (truncated): '{str(answer)[:100]}...'")
        return answer, standard_input_tokens, cached_input_tokens, output_tokens
            
    except openai.APIError as e:
        logging.error(f"OpenAI API Error: {str(e)}", exc_info=True)
        raise Exception(f"OpenAI API Error: {str(e)}") from e
    except Exception as e:
        logging.error(f"Error in openai_ask: {str(e)}", exc_info=True)
        raise Exception(f"Error in openai_ask: {str(e)}") from e
