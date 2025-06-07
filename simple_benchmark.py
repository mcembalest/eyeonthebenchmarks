
import argparse
import sys
import os
import json
import logging
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Set up minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_models_available():
    """Import model modules and check API keys"""
    try:
        from models_openai import openai_ask_with_files, AVAILABLE_MODELS as OPENAI_MODELS
        from models_anthropic import anthropic_ask_with_files, AVAILABLE_MODELS as ANTHROPIC_MODELS  
        from models_google import google_ask_with_files, AVAILABLE_MODELS as GOOGLE_MODELS
        return {
            'openai': (openai_ask_with_files, OPENAI_MODELS),
            'anthropic': (anthropic_ask_with_files, ANTHROPIC_MODELS),
            'google': (google_ask_with_files, GOOGLE_MODELS)
        }
    except ImportError as e:
        logger.error(f"Failed to import model modules: {e}")
        sys.exit(1)

def get_provider_from_model(model_name: str) -> str:
    """Determine provider from model name"""
    if model_name.startswith("gpt-") or model_name.startswith("o3") or model_name.startswith("o4"):
        return "openai"
    elif model_name.startswith("claude-"):
        return "anthropic"
    elif model_name.startswith("gemini-"):
        return "google"
    else:
        raise ValueError(f"Unknown model provider for: {model_name}")

def check_api_keys(provider: str) -> bool:
    """Check if API key is available for provider"""
    key_map = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY', 
        'google': 'GOOGLE_API_KEY'
    }
    
    key = os.environ.get(key_map.get(provider))
    if not key:
        logger.error(f"Missing API key for {provider}. Please set {key_map.get(provider)} environment variable.")
        return False
    return True

def validate_files(file_paths: List[Path]) -> List[Path]:
    """Validate that all files exist and are readable"""
    valid_files = []
    for file_path in file_paths:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            continue
        if not file_path.is_file():
            logger.error(f"Not a file: {file_path}")
            continue
        
        # Check file size (32MB limit)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 32:
            logger.error(f"File too large ({file_size_mb:.1f}MB): {file_path}")
            continue
            
        valid_files.append(file_path)
    
    return valid_files

def format_model_display_name(model_name: str) -> str:
    """Format model name for display, adding thinking suffix if applicable"""
    if model_name.endswith('-thinking'):
        base_name = model_name.replace('-thinking', '')
        return f"{base_name} (+ Thinking)"
    return model_name

