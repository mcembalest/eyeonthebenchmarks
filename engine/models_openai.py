from pathlib import Path
import os
from dotenv import load_dotenv
import openai
# from time import sleep # No longer needed for polling

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set. Please check your .env file.")

# Configure OpenAI client
client = openai.OpenAI(api_key=api_key)

AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",         # User specified; verify actual OpenAI model ID if issues arise
    "gpt-4.1-mini",    # User specified; verify actual OpenAI model ID
    "gpt-4.1-nano",    # User specified; verify actual OpenAI model ID
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
    try:
        with open(pdf_path, "rb") as file_stream:
            response = client.files.create(
                file=file_stream,
                purpose="user_data"  # Changed from "assistants"
            )
        
        file_id = response.id
        print(f"Successfully uploaded {pdf_path.name} to OpenAI with purpose 'user_data'. File ID: {file_id}")
        return file_id
    
    except Exception as e:
        print(f"Error uploading {pdf_path} to OpenAI: {e}")
        raise

def openai_ask(file_id: str, prompt_text: str, model_name="gpt-4o-mini") -> tuple[str, int, int, int]:
    """
    
    Args:
        file_id: ID of the uploaded file (obtained via openai_upload).
        prompt_text: The question to ask the model.
        model_name: The model to use (e.g., "gpt-4o-mini", "gpt-4o").
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response.
            - standard_input_tokens (int): Tokens used in the input (non-cached portion).
            - cached_input_tokens (int): Tokens used in the input (cached portion).
            - output_tokens (int): Tokens used in the output.
    """
    try:
        print(f"Asking model {model_name} about file {file_id} with prompt: '{prompt_text[:50]}...'")

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
        
        response = client.responses.create( # Original call
            model=model_name, 
            input=api_input
        )
        
        answer = None
        standard_input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0

        # Primary attempt: Directly access response.output_text.
        # An AttributeError will occur if 'output_text' does not exist on the response object.
        answer = response.output_text

        # Fallback: If response.output_text was None or an empty string, 
        # try to parse response.output (the list/array).
        # This assumes response.output, if accessed, is iterable and its items have .type and .text attributes.
        # Accessing these attributes directly will raise an AttributeError if they don't exist, unmasking issues.
        if not answer: # Checks if answer is None or an empty string
            if response.output: # This will raise AttributeError if 'output' doesn't exist when 'output_text' was falsy
                for block in response.output: # Assumes response.output is an iterable list of blocks
                    if block.type == "text": # Direct access to block.type
                        answer = block.text  # Direct access to block.text
                        break # Found the first text block
        
        # If no answer could be extracted by either method, raise an exception.
        if answer is None:
            print(f"Unexpected response structure from OpenAI: Failed to extract answer. 'response.output_text' was None or empty, and no 'text' type block found in 'response.output'. Response: {response}")
            raise Exception("Failed to extract answer from OpenAI response. Please check API response structure.")

        # Token usage extraction based on actual OpenAI response structure
        # See: https://platform.openai.com/docs/api-reference/responses/object
        standard_input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0
        
        try:
            if hasattr(response, 'usage'):
                # Standard input tokens are in response.usage.input_tokens
                if hasattr(response.usage, 'input_tokens'):
                    standard_input_tokens = response.usage.input_tokens or 0
                
                # Cached tokens are in response.usage.input_tokens_details.cached_tokens
                if hasattr(response.usage, 'input_tokens_details') and hasattr(response.usage.input_tokens_details, 'cached_tokens'):
                    cached_input_tokens = response.usage.input_tokens_details.cached_tokens or 0
                
                # Output tokens are in response.usage.output_tokens
                if hasattr(response.usage, 'output_tokens'):
                    output_tokens = response.usage.output_tokens or 0
        except Exception as e:
            print(f"Error extracting token usage details: {e}")
            # Continue with default values (0) in case of any error

        print(f"Received answer from model: '{str(answer)[:100]}...'")
        print(f"Tokens - Standard Input: {standard_input_tokens}, Cached Input: {cached_input_tokens}, Output: {output_tokens}")
        return answer, standard_input_tokens, cached_input_tokens, output_tokens
            
    except openai.APIError as e:
        print(f"OpenAI API Error asking about file {file_id} with model {model_name}: {e}")
        # More specific error handling can be added here based on e.status_code or e.type
        # Return 0 tokens on error
        raise Exception(f"OpenAI API Error: {e}") from e # Re-raise to be caught by runner
    except Exception as e:
        print(f"Generic error asking OpenAI about file {file_id} with model {model_name}: {e}")
        # Return 0 tokens on error
        raise Exception(f"Generic error in openai_ask: {e}") from e # Re-raise
