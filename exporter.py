"""
CSV Export functionality

This module provides functions to export benchmark results to CSV format,
allowing users to easily analyze results and create charts in external tools.
"""

import csv
import os
from pathlib import Path
import datetime
from file_store import load_benchmark_details, load_all_benchmarks_with_models

def export_benchmark_to_csv(benchmark_id: int, output_dir: Path = None) -> str:
    """
    Export a benchmark's results to a CSV file.
    
    Args:
        benchmark_id: The ID of the benchmark to export
        output_dir: Optional directory to save the CSV file (defaults to current working directory)
    
    Returns:
        Path to the generated CSV file
    """
    # Get benchmark details including all runs and prompts
    benchmark_details = load_all_benchmarks_with_models()
    
    # Find the benchmark with the given ID
    benchmark = None
    for b in benchmark_details:
        if b['id'] == benchmark_id:
            benchmark = b
            break
    
    if not benchmark:
        raise ValueError(f"Benchmark with ID {benchmark_id} not found")
    
    # Get detailed benchmark data with prompts
    detailed_data = load_benchmark_details(benchmark_id)
    if not detailed_data:
        raise ValueError(f"Could not load detailed data for benchmark ID {benchmark_id}")
    
    # Create output directory if not specified
    if not output_dir:
        output_dir = Path.cwd() / "exports"
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_label = benchmark.get('label', f"benchmark_{benchmark_id}").replace(" ", "_").replace("/", "-")
    filename = f"{sanitized_label}_{timestamp}.csv"
    filepath = output_dir / filename
    
    # Get all model names for this benchmark
    model_names = benchmark.get('model_names', [])
    
    # Format for CSV export depends on what we want to show
    # 1. Summary per model
    export_benchmark_summary(benchmark, filepath)
    
    # 2. Detailed per-prompt results
    # For each prompt, show results across all models (side by side comparison)
    detailed_filepath = output_dir / f"{sanitized_label}_detailed_{timestamp}.csv"
    export_benchmark_detailed(benchmark_id, model_names, detailed_filepath)
    
    return str(filepath)

def export_benchmark_summary(benchmark: dict, filepath: Path) -> None:
    """Export summary statistics for each model in the benchmark."""
    model_results = benchmark.get('model_results', {})
    model_names = list(model_results.keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Metric'] + model_names
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Write rows for each metric (MVP - no scores)
        metrics = {
            'Latency (seconds)': 'latency',
            'Standard Input Tokens': 'standard_input_tokens',
            'Cached Input Tokens': 'cached_input_tokens', 
            'Output Tokens': 'output_tokens',
            'Total Tokens': 'total_tokens',
            'Estimated Cost ($)': 'cost'
        }
        
        for metric_name, metric_key in metrics.items():
            row = {'Metric': metric_name}
            for model_name in model_names:
                if model_name in model_results:
                    value = model_results[model_name].get(metric_key, 'N/A')
                    # Format numeric values nicely
                    if isinstance(value, (int, float)):
                        if metric_key == 'cost':
                            value = f"{value:.4f}"
                        elif 'tokens' in metric_key:
                            value = f"{value:,}"
                        else:
                            value = f"{value:.2f}"
                    row[model_name] = value
                else:
                    row[model_name] = 'N/A'
            writer.writerow(row)
        
        # Add benchmark metadata
        writer.writerow({'Metric': '---', **{model: '---' for model in model_names}})
        writer.writerow({'Metric': 'Benchmark ID', **{model: benchmark.get('id', 'N/A') for model in model_names}})
        writer.writerow({'Metric': 'Benchmark Label', **{model: benchmark.get('label', 'N/A') for model in model_names}})
        writer.writerow({'Metric': 'File Paths', **{model: ', '.join(benchmark.get('file_paths', [])) for model in model_names}})
        writer.writerow({'Metric': 'Created', **{model: benchmark.get('timestamp', 'N/A') for model in model_names}})

def export_benchmark_detailed(benchmark_id: int, model_names: list, filepath: Path) -> None:
    """Export detailed per-prompt results for all models in the benchmark (MVP - no expected answers or scores)."""
    # Get detailed data for the benchmark once
    benchmark_data = load_benchmark_details(benchmark_id)
    if not benchmark_data or 'prompts_by_model' not in benchmark_data:
        return
    
    # Get all unique prompts across all models (only prompt text, no expected answers)
    all_prompts = set()
    for model_name, prompts in benchmark_data['prompts_by_model'].items():
        for prompt in prompts:
            all_prompts.add(prompt.get('prompt_text', ''))
    
    # Convert to list and sort for consistent ordering
    all_prompts = sorted(list(all_prompts))
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        # Create fields for CSV (MVP - no expected answers or scores)
        fieldnames = ['Prompt']
        for model in model_names:
            fieldnames.extend([
                f"{model} - Response",
                f"{model} - Standard Input Tokens",
                f"{model} - Cached Input Tokens",
                f"{model} - Output Tokens",
                f"{model} - Latency (ms)"
            ])
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write data for each prompt
        for prompt_text in all_prompts:
            row = {
                'Prompt': prompt_text
            }
            
            # Add data for each model
            for model in model_names:
                model_prompts = benchmark_data['prompts_by_model'].get(model, [])
                prompt_data = next(
                    (p for p in model_prompts 
                     if p.get('prompt_text') == prompt_text),
                    {}
                )
                
                # Extract metrics (MVP - no expected answers or scores)
                row[f"{model} - Response"] = prompt_data.get('model_answer', prompt_data.get('response', 'N/A'))
                row[f"{model} - Standard Input Tokens"] = prompt_data.get('standard_input_tokens', 'N/A')
                row[f"{model} - Cached Input Tokens"] = prompt_data.get('cached_input_tokens', 'N/A')
                row[f"{model} - Output Tokens"] = prompt_data.get('output_tokens', 'N/A')
                row[f"{model} - Latency (ms)"] = prompt_data.get('prompt_latency', 'N/A')
            
            writer.writerow(row)

def export_all_benchmarks_to_csv(output_dir: Path = None) -> list[str]:
    """
    Export all benchmarks to CSV files.
    
    Args:
        output_dir: Optional directory to save the CSV files (defaults to current working directory)
    
    Returns:
        List of paths to the generated CSV files
    """
    benchmark_details = load_all_benchmarks_with_models()
    
    csv_files = []
    for benchmark in benchmark_details:
        benchmark_id = benchmark.get('id')
        if benchmark_id:
            try:
                csv_file = export_benchmark_to_csv(benchmark_id, output_dir)
                csv_files.append(csv_file)
            except Exception as e:
                print(f"Error exporting benchmark {benchmark_id}: {e}")
    
    return csv_files
