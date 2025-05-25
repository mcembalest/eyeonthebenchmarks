from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union, List
import os
import pathlib
from pathlib import Path
from dotenv import load_dotenv
from google import genai  # Google Generative AI Python SDK
import time
import logging
from file_store import register_file, get_provider_file_id, register_provider_upload

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please check your .env file.")

# Configure Google Generative AI client
client = genai.Client(api_key=api_key)

# Available Google models for benchmarking
AVAILABLE_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    # "imagen-3.0-generate-002",
]

"""gemini 2.5 pro pricing
Gemini 2.5 Pro Preview
Try it in Google AI Studio

Our state-of-the-art multipurpose model, which excels at coding and complex reasoning tasks.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Not available	$1.25, prompts <= 200k tokens
$2.50, prompts > 200k tokens
Output price (including thinking tokens)	Not available	$10.00, prompts <= 200k tokens
$15.00, prompts > 200k
Context caching price	Not available	$0.31, prompts <= 200k tokens
$0.625, prompts > 200k
$4.50 / 1,000,000 tokens per hour
Grounding with Google Search	Not available	1,500 RPD (free), then $35 / 1,000 requests
Text-to-speech
(gemini-2.5-pro-preview-tts)	Free of charge	$1.00 (Input)
$20.00 (Output)
Used to improve our products	Yes	No"""


"""gemini 2.5 flash pricing
Gemini 2.5 Flash Preview
Try it in Google AI Studio

Our first hybrid reasoning model which supports a 1M token context window and has thinking budgets.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Free of charge	$0.15 (text / image / video)
$1.00 (audio)
Output price	Free of charge	Non-thinking: $0.60
Thinking: $3.50
Context caching price	Not available	$0.0375 (text / image / video)
$0.25 (audio)
$1.00 / 1,000,000 tokens per hour
Grounding with Google Search	Free of charge, up to 500 RPD	1,500 RPD (free), then $35 / 1,000 requests
Text-to-speech
(gemini-2.5-flash-preview-tts)	Free of charge	$0.50 (Input)
$10.00 (Output)
Used to improve our products	Yes	No"""

"""token counting guide

Context windows
The models available through the Gemini API have context windows that are measured in tokens. The context window defines how much input you can provide and how much output the model can generate. You can determine the size of the context window by calling the getModels endpoint or by looking in the models documentation.

In the following example, you can see that the gemini-1.5-flash model has an input limit of about 1,000,000 tokens and an output limit of about 8,000 tokens, which means a context window is 1,000,000 tokens.


from google import genai

client = genai.Client()
model_info = client.models.get(model="gemini-2.0-flash")
print(f"{model_info.input_token_limit=}")
print(f"{model_info.output_token_limit=}")
# ( e.g., input_token_limit=30720, output_token_limit=2048 )

Count tokens
All input to and output from the Gemini API is tokenized, including text, image files, and other non-text modalities.

You can count tokens in the following ways:

Call count_tokens with the input of the request.
This returns the total number of tokens in the input only. You can make this call before sending the input to the model to check the size of your requests.

Use the usage_metadata attribute on the response object after calling generate_content.
This returns the total number of tokens in both the input and the output: total_token_count.
It also returns the token counts of the input and output separately: prompt_token_count (input tokens) and candidates_token_count (output tokens).

Count text tokens
If you call count_tokens with a text-only input, it returns the token count of the text in the input only (total_tokens). You can make this call before calling generate_content to check the size of your requests.

Another option is calling generate_content and then using the usage_metadata attribute on the response object to get the following:

The separate token counts of the input (prompt_token_count) and the output (candidates_token_count)
The total number of tokens in both the input and the output (total_token_count)

from google import genai

client = genai.Client()
prompt = "The quick brown fox jumps over the lazy dog."

# Count tokens using the new client method.
total_tokens = client.models.count_tokens(
    model="gemini-2.0-flash", contents=prompt
)
print("total_tokens: ", total_tokens)
# ( e.g., total_tokens: 10 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=prompt
)

# The usage_metadata provides detailed token counts.
print(response.usage_metadata)
# ( e.g., prompt_token_count: 11, candidates_token_count: 73, total_token_count: 84 )

Count multimodal tokens
All input to the Gemini API is tokenized, including text, image files, and other non-text modalities. Note the following high-level key points about tokenization of multimodal input during processing by the Gemini API:

With Gemini 2.0, image inputs with both dimensions <=384 pixels are counted as 258 tokens. Images larger in one or both dimensions are cropped and scaled as needed into tiles of 768x768 pixels, each counted as 258 tokens. Prior to Gemini 2.0, images used a fixed 258 tokens.

Video and audio files are converted to tokens at the following fixed rates: video at 263 tokens per second and audio at 32 tokens per second.

Image files
If you call count_tokens with a text-and-image input, it returns the combined token count of the text and the image in the input only (total_tokens). You can make this call before calling generate_content to check the size of your requests. You can also optionally call count_tokens on the text and the file separately.

Another option is calling generate_content and then using the usage_metadata attribute on the response object to get the following:

The separate token counts of the input (prompt_token_count) and the output (candidates_token_count)
The total number of tokens in both the input and the output (total_token_count)
Note: You'll get the same token count if you use a file uploaded using the File API or you provide the file as inline data.
Example that uses an uploaded image from the File API:


from google import genai

client = genai.Client()
prompt = "Tell me about this image"
your_image_file = client.files.upload(file=media / "organ.jpg")

print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=[prompt, your_image_file]
    )
)
# ( e.g., total_tokens: 263 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=[prompt, your_image_file]
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 264, candidates_token_count: 80, total_token_count: 345 )

System instructions and tools
System instructions and tools also count towards the total token count for the input.

If you use system instructions, the total_tokens count increases to reflect the addition of system_instruction.

If you use function calling, the total_tokens count increases to reflect the addition of tools."""

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

