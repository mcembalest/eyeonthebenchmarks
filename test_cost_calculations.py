#!/usr/bin/env python3
"""
Comprehensive test suite for token counting and cost calculation accuracy
across all three providers: OpenAI, Google, and Anthropic.
"""

import sys
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from models_openai import calculate_cost as openai_calculate_cost
from models_google import calculate_cost as google_calculate_cost
from models_anthropic import calculate_cost as anthropic_calculate_cost

def test_openai_costs():
    """Test OpenAI cost calculations"""
    print("🔍 Testing OpenAI Cost Calculations")
    print("=" * 50)
    
    # Test gpt-4o
    result = openai_calculate_cost(
        model_name="gpt-4o",
        standard_input_tokens=1000,
        cached_input_tokens=500,
        output_tokens=200,
        reasoning_tokens=50
    )
    
    expected_input_cost = (1000 * 2.50) / 1_000_000  # $0.0025
    expected_cached_cost = (500 * 1.25) / 1_000_000  # $0.000625
    expected_output_cost = (200 * 10.00) / 1_000_000  # $0.002
    expected_total = expected_input_cost + expected_cached_cost + expected_output_cost
    
    print(f"GPT-4o Test:")
    print(f"  Input: 1000 tokens × $2.50/1M = ${expected_input_cost:.6f}")
    print(f"  Cached: 500 tokens × $1.25/1M = ${expected_cached_cost:.6f}")
    print(f"  Output: 200 tokens × $10.00/1M = ${expected_output_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()
    
    # Test o4-mini
    result = openai_calculate_cost(
        model_name="o4-mini",
        standard_input_tokens=2000,
        cached_input_tokens=0,
        output_tokens=300
    )
    
    expected_input_cost = (2000 * 1.10) / 1_000_000  # $0.0022
    expected_output_cost = (300 * 4.40) / 1_000_000  # $0.00132
    expected_total = expected_input_cost + expected_output_cost
    
    print(f"o4-mini Test:")
    print(f"  Input: 2000 tokens × $1.10/1M = ${expected_input_cost:.6f}")
    print(f"  Output: 300 tokens × $4.40/1M = ${expected_output_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()

def test_google_costs():
    """Test Google cost calculations"""
    print("🔍 Testing Google Cost Calculations")
    print("=" * 50)
    
    # Test Gemini 2.5 Flash with thinking tokens
    result = google_calculate_cost(
        model_name="gemini-2.5-flash-preview-05-20",
        standard_input_tokens=1000,
        cached_input_tokens=500,
        output_tokens=200,
        thinking_tokens=50
    )
    
    expected_input_cost = (1000 * 0.15) / 1_000_000  # $0.00015
    expected_cached_cost = (500 * 0.0375) / 1_000_000  # $0.00001875
    expected_output_cost = (200 * 0.60) / 1_000_000  # $0.00012
    expected_thinking_cost = (50 * 3.50) / 1_000_000  # $0.000175
    expected_total = expected_input_cost + expected_cached_cost + expected_output_cost + expected_thinking_cost
    
    print(f"Gemini 2.5 Flash Test:")
    print(f"  Input: 1000 tokens × $0.15/1M = ${expected_input_cost:.6f}")
    print(f"  Cached: 500 tokens × $0.0375/1M = ${expected_cached_cost:.8f}")
    print(f"  Output: 200 tokens × $0.60/1M = ${expected_output_cost:.6f}")
    print(f"  Thinking: 50 tokens × $3.50/1M = ${expected_thinking_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()
    
    # Test Gemini 2.5 Pro with large prompt
    result = google_calculate_cost(
        model_name="gemini-2.5-pro-preview-05-06",
        standard_input_tokens=250000,  # >200k tokens
        cached_input_tokens=0,
        output_tokens=1000,
        prompt_size_category="large"
    )
    
    expected_input_cost = (250000 * 2.50) / 1_000_000  # $0.625
    expected_output_cost = (1000 * 15.00) / 1_000_000  # $0.015
    expected_total = expected_input_cost + expected_output_cost
    
    print(f"Gemini 2.5 Pro Large Prompt Test:")
    print(f"  Input: 250000 tokens × $2.50/1M = ${expected_input_cost:.6f}")
    print(f"  Output: 1000 tokens × $15.00/1M = ${expected_output_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()

def test_anthropic_costs():
    """Test Anthropic cost calculations"""
    print("🔍 Testing Anthropic Cost Calculations")
    print("=" * 50)
    
    # Test Claude 3.5 Haiku with cache differentiation
    result = anthropic_calculate_cost(
        model_name="claude-3-5-haiku-20241022",
        standard_input_tokens=1000,
        cache_write_tokens=100,
        cache_read_tokens=400,
        output_tokens=200
    )
    
    expected_input_cost = (1000 * 0.80) / 1_000_000  # $0.0008
    expected_cache_write_cost = (100 * 1.00) / 1_000_000  # $0.0001
    expected_cache_read_cost = (400 * 0.08) / 1_000_000  # $0.000032
    expected_output_cost = (200 * 4.00) / 1_000_000  # $0.0008
    expected_total = expected_input_cost + expected_cache_write_cost + expected_cache_read_cost + expected_output_cost
    
    print(f"Claude 3.5 Haiku Test:")
    print(f"  Input: 1000 tokens × $0.80/1M = ${expected_input_cost:.6f}")
    print(f"  Cache Write: 100 tokens × $1.00/1M = ${expected_cache_write_cost:.6f}")
    print(f"  Cache Read: 400 tokens × $0.08/1M = ${expected_cache_read_cost:.6f}")
    print(f"  Output: 200 tokens × $4.00/1M = ${expected_output_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()
    
    # Test Claude 3.5 Haiku (cost-effective model) - second test
    result = anthropic_calculate_cost(
        model_name="claude-3-5-haiku-20241022",
        standard_input_tokens=5000,
        cache_write_tokens=0,
        cache_read_tokens=1000,
        output_tokens=500
    )
    
    expected_input_cost = (5000 * 0.80) / 1_000_000  # $0.004
    expected_cache_read_cost = (1000 * 0.08) / 1_000_000  # $0.00008
    expected_output_cost = (500 * 4.00) / 1_000_000  # $0.002
    expected_total = expected_input_cost + expected_cache_read_cost + expected_output_cost
    
    print(f"Claude 3.5 Haiku Test:")
    print(f"  Input: 5000 tokens × $0.80/1M = ${expected_input_cost:.6f}")
    print(f"  Cache Read: 1000 tokens × $0.08/1M = ${expected_cache_read_cost:.8f}")
    print(f"  Output: 500 tokens × $4.00/1M = ${expected_output_cost:.6f}")
    print(f"  Expected Total: ${expected_total:.6f}")
    print(f"  Calculated Total: ${result['total_cost']:.6f}")
    print(f"  ✅ Match: {abs(result['total_cost'] - expected_total) < 0.000001}")
    print()


def main():
    """Run all cost calculation tests"""
    print("🧮 COMPREHENSIVE TOKEN COUNTING & PRICING VERIFICATION")
    print("=" * 60)
    print()
    
    try:
        test_openai_costs()
        test_google_costs()
        test_anthropic_costs()

    except Exception as e:
        print(f"❌ ERROR during cost calculation testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 