def export_results_to_csv(results: List[Dict], output_file: Path, benchmark_name: str = None) -> bool:
    """Export results to CSV in the same format as the main app"""
    try:
        # Define the exact column order from the main app
        cols_order = [
            # Metadata
            'benchmark_name', 'model_name', 'provider', 'files_used', 'file_count',
            # Content
            'prompt_text', 'model_answer', 'latency',
            # Token breakdown
            'standard_input_tokens', 'cached_input_tokens', 'output_tokens',
            'thinking_tokens', 'reasoning_tokens',
            # Cost breakdown  
            'input_cost', 'cached_cost', 'output_cost', 
            'thinking_cost', 'reasoning_cost', 'total_cost',
            # Web search
            'web_search_used', 'web_search_sources',
            # New formatted model display name
            'model_display_name'
        ]
        
        # Prepare data for CSV
        csv_data = []
        for result in results:
            if not result.get('success'):
                continue  # Skip failed results
                
            # Extract data from result
            model_name = result.get('model', '')
            provider = result.get('provider', '')
            prompt_text = result.get('prompt', '')
            model_answer = result.get('answer', '')
            tokens = result.get('tokens', {})
            web_search = result.get('web_search', {})
            files_used = result.get('files_used', [])
            
            # Prepare files information
            files_used_str = '; '.join([Path(f).name for f in files_used]) if files_used else ''
            file_count = len(files_used)
            
            # Format web search data
            web_search_used = str(web_search.get('used', False))
            web_search_sources = web_search.get('sources', '')
            
            # Create row data
            row_data = {
                # Metadata
                'benchmark_name': benchmark_name or f"Simple Benchmark {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                'model_name': model_name,
                'provider': provider,
                'files_used': files_used_str,
                'file_count': file_count,
                
                # Content
                'prompt_text': prompt_text,
                'model_answer': model_answer,
                'latency': 0,  # Simple script doesn't track latency per prompt
                
                # Token breakdown
                'standard_input_tokens': tokens.get('input', 0),
                'cached_input_tokens': tokens.get('cached', 0),
                'output_tokens': tokens.get('output', 0),
                'thinking_tokens': tokens.get('thinking', 0),
                'reasoning_tokens': 0,  # Not used in simple script
                
                # Cost breakdown (simple script doesn't calculate costs)
                'input_cost': 0.0,
                'cached_cost': 0.0,
                'output_cost': 0.0,
                'thinking_cost': 0.0,
                'reasoning_cost': 0.0,
                'total_cost': 0.0,
                
                # Web search
                'web_search_used': web_search_used,
                'web_search_sources': web_search_sources,
                
                # Formatted model display name
                'model_display_name': format_model_display_name(model_name)
            }
            
            csv_data.append(row_data)
        
        if not csv_data:
            logger.warning("No successful results to export to CSV")
            return False
        
        # Create DataFrame and export to CSV
        df = pd.DataFrame(csv_data)
        
        # Ensure all required columns are present (add missing with defaults)
        for col in cols_order:
            if col not in df.columns:
                if col in ['latency', 'standard_input_tokens', 'cached_input_tokens', 'output_tokens', 
                          'thinking_tokens', 'reasoning_tokens', 'file_count']:
                    df[col] = 0
                elif col in ['input_cost', 'cached_cost', 'output_cost', 'thinking_cost', 
                            'reasoning_cost', 'total_cost']:
                    df[col] = 0.0
                else:
                    df[col] = ''
        
        # Reorder columns to match main app
        df = df[cols_order]
        
        # Export to CSV
        df.to_csv(output_file, index=False)
        
        logger.info(f"Exported {len(csv_data)} results to CSV: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False

def load_prompts_from_file(prompts_file: Path) -> List[str]:
    """Load prompts from a text file (one per line)"""
    if not prompts_file.exists():
        logger.error(f"Prompts file not found: {prompts_file}")
        sys.exit(1)
    
    try:
        with open(prompts_file, 'r', encoding='utf-8') as f:
            prompts = [line.strip() for line in f if line.strip()]
        
        if not prompts:
            logger.error("No prompts found in file")
            sys.exit(1)
            
        logger.info(f"Loaded {len(prompts)} prompts from {prompts_file}")
        return prompts
        
    except Exception as e:
        logger.error(f"Error reading prompts file: {e}")
        sys.exit(1)

def run_single_prompt(prompt: str, model_name: str, pdf_paths: List[Path], 
                     web_search: bool, models_dict: Dict) -> Dict[str, Any]:
    """Run a single prompt against the model"""
    provider = get_provider_from_model(model_name)
    
    if not check_api_keys(provider):
        return {"error": f"Missing API key for {provider}"}
    
    ask_function, available_models = models_dict[provider]
    
    if model_name not in available_models:
        return {"error": f"Model {model_name} not available for {provider}"}
    
    logger.info(f"Running prompt with {provider} model: {model_name}")
    logger.info(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if pdf_paths:
        logger.info(f"PDFs: {[p.name for p in pdf_paths]}")
    if web_search:
        logger.info("Web search: ENABLED")
    
    try:
        # Call the appropriate model function
        # All model functions return: (answer, input_tokens, cached_tokens, output_tokens, thinking_tokens, web_search_used, web_search_sources)
        result = ask_function(pdf_paths, prompt, model_name, Path.cwd(), web_search)
        
        # Unpack result
        answer, input_tokens, cached_tokens, output_tokens, thinking_tokens, web_search_used, web_search_sources = result
        
        # Calculate total tokens
        total_tokens = (input_tokens or 0) + (cached_tokens or 0) + (output_tokens or 0)
        
        return {
            "success": True,
            "model": model_name,
            "provider": provider,
            "prompt": prompt,
            "answer": answer,
            "tokens": {
                "input": input_tokens or 0,
                "cached": cached_tokens or 0, 
                "output": output_tokens or 0,
                "thinking": thinking_tokens or 0,
                "total": total_tokens
            },
            "web_search": {
                "requested": web_search,
                "used": web_search_used,
                "sources": web_search_sources
            },
            "files_used": [str(p) for p in pdf_paths]
        }
        
    except Exception as e:
        logger.error(f"Error running prompt: {e}")
        return {
            "success": False,
            "error": str(e),
            "model": model_name,
            "provider": provider,
            "prompt": prompt
        }

def main():
    parser = argparse.ArgumentParser(description="Simple Benchmark Script")
    
    # Prompt options (mutually exclusive)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", type=str, help="Single prompt to run")
    prompt_group.add_argument("--prompts-file", type=Path, help="File containing prompts (one per line)")
    
    # Model selection
    parser.add_argument("--models", nargs="*", type=str, 
                       default=["o3", "claude-opus-4-20250514-thinking", "gemini-2.5-pro-preview-06-05"],
                       help="Models to use (default: o3, claude-opus-4-thinking, gemini-2.5-pro)")
    parser.add_argument("--model", type=str, help="Single model to use (overrides --models)")
    
    # File inputs
    parser.add_argument("--pdfs", nargs="*", type=Path, default=[], 
                       help="PDF files to include in context")
    
    # Web search
    parser.add_argument("--web-search", action="store_true", 
                       help="Enable web search for prompts")
    
    # Output options
    parser.add_argument("--output", type=Path, help="Save results to JSON file")
    parser.add_argument("--csv", type=Path, help="Export results to CSV file")
    parser.add_argument("--no-auto-csv", action="store_true", help="Disable automatic CSV export")
    parser.add_argument("--benchmark-name", type=str, help="Name for the benchmark (used in CSV)")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Load model functions
    models_dict = ensure_models_available()
    
    # Validate PDFs
    pdf_paths = validate_files(args.pdfs) if args.pdfs else []
    
    # Get prompts
    if args.prompt:
        prompts = [args.prompt]
    else:
        prompts = load_prompts_from_file(args.prompts_file)
    
    # Get models list
    if args.model:
        models = [args.model]
    else:
        models = args.models
    
    # Validate all models and their API keys
    for model in models:
        provider = get_provider_from_model(model)
        if not check_api_keys(provider):
            sys.exit(1)
    
    # Run benchmarks
    results = []
    total_combinations = len(prompts) * len(models)
    
    combination_count = 0
    for i, prompt in enumerate(prompts, 1):
        for j, model in enumerate(models, 1):
            combination_count += 1
            if not args.quiet:
                print(f"\n[{combination_count}/{total_combinations}] Running prompt {i}/{len(prompts)} with model {j}/{len(models)} ({model})...")
            
            result = run_single_prompt(prompt, model, pdf_paths, args.web_search, models_dict)
            results.append(result)
            
            # Print result
            if result.get("success"):
                if not args.quiet:
                    print(f"✅ Success")
                    print(f"Answer: {result['answer'][:200]}{'...' if len(result['answer']) > 200 else ''}")
                    print(f"Tokens: {result['tokens']['total']} (in: {result['tokens']['input']}, out: {result['tokens']['output']})")
                    if result['web_search']['used']:
                        print(f"Web search: Used ({len(result['web_search']['sources'])} sources)")
                else:
                    print(f"[{combination_count}/{total_combinations}] ✅ {model}")
            else:
                print(f"❌ Error ({model}): {result.get('error')}")
    
    # Save JSON results if requested
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to: {args.output}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    # Export to CSV (either specified file or auto-generated)
    csv_exported = False
    if not args.no_auto_csv:
        # Determine CSV filename
        if args.csv:
            csv_file = args.csv
        else:
            # Auto-generate CSV filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            benchmark_name = args.benchmark_name or "simple_benchmark"
            safe_name = "".join(c for c in benchmark_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            csv_file = Path(f"{safe_name}_{timestamp}.csv")
        
        # Export to CSV
        benchmark_name = args.benchmark_name or f"Simple Benchmark {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        csv_exported = export_results_to_csv(results, csv_file, benchmark_name)
        
        if csv_exported and not args.quiet:
            print(f"\n📊 Results exported to CSV: {csv_file}")
    elif args.csv:
        # Manual CSV export requested even with --no-auto-csv
        benchmark_name = args.benchmark_name or f"Simple Benchmark {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        csv_exported = export_results_to_csv(results, args.csv, benchmark_name)
        
        if csv_exported and not args.quiet:
            print(f"\n📊 Results exported to CSV: {args.csv}")
    
    # Summary
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful
    
    if not args.quiet:
        print(f"\n=== SUMMARY ===")
        print(f"Total combinations: {len(results)} ({len(prompts)} prompts × {len(models)} models)")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if successful > 0:
            total_tokens = sum(r.get('tokens', {}).get('total', 0) for r in results if r.get('success'))
            print(f"Total tokens used: {total_tokens}")
            
            # Summary by model
            model_stats = {}
            for result in results:
                if result.get('success'):
                    model = result['model']
                    if model not in model_stats:
                        model_stats[model] = {'count': 0, 'tokens': 0}
                    model_stats[model]['count'] += 1
                    model_stats[model]['tokens'] += result.get('tokens', {}).get('total', 0)
            
            print(f"\nBy model:")
            for model, stats in model_stats.items():
                print(f"  {model}: {stats['count']} successful, {stats['tokens']} tokens")
    
    # Exit with error code if any failed
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()