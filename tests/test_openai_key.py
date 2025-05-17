#!/usr/bin/env python
import os
from dotenv import load_dotenv
import openai
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load API key from .env file
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
print(f"API Key found (first 10 chars): {api_key[:10]}...")

# Configure client
try:
    client = openai.OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized")
    
    # Try a simple completions request to test the key
    logger.info("Testing API key with a simple request...")
    response = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "user", "content": "Hello, can you hear me?"}
        ]
    )
    
    print(f"Response received: {response.output_text}")
    print("✅ API key is working correctly!")
    
except Exception as e:
    logger.error(f"Error testing OpenAI API key: {e}", exc_info=True)
    print(f"❌ Error: {e}")
