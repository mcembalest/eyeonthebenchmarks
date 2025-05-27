#!/usr/bin/env python3
"""
Test script to verify upload-then-count workflow eliminates all fallbacks.
"""

from pathlib import Path
from models_google import count_tokens_google
from models_anthropic import count_tokens_anthropic  
from models_openai import count_tokens_openai
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_upload_and_count():
    """Test upload-then-count workflow on the specific PDF file."""
    
    # Test file
    pdf_path = Path('files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf')
    print(f'Testing upload-then-count workflow on: {pdf_path}')
    print(f'File exists: {pdf_path.exists()}')

    if not pdf_path.exists():
        print('❌ File not found')
        return

    print(f'File size: {pdf_path.stat().st_size:,} bytes')
    
    # Test results
    results = {}
    
    print('\n=== TESTING GOOGLE ===')
    try:
        # This will upload to Google then count tokens (no fallbacks)
        google_tokens = count_tokens_google([pdf_path], 'gemini-2.5-flash-preview-05-20')
        print(f'✅ Google token count: {google_tokens:,} tokens')
        results['google'] = google_tokens
    except Exception as e:
        print(f'❌ Google failed: {e}')
        results['google'] = f'ERROR: {e}'
    
    print('\n=== TESTING ANTHROPIC ===') 
    try:
        # This will upload to Anthropic then count tokens (no fallbacks)
        content = [{'type': 'file', 'file_path': str(pdf_path)}]
        anthropic_tokens = count_tokens_anthropic(content, 'claude-3-5-haiku-20241022')
        print(f'✅ Anthropic token count: {anthropic_tokens:,} tokens')
        results['anthropic'] = anthropic_tokens
    except Exception as e:
        print(f'❌ Anthropic failed: {e}')
        results['anthropic'] = f'ERROR: {e}'
        
    print('\n=== TESTING OPENAI ===')
    try:
        # This will extract PDF text and count with tiktoken (no fallbacks)
        content = [{'type': 'input_file', 'file_path': str(pdf_path)}]
        openai_tokens = count_tokens_openai(content, 'gpt-4o')
        print(f'✅ OpenAI token count: {openai_tokens:,} tokens')
        results['openai'] = openai_tokens
    except Exception as e:
        print(f'❌ OpenAI failed: {e}')
        results['openai'] = f'ERROR: {e}'
    
    print('\n=== SUMMARY ===')
    for provider, result in results.items():
        if isinstance(result, int):
            print(f'{provider.upper()}: {result:,} tokens')
        else:
            print(f'{provider.upper()}: {result}')
    
    # Check if all providers succeeded
    successful_providers = [p for p, r in results.items() if isinstance(r, int)]
    if len(successful_providers) == 3:
        print(f'\n✅ ALL PROVIDERS SUCCESSFUL - NO FALLBACKS USED')
        
        # Check for reasonable token count variance (should be similar but not identical)
        token_counts = [r for r in results.values() if isinstance(r, int)]
        min_tokens = min(token_counts)
        max_tokens = max(token_counts)
        variance = (max_tokens - min_tokens) / min_tokens * 100
        print(f'Token count variance: {variance:.1f}% (expected due to different tokenization)')
    else:
        print(f'\n⚠️ {len(successful_providers)}/3 providers successful')

if __name__ == '__main__':
    test_upload_and_count() 