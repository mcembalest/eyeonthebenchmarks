#!/usr/bin/env python3
"""
Debug test for Google token counting issues.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

def test_google_debug():
    """Debug Google token counting issues."""
    
    # Initialize client
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ No GOOGLE_API_KEY found")
        return
    
    client = genai.Client(api_key=api_key)
    
    pdf_path = Path('files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf')
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return
    
    print(f"Testing with file: {pdf_path}")
    
    try:
        # Upload file
        print("\n=== UPLOADING FILE ===")
        uploaded_file = client.files.upload(
            file=pdf_path,
            config=dict(mime_type='application/pdf')
        )
        
        print(f"✅ Upload successful!")
        print(f"File object type: {type(uploaded_file)}")
        print(f"File object dir: {dir(uploaded_file)}")
        print(f"File object: {uploaded_file}")
        
        # Debug what we're passing to count_tokens
        print("\n=== DEBUGGING CONTENTS ===")
        contents = [uploaded_file]
        print(f"Contents type: {type(contents)}")
        print(f"Contents[0] type: {type(contents[0])}")
        print(f"Contents[0]: {contents[0]}")
        
        # Try token counting with debug
        print("\n=== TOKEN COUNTING WITH DEBUG ===")
        try:
            print("Calling client.models.count_tokens...")
            response = client.models.count_tokens(
                model="gemini-2.5-flash-preview-05-20",
                contents=contents
            )
            print(f"✅ Success! Tokens: {response.total_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
            print(f"Exception type: {type(e)}")
            print(f"Exception details: {str(e)}")
            
            # Let's try a different approach - maybe the issue is the contents structure
            print("\n=== TRYING DIRECT FILE OBJECT ===")
            try:
                response2 = client.models.count_tokens(
                    model="gemini-2.5-flash-preview-05-20",
                    contents=uploaded_file  # Direct file object, not in list
                )
                print(f"✅ Success with direct file! Tokens: {response2.total_tokens}")
            except Exception as e2:
                print(f"❌ Also failed with direct file: {e2}")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")

if __name__ == '__main__':
    test_google_debug() 