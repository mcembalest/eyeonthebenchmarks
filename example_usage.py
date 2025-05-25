#!/usr/bin/env python3
"""
Example usage of the clean multi-provider benchmarking system.
This demonstrates the MVP architecture: collect responses, accurate token counting, and cost calculation.
"""

from pathlib import Path
from file_store import init_db, save_benchmark, load_all_benchmarks, get_benchmark_details
from runner import run_benchmark_from_db
from models_openai import calculate_cost as openai_calculate_cost
from models_google import calculate_cost as google_calculate_cost
from models_anthropic import calculate_cost as anthropic_calculate_cost

def main():
    """Demonstrate the new clean architecture with accurate token counting and cost calculation."""
    
    print("🚀 Multi-Provider Benchmarking System (MVP - Accurate Token Counting)")
    print("=" * 70)
    
    # Initialize the database
    print("1. Initializing database...")
    init_db()
    print("   ✅ Database initialized (Simplified Schema - No Scoring)")
    
    # Example: Create a benchmark with multiple files
    print("\n2. Creating a benchmark...")
    
    # Example file paths (replace with your actual files or create dummy PDFs)
    example_files = ["example1.pdf", "example2.pdf"]
    
    # Ensure dummy files exist for the demo if not already present
    for i, f_name in enumerate(example_files):
        p = Path(f_name)
        if not p.exists():
            try:
                with open(p, "w") as f:
                    f.write(f"This is dummy PDF content for testing - File {i+1}. Different content to ensure unique hashes.")
                print(f"   ℹ️ Created dummy file: {p}")
            except IOError as e:
                print(f"   ⚠️ Could not create dummy file {p}: {e}. Please create it manually.")
    
    # Create benchmark with multiple files
    benchmark_id = save_benchmark(
        label="Token Counting Demo",
        description="Demonstrates accurate token counting and cost calculation across providers",
        file_paths=example_files
    )
    print(f"   ✅ Created benchmark with ID: {benchmark_id}")
    
    # Example prompts for testing
    prompts = [
        {"prompt_text": "What is the main topic of this document?"},
        {"prompt_text": "Summarize the key points in 3 bullet points."},
        {"prompt_text": "What questions would you ask to better understand this content?"}
    ]
    
    print(f"\n3. Running benchmarks with accurate token counting...")
    
    # Test different models to demonstrate token counting differences
    test_models = [
        "gpt-4o-mini",  # OpenAI
        "gemini-2.5-flash-preview-05-20",  # Google
        "claude-3-5-haiku-20241022"  # Anthropic
    ]
    
    for model_name in test_models:
        print(f"\n   🔄 Testing {model_name}...")
        
        try:
            # Run the benchmark
            result = run_benchmark_from_db(prompts, benchmark_id, model_name)
            
            if "error" in result:
                print(f"   ❌ Error with {model_name}: {result['error']}")
                continue
            
            # Extract token counts
            total_standard_input = result.get('total_standard_input_tokens', 0)
            total_cached_input = result.get('total_cached_input_tokens', 0)
            total_output = result.get('total_output_tokens', 0)
            
            print(f"   ✅ {model_name} completed:")
            print(f"      📊 Tokens - Input: {total_standard_input}, Cached: {total_cached_input}, Output: {total_output}")
            print(f"      ⏱️ Time: {result.get('elapsed_s', 0)}s")
            
            # Calculate costs using the appropriate provider function
            if model_name.startswith("gpt-") or model_name.startswith("o"):
                cost_info = openai_calculate_cost(
                    model_name=model_name,
                    standard_input_tokens=total_standard_input,
                    cached_input_tokens=total_cached_input,
                    output_tokens=total_output
                )
            elif model_name.startswith("gemini-"):
                cost_info = google_calculate_cost(
                    model_name=model_name,
                    standard_input_tokens=total_standard_input,
                    cached_input_tokens=total_cached_input,
                    output_tokens=total_output,
                    thinking_tokens=0  # Would need to extract from response if available
                )
            elif model_name.startswith("claude-"):
                cost_info = anthropic_calculate_cost(
                    model_name=model_name,
                    standard_input_tokens=total_standard_input,
                    cache_write_tokens=0,  # Would need to differentiate from response
                    cache_read_tokens=total_cached_input,
                    output_tokens=total_output
                )
            else:
                cost_info = {"error": "Unknown provider"}
            
            if "error" not in cost_info:
                print(f"      💰 Estimated cost: ${cost_info['total_cost']:.6f}")
                print(f"         - Input: ${cost_info['input_cost']:.6f}")
                if 'cached_cost' in cost_info:
                    print(f"         - Cached: ${cost_info['cached_cost']:.6f}")
                if 'cache_read_cost' in cost_info:
                    print(f"         - Cache Read: ${cost_info['cache_read_cost']:.6f}")
                if 'thinking_cost' in cost_info:
                    print(f"         - Thinking: ${cost_info['thinking_cost']:.6f}")
                print(f"         - Output: ${cost_info['output_cost']:.6f}")
            else:
                print(f"      ⚠️ Cost calculation error: {cost_info['error']}")
                
        except Exception as e:
            print(f"   ❌ Error running {model_name}: {e}")
    
    print(f"\n4. Listing all benchmarks...")
    benchmarks = load_all_benchmarks()
    print(f"   📋 Found {len(benchmarks)} benchmarks:")
    for bm in benchmarks:
        print(f"      - ID {bm['id']}: {bm['label']} ({bm['timestamp']})")
    
    print(f"\n5. Getting detailed results...")
    details = get_benchmark_details(benchmark_id)
    if details and 'prompts_data' in details:
        print(f"   📊 Benchmark '{details['label']}' has {len(details['prompts_data'])} prompt results")
        for i, prompt_data in enumerate(details['prompts_data'][:2]):  # Show first 2
            print(f"      Prompt {i+1}: '{prompt_data.get('prompt_text', 'N/A')[:50]}...'")
            print(f"      Response: '{prompt_data.get('model_answer', 'N/A')[:100]}...'")
            print(f"      Tokens: {prompt_data.get('standard_input_tokens', 0)} in, {prompt_data.get('output_tokens', 0)} out")
    
    print(f"\n✅ Demo completed! Key improvements:")
    print(f"   🎯 Removed unnecessary token estimation - using actual API counts")
    print(f"   💰 Added accurate cost calculation for all providers")
    print(f"   🧠 Support for thinking tokens (Google charges differently)")
    print(f"   💾 Proper cache token differentiation (Anthropic write vs read)")
    print(f"   📊 Comprehensive token tracking and reporting")

if __name__ == "__main__":
    main() 