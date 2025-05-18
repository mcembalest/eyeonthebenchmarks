import os
import pathlib
from dotenv import load_dotenv
import logging
from google import genai

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load API key from .env file
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found in environment variables or .env file")
    print("Please add your GOOGLE_API_KEY to your .env file")
    exit(1)

print(f"API Key found (first 10 chars): {api_key[:10]}...")

# Configure client
try:
    # Initialize the Google Generative AI client
    client = genai.Client(api_key=api_key)
    logger.info("Google Generative AI client initialized successfully")
    
    # Create a simple text file for testing
    test_file_path = pathlib.Path('test_file.txt')
    test_file_path.write_text('This is a test file to verify Google API access')
    
    # Test file upload capability
    logger.info("Testing file upload...")
    uploaded_file = client.files.upload(file=test_file_path)
    print(f"File uploaded successfully with ID: {uploaded_file.name}")
    
    # Test simple text generation
    logger.info("Testing text generation...")
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-04-17",
        contents=["Hello, can you verify my API key is working correctly?"])
    
    print(f"\nResponse from Gemini:\n{response.text}")
    print("\n✅ Google API key is working correctly!")
    
    # Print available models from our own list
    from models_google import AVAILABLE_MODELS
    print("\nAvailable Google Generative AI models:")
    for model in AVAILABLE_MODELS:
        print(f" - {model}")
        
    # Clean up test file
    test_file_path.unlink(missing_ok=True)
    
    print("\nGoogle API integration is ready for benchmarking!")
    
except Exception as e:
    logger.error(f"Error testing Google API key: {e}", exc_info=True)
    print(f"❌ Error: {e}")

