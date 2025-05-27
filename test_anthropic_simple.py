#!/usr/bin/env python3
"""
Simple test of Anthropic file upload and token counting APIs.
"""

import os
from pathlib import Path
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_anthropic_simple():
    """Test basic Anthropic file upload and token counting."""
    
    # Initialize client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No ANTHROPIC_API_KEY found")
        return
    
    client = anthropic.Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "files-api-2025-04-14"}
    )
    
    pdf_path = Path('files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf')
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return
    
    print(f"Testing with file: {pdf_path}")
    print(f"File size: {pdf_path.stat().st_size:,} bytes")
    
    try:
        # Step 1: Upload file
        print("\n=== STEP 1: UPLOAD FILE ===")
        with open(pdf_path, "rb") as file_stream:
            upload_response = client.beta.files.upload(
                file=(pdf_path.name, file_stream, "application/pdf")
            )
        
        print(f"✅ Upload successful!")
        print(f"File ID: {upload_response.id}")
        print(f"Upload response: {upload_response}")
        
        # Step 2: Try token counting with different formats
        print("\n=== STEP 2: TOKEN COUNTING ATTEMPTS ===")
        
        # Attempt 1: Using document with file source
        print("\nAttempt 1: document with file source")
        try:
            response1 = client.messages.count_tokens(
                model="claude-3-5-haiku-20241022",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "file",
                                "file_id": upload_response.id
                            }
                        }
                    ]
                }]
            )
            print(f"✅ Success! Tokens: {response1.input_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Attempt 2: Using just text (for baseline)
        print("\nAttempt 2: text only (baseline)")
        try:
            response2 = client.messages.count_tokens(
                model="claude-3-5-haiku-20241022",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello, how are you?"
                        }
                    ]
                }]
            )
            print(f"✅ Success! Tokens: {response2.input_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Attempt 3: Using file with base64 (if we can read the PDF)
        print("\nAttempt 3: document with base64 source")
        try:
            import base64
            with open(pdf_path, "rb") as f:
                pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
            
            response3 = client.messages.count_tokens(
                model="claude-3-5-haiku-20241022",
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
                        }
                    ]
                }]
            )
            print(f"✅ Success! Tokens: {response3.input_tokens}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Step 3: Test actual message creation (should work)
        print("\n=== STEP 3: ACTUAL MESSAGE WITH FILE ===")
        try:
            message_response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "file",
                                "file_id": upload_response.id
                            }
                        },
                        {
                            "type": "text",
                            "text": "What is this document about? (One sentence only)"
                        }
                    ]
                }]
            )
            print(f"✅ Message creation successful!")
            print(f"Response: {message_response.content[0].text[:100]}...")
            
            # Check if usage info shows token counts
            if hasattr(message_response, 'usage'):
                print(f"Input tokens from message: {message_response.usage.input_tokens}")
                print(f"Output tokens from message: {message_response.usage.output_tokens}")
            
        except Exception as e:
            print(f"❌ Message creation failed: {e}")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")

if __name__ == '__main__':
    test_anthropic_simple() 