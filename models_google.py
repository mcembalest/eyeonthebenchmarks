from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
import os
from dotenv import load_dotenv
from google import genai  # Google Generative AI Python SDK
import time

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please check your .env file.")

# Configure Google Generative AI client
client = genai.Client(api_key=api_key)

# Import cost calculator
from cost_calculator import calculate_cost, calculate_image_cost

# Available Google models for benchmarking
AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "imagen-3",
]

def google_upload(pdf_path: Path) -> str:
    """
    Upload a PDF file to Google Generative AI and return the file ID.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        file_id: The name (ID) of the uploaded file
    """
    try:
        # Upload file to Google
        uploaded_file = client.files.upload(file=str(pdf_path))
        
        # Get the file name (which serves as the ID)
        file_id = uploaded_file.name
        
        print(f"Successfully uploaded {pdf_path.name} to Google. File ID: {file_id}")
        return file_id
    
    except Exception as e:
        print(f"Error uploading {pdf_path} to Google: {e}")
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
        model_name: The model to use (e.g., "gemini-2.5-pro", "imagen-3")
        input_tokens: Number of input tokens (for text models)
        output_tokens: Number of output tokens (for text models)
        search_queries: Number of web search queries
        images: Number of images to generate (for image models)
        image_size: Size of generated images (for image models)
        image_quality: Quality of generated images (standard/hd)
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name == 'imagen-3':
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
            cached_input_tokens=0,  # We'll get this from the API response
            output_tokens=output_tokens,
            search_queries=search_queries
        )


def google_ask(file_id: str, prompt_text: str, model_name: str = "gemini-2.5-flash") -> Tuple[str, int, int, int]:
    """
    Ask a question about a PDF file using Google's Generative AI models.
    
    Args:
        file_id: ID (name) of the uploaded file (obtained via google_upload).
        prompt_text: The question to ask the model.
        model_name: The model to use (e.g., "gemini-2.5-flash", "gemini-2.5-pro").
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response.
            - standard_input_tokens (int): Tokens used in the input (non-cached portion).
            - cached_input_tokens (int): Tokens used in the input (cached portion).
            - output_tokens (int): Tokens used in the output.
    """
    try:
        print(f"Asking model {model_name} about file {file_id} with prompt: '{prompt_text[:50]}...'")

        # Get the file object using the file_id
        file_obj = client.files.get(name=file_id)
        
        # Create the content list with the file and prompt
        contents = [prompt_text, file_obj]
        
        # Track request start time for performance monitoring
        start_time = time.time()
        
        # Generate content using the specified model
        response = client.models.generate_content(
            model=model_name,
            contents=contents
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Extract the response text
        if response and hasattr(response, 'text'):
            answer = response.text
        else:
            raise Exception("Failed to extract answer from Google response")
            
        # Default token values (Google's API doesn't currently provide detailed token info in all models)
        # In the future, if Google adds the token information, update this section
        standard_input_tokens = 0
        cached_input_tokens = 0  # Google doesn't currently indicate cached tokens separately
        output_tokens = 0
        
        # Try to extract token usage if available in the response
        try:
            if hasattr(response, 'usage_metadata'):
                # Standard input tokens
                if hasattr(response.usage_metadata, 'prompt_token_count'):
                    standard_input_tokens = response.usage_metadata.prompt_token_count or 0
                
                # Output tokens
                if hasattr(response.usage_metadata, 'candidates_token_count'):
                    output_tokens = response.usage_metadata.candidates_token_count or 0
        except Exception as e:
            print(f"Error extracting token usage details: {e}")
            # Continue with default values (0) in case of any error
        
        print(f"Received answer from model: '{str(answer)[:100]}...'")

        print(f"Tokens - Standard Input: {standard_input_tokens}, Cached Input: {cached_input_tokens}, Output: {output_tokens}")

        print(f"Response time: {elapsed_time:.2f} seconds")

        return answer, standard_input_tokens, cached_input_tokens, output_tokens
            
    except Exception as e:
        print(f"Error asking Google model about file {file_id} with model {model_name}: {e}")

        # Re-raise the exception to be caught by the runner
        raise Exception(f"Google API Error: {e}") from e



""" imagen model

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key='GEMINI_API_KEY')

response = client.models.generate_images(
    model='imagen-3.0-generate-002',
    prompt='Fuzzy bunnies in my kitchen',
    config=types.GenerateImagesConfig(
        number_of_images= 4,
    )
)
for generated_image in response.generated_images:
  image = Image.open(BytesIO(generated_image.image.image_bytes))
  image.show()

"""