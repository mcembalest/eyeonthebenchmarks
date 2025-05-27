#!/usr/bin/env python3
"""
Debug token counting issues across providers.
Investigating why Google reports so few tokens and why gpt-4o-mini has 8x more input tokens.
"""

import sys
from pathlib import Path
from models_openai import openai_ask_with_files, ensure_openai_client
from models_google import google_ask_with_files, ensure_google_client
from models_anthropic import anthropic_ask_with_files

def analyze_pdf_content():
    """Analyze the actual PDF content to understand expected token count."""
    
    pdf_path = Path("files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf")
    
    print(f"📄 ANALYZING PDF CONTENT")
    print(f"=" * 60)
    print(f"   File: {pdf_path.name}")
    print(f"   Size: {pdf_path.stat().st_size:,} bytes")
    
    # Try to extract text from PDF to estimate expected tokens
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            total_text = ""
            page_count = len(pdf_reader.pages)
            
            print(f"   Pages: {page_count}")
            
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                total_text += page_text
                print(f"      Page {i+1}: {len(page_text)} characters")
                if i < 2:  # Show first 2 pages as sample
                    print(f"         Sample: '{page_text[:100]}...'")
            
            print(f"   Total text: {len(total_text):,} characters")
            
            # Rough token estimate (1 token ≈ 4 characters)
            estimated_tokens = len(total_text) // 4
            print(f"   Estimated tokens (text only): ~{estimated_tokens:,}")
            print(f"   Expected multimodal tokens: ~{estimated_tokens * 2}-{estimated_tokens * 5:,}")
            
            return estimated_tokens, total_text
            
    except Exception as e:
        print(f"   ❌ Could not extract PDF text: {e}")
        return None, None

def debug_openai_models():
    """Debug OpenAI token counting differences."""
    
    pdf_path = Path("files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf")
    
    print(f"\n🤖 DEBUGGING OPENAI TOKEN DIFFERENCES")
    print(f"=" * 60)
    
    models_to_test = ["gpt-4o", "gpt-4o-mini", "gpt-4.1"]
    
    for model in models_to_test:
        print(f"\n🔬 Testing {model}:")
        try:
            # Test with manual client inspection
            client = ensure_openai_client()
            
            # Upload file and get file object
            from models_openai import ensure_file_uploaded
            file_id = ensure_file_uploaded(pdf_path)
            
            print(f"   File ID: {file_id}")
            
            # Build content manually to see what's being sent
            content = [
                {"type": "input_file", "file_id": file_id},
                {"type": "input_text", "text": "Who wrote this?"}
            ]
            
            api_input = [{"role": "user", "content": content}]
            
            print(f"   Content blocks: {len(content)}")
            print(f"   File reference: {file_id}")
            
            # Make API call and examine response structure
            response = client.responses.create(model=model, input=api_input)
            
            usage = response.usage
            print(f"   Raw usage object: {usage}")
            print(f"   Input tokens: {usage.input_tokens}")
            print(f"   Output tokens: {usage.output_tokens}")
            print(f"   Total tokens: {usage.total_tokens}")
            
            if hasattr(usage, 'input_tokens_details'):
                print(f"   Input details: {usage.input_tokens_details}")
            if hasattr(usage, 'output_tokens_details'):
                print(f"   Output details: {usage.output_tokens_details}")
                
        except Exception as e:
            print(f"   ❌ Error testing {model}: {e}")

def debug_google_tokens():
    """Debug Google's low token counts."""
    
    pdf_path = Path("files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf")
    
    print(f"\n🟢 DEBUGGING GOOGLE TOKEN COUNTING")
    print(f"=" * 60)
    
    try:
        client = ensure_google_client()
        
        # Upload file and examine
        from models_google import google_upload
        google_file_id = google_upload(pdf_path)
        google_file = client.files.get(name=google_file_id)
        
        print(f"   Google file ID: {google_file_id}")
        print(f"   File object: {type(google_file)}")
        print(f"   File size info: {getattr(google_file, 'size_bytes', 'unknown')}")
        
        # Test token counting manually
        contents = [google_file, "Who wrote this?"]
        
        print(f"   Testing token counting...")
        token_response = client.models.count_tokens(
            model="gemini-2.5-flash-preview-05-20",
            contents=contents
        )
        
        print(f"   Count tokens result: {token_response}")
        print(f"   Total tokens from count_tokens: {token_response.total_tokens}")
        
        # Test with actual generation to compare
        print(f"   Testing with generation...")
        from google.genai.types import GenerateContentConfig
        config = GenerateContentConfig(
            max_output_tokens=50,
            response_modalities=["TEXT"]
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=contents,
            config=config
        )
        
        usage = response.usage_metadata
        print(f"   Generation usage: {usage}")
        print(f"   Prompt tokens: {usage.prompt_token_count}")
        print(f"   Total tokens: {usage.total_token_count}")
        
        # Check if there's a discrepancy
        if token_response.total_tokens != usage.prompt_token_count:
            print(f"   ⚠️ DISCREPANCY: count_tokens={token_response.total_tokens} vs prompt_tokens={usage.prompt_token_count}")
        
    except Exception as e:
        print(f"   ❌ Error debugging Google: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run comprehensive token debugging."""
    
    print("🔍 COMPREHENSIVE TOKEN DEBUGGING")
    print("=" * 80)
    
    # Analyze PDF content first
    estimated_tokens, text_content = analyze_pdf_content()
    
    # Debug OpenAI differences
    debug_openai_models()
    
    # Debug Google low counts
    debug_google_tokens()
    
    print(f"\n📊 SUMMARY OF ISSUES:")
    if estimated_tokens:
        print(f"   Expected tokens (rough): ~{estimated_tokens:,} - {estimated_tokens*3:,}")
    
    print(f"   🚨 Google reporting only ~2,300 tokens (likely missing multimodal processing)")
    print(f"   🚨 OpenAI gpt-4o-mini reporting 8x more than other models (possible tokenization issue)")
    
    print(f"\n🔧 INVESTIGATION NEEDED:")
    print(f"   1. Verify Google is processing PDF as multimodal vs text-only")
    print(f"   2. Check OpenAI file upload consistency across models")
    print(f"   3. Validate token counting APIs vs generation APIs")

if __name__ == "__main__":
    main() 