#!/usr/bin/env python3
"""
Test script to verify token counting across all providers
"""

from pathlib import Path
from token_validator import validate_token_limits, format_token_validation_message
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_token_counting():
    """Test token counting with a sample prompt and PDF"""
    
    # Sample test data
    prompts = [{"prompt_text": "Please analyze this document and provide a summary."}]
    
    # Use the specific PDF file provided
    pdf_path = Path("/Users/maxcembalest/Desktop/repos/eyeonthebenchmarks/files/2025_Special_FiftyDaysOfGrey/fifty-days-of-grey.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return
    
    pdf_paths = [str(pdf_path)]
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"📄 Using PDF file: {pdf_path.name}")
    print(f"📊 File size: {file_size_mb:.2f} MB ({pdf_path.stat().st_size:,} bytes)")
    
    # Test models from each provider
    model_names = [
        # OpenAI models
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4.1",
        "o3",
        
        # Anthropic models  
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
        
        # Google models
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-pro-preview-05-06"
    ]
    
    print(f"\n🧪 Testing token counting with {len(model_names)} models...")
    print(f"💬 Test prompt: '{prompts[0]['prompt_text']}'")
    
    # Run validation
    try:
        results = validate_token_limits(prompts, pdf_paths, model_names)
        
        print(f"\n📊 Token Counting Results:")
        print("=" * 60)
        
        for model_name, result in results["model_results"].items():
            provider = result["provider"]
            tokens = result["estimated_tokens"]
            limit = result["context_limit"]
            will_exceed = result["will_exceed"]
            
            status = "🚫" if will_exceed else "✅"
            print(f"{status} {model_name} ({provider}):")
            print(f"   Tokens: {tokens:,} / {limit:,}")
            if will_exceed:
                print(f"   ⚠️ EXCEEDS LIMIT")
            print()
        
        # Print formatted message
        print("\n📋 Formatted validation message:")
        print("-" * 40)
        print(format_token_validation_message(results))
        
        # Summary by provider
        print(f"\n📈 Summary by Provider:")
        print("-" * 40)
        providers = {}
        for model_name, result in results["model_results"].items():
            provider = result["provider"]
            if provider not in providers:
                providers[provider] = []
            providers[provider].append((model_name, result["estimated_tokens"]))
        
        for provider, models in providers.items():
            print(f"\n{provider.upper()}:")
            for model_name, tokens in models:
                print(f"  • {model_name}: {tokens:,} tokens")
        
        # Check for concerning discrepancies 
        all_tokens = [result["estimated_tokens"] for result in results["model_results"].values()]
        min_tokens = min(all_tokens)
        max_tokens = max(all_tokens)
        
        if max_tokens > min_tokens * 10:  # More than 10x difference
            print(f"\n⚠️ WARNING: Large discrepancy in token counts!")
            print(f"   Range: {min_tokens:,} to {max_tokens:,} tokens")
            print(f"   Ratio: {max_tokens/min_tokens:.1f}x difference")
            print(f"   This suggests issues in token counting logic.")
        else:
            print(f"\n✅ Token counts are reasonably consistent")
            print(f"   Range: {min_tokens:,} to {max_tokens:,} tokens")
            print(f"   Ratio: {max_tokens/min_tokens:.1f}x difference")
            
    except Exception as e:
        print(f"❌ Error during token validation: {e}")
        import traceback
        traceback.print_exc()
    
    # No cleanup needed since we're using an actual file

if __name__ == "__main__":
    test_token_counting() 