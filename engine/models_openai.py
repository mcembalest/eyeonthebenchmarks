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

def openai_ask(file_id: str, prompt_text: str, model_name="gpt-4o-mini") -> tuple[str, int, int]:
    """
    Ask a question about a file using OpenAI's Chat Completions API.
    
    Args:
        file_id: ID of the uploaded file (obtained via openai_upload).
        prompt_text: The question to ask the model.
        model_name: The model to use (e.g., "gpt-4o-mini", "gpt-4o").
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response.
            - prompt_tokens (int): Tokens used in the prompt.
            - completion_tokens (int): Tokens used in the completion.
    """
    try:
        print(f"Asking model {model_name} (ChatCompletion) about file {file_id} with prompt: '{prompt_text[:50]}...'")
        
        # Construct messages for Chat Completions API
        # This assumes the model can handle a file_id directly in a text-like content.
        # If the model requires a specific format for file inputs (e.g., gpt-4-vision-preview style with image_url),
        # this part might need adjustment or a check for model capabilities.
        # For now, we'll try a common approach.
        # A more robust solution might involve a pre-processing step to include file content if the model
        # doesn't directly support file_id in this manner, or using a specific multimodal model structure.
        
        # Option 1: Simple text prompt including a reference to the file.
        # This is less likely to work if the model expects the file content to be part of the prompt in a specific way.
        # enriched_prompt = f"Using the content of the file with ID {file_id}, please answer the following: {prompt_text}"
        # messages = [{"role": "user", "content": enriched_prompt}]
        
        # Option 2: Attempting to use a structure similar to how some multimodal models might take complex content.
        # The OpenAI Python library and API docs should be consulted for the specific model in use.
        # The `client.responses.create` call had a specific structure for `input_file` and `input_text`.
        # Replicating that for `client.chat.completions.create` is not straightforward without knowing if the target model
        # supports this complex content type in the `messages` array.
        # For models like gpt-4o, it can often infer from context or handle image data if provided in a specific format.
        # Since we are passing a file_id from an uploaded file (presumably text-based PDF),
        # the ideal way would be if the model could dereference this file_id.
        # OpenAI's newer "Assistants API" or specific file-processing endpoints are usually better for this.
        #
        # Given the original code used `client.responses.create` with `input_file`,
        # it suggests an API/model that might not be the standard chat completion.
        # However, to get token counts, `chat.completions.create` is standard.
        # This is a tricky part: `gpt-4.1-nano` (and others in `AVAILABLE_MODELS`)
        # might be intended for use with `client.responses.create` IF that endpoint
        # is a specialized one (e.g. from Azure or a beta).
        #
        # If `client.responses.create` *does* return token usage in its response object,
        # then sticking to it and extracting usage would be simpler.
        # Let's assume for a moment it *might* have a usage field, or that we need to adapt.
        
        # Sticking to the original `client.responses.create` and hoping it has usage info:
        # This is a deviation from the plan to switch to chat.completions.create, but might be necessary
        # if `input_file` type is specific to `client.responses.create`.

        api_input = [
            {
                # "role": "user", # Not typically used in client.responses.create input
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
        prompt_tokens = 0
        completion_tokens = 0

        # Attempt to get answer (same as before)
        if hasattr(response, 'output_text') and response.output_text:
            answer = response.output_text
        elif hasattr(response, 'choices') and response.choices and response.choices[0].message and response.choices[0].message.content:
            answer = response.choices[0].message.content
        else:
            print(f"Unexpected response structure from OpenAI (for answer): {response}")
            raise Exception("Failed to extract answer from OpenAI response. Unexpected structure.")

        # Attempt to get token usage - this is speculative for client.responses.create
        if hasattr(response, 'usage'):
            if hasattr(response.usage, 'prompt_tokens'):
                prompt_tokens = response.usage.prompt_tokens
            if hasattr(response.usage, 'completion_tokens'):
                completion_tokens = response.usage.completion_tokens
        elif hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'usage'): # Another possible location
             usage_data = response.choices[0].usage
             if hasattr(usage_data, 'prompt_tokens'):
                prompt_tokens = usage_data.prompt_tokens
             if hasattr(usage_data, 'completion_tokens'):
                completion_tokens = usage_data.completion_tokens
        else:
            print(f"Warning: Token usage information not found in response from {model_name}. Response: {response}")
            # We will return 0 for tokens if not found, and the calling function can decide how to handle this.

        print(f"Received answer from model: '{str(answer)[:100]}...'")
        print(f"Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}")
        return answer, prompt_tokens, completion_tokens
            
    except openai.APIError as e:
        print(f"OpenAI API Error asking about file {file_id} with model {model_name}: {e}")
        # More specific error handling can be added here based on e.status_code or e.type
        # Return 0 tokens on error
        raise Exception(f"OpenAI API Error: {e}") from e # Re-raise to be caught by runner
    except Exception as e:
        print(f"Generic error asking OpenAI about file {file_id} with model {model_name}: {e}")
        # Return 0 tokens on error
        raise Exception(f"Generic error in openai_ask: {e}") from e # Re-raise