IMAGE_COST = 0.03

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

def google_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str = "gemini-2.5-flash-preview-05-20", db_path: Path = Path.cwd()) -> Tuple[str, int, int, int]:
    """
    Send a query to a Google model with multiple file attachments.
    
    Args:
        file_paths: List of paths to files to include
        prompt_text: The question to ask the model
        model_name: The model to use
        db_path: Path to the database directory
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output
    """
    # Ensure all files are uploaded to Google
    file_ids = []
    for file_path in file_paths:
        file_id = ensure_file_uploaded(file_path, db_path)
        file_ids.append(file_id)
    
    # Build contents with all files
    contents = [prompt_text]
    for file_id in file_ids:
        file_obj = client.files.get(name=file_id)
        contents.append(file_obj)
    
    return google_ask_internal(contents, model_name)

def google_ask_internal(contents: List, model_name: str) -> Tuple[str, int, int, int]:
    """
    Internal function to send a query to Google with prepared contents.
    """
    try:
        print(f"\n🔄 GOOGLE API CALL STARTING - MODEL: {model_name}")
        
        # Count files in contents
        file_count = sum(1 for item in contents if hasattr(item, 'name'))  # Google file objects have 'name' attribute
        prompt_preview = contents[0][:50] + "..." if isinstance(contents[0], str) else "No text prompt"
        
        print(f"   Files: {file_count}, Prompt: '{prompt_preview}'")
        
        logging.info(f"Sending prompt to Google using model {model_name}")
        
        # Track request start time for performance monitoring
        start_time = time.time()
        
        # Generate content using the specified model
        response = client.models.generate_content(
            model=model_name,
            contents=contents
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ GOOGLE API RESPONSE RECEIVED AFTER {elapsed_time:.2f} SECONDS")
        print(f"   Model: {model_name}")
        
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
                    
                logging.info(f"Extracted token counts - Input: {standard_input_tokens}, Output: {output_tokens}")
        except Exception as e:
            logging.warning(f"Error extracting token usage details: {e}")
            # Continue with default values (0) in case of any error
        
        # Print prominent results for high visibility in the console
        print(f"\n💬 ANSWER FROM {model_name.upper()}:")
        print(f"   '{str(answer)[:150]}...'" if len(str(answer)) > 150 else f"   '{str(answer)}'")
        print(f"   Tokens - Input: {standard_input_tokens}, Cached: {cached_input_tokens}, Output: {output_tokens}")
        print(f"   Response time: {elapsed_time:.2f} seconds")
        print(f"=================================================")

        logging.info(f"Received answer (truncated): '{str(answer)[:100]}...'")
        return answer, standard_input_tokens, cached_input_tokens, output_tokens
            
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