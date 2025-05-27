#!/usr/bin/env python3
"""
Simple test of Google file upload and token counting APIs.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

def test_google_simple():
    """Test basic Google file upload and token counting."""
    
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
    print(f"File size: {pdf_path.stat().st_size:,} bytes")
    
    try:
        # Step 1: Upload file
        print("\n=== STEP 1: UPLOAD FILE ===")
        uploaded_file = client.files.upload(
            file=pdf_path,
            config=dict(mime_type='application/pdf')
        )
        
        print(f"✅ Upload successful!")
        print(f"File name: {uploaded_file.name}")
        print(f"Upload response: {uploaded_file}")
        
        # Step 2: Try token counting with different formats
        print("\n=== STEP 2: TOKEN COUNTING ATTEMPTS ===")
        
        # Attempt 1: Using uploaded file object directly
        print("\nAttempt 1: uploaded file object directly")
        try:
            response1 = client.models.count_tokens(
                model="gemini-2.5-flash-preview-05-20",
                contents=[uploaded_file]
            )
            print(f"✅ Success! Tokens: {response1.total_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Attempt 2: Using file via client.files.get()
        print("\nAttempt 2: file via client.files.get()")
        try:
            file_obj = client.files.get(uploaded_file.name)
            response2 = client.models.count_tokens(
                model="gemini-2.5-flash-preview-05-20",
                contents=[file_obj]
            )
            print(f"✅ Success! Tokens: {response2.total_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Attempt 3: Using text only (baseline)
        print("\nAttempt 3: text only (baseline)")
        try:
            response3 = client.models.count_tokens(
                model="gemini-2.5-flash-preview-05-20",
                contents=["Hello, how are you?"]
            )
            print(f"✅ Success! Tokens: {response3.total_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Attempt 4: Mixed content (text + file)
        print("\nAttempt 4: mixed content (text + file)")
        try:
            response4 = client.models.count_tokens(
                model="gemini-2.5-flash-preview-05-20",
                contents=["Summarize this document:", uploaded_file]
            )
            print(f"✅ Success! Tokens: {response4.total_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Step 3: Test actual message creation (should work)
        print("\n=== STEP 3: ACTUAL MESSAGE WITH FILE ===")
        try:
            from google.genai.types import GenerateContentConfig
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[
                    {
                        "parts": [
                            {"file_data": {"file_uri": uploaded_file.name, "mime_type": "application/pdf"}},
                            {"text": "What is this document about? (One sentence only)"}
                        ]
                    }
                ],
                config=GenerateContentConfig(
                    max_output_tokens=100
                )
            )
            print(f"✅ Message creation successful!")
            
            # Extract text from response
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                print(f"Response: {part.text[:100]}...")
                                break
            
            # Check if usage info shows token counts
            if hasattr(response, 'usage_metadata'):
                print(f"Input tokens from message: {response.usage_metadata.prompt_token_count}")
                print(f"Output tokens from message: {response.usage_metadata.candidates_token_count}")
            
        except Exception as e:
            print(f"❌ Message creation failed: {e}")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")

if __name__ == '__main__':
    test_google_simple() 