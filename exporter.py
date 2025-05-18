"""
CSV Export functionality for EOTM Benchmark results.

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
        
        # Write rows for each metric
        metrics = {
            'Average Score (%)': 'score',
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
                    if isinstance(value, (int, float)) and metric_key != 'score':
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
    """Export detailed per-prompt results for all models in the benchmark."""
    # Get detailed data for each model
    model_data = {}
    for model_name in model_names:
        # Load detailed data with prompts for this benchmark and model
        detailed = load_benchmark_details(benchmark_id)
        if detailed and 'prompts_data' in detailed:
            model_data[model_name] = detailed['prompts_data']
    
    # Bail if we don't have any prompt data
    if not model_data or not any(model_data.values()):
        return
    
    # Get list of prompts - assuming the first model has all prompts
    # This may need to be updated if models can have different prompt sets
    first_model = next(iter(model_data.values()))
    prompts = [p.get('prompt_text', '') for p in first_model]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        # Create fields for CSV
        fieldnames = ['Prompt', 'Expected Answer']
        for model in model_names:
            fieldnames.extend([
                f"{model} - Actual Answer",
                f"{model} - Score",
                f"{model} - Standard Input Tokens",
                f"{model} - Cached Input Tokens",
                f"{model} - Output Tokens",
                f"{model} - Latency (ms)"
            ])
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write data for each prompt
        for i, prompt in enumerate(prompts):
            expected_answer = first_model[i].get('expected_answer', '') if i < len(first_model) else ''
            row = {
                'Prompt': prompt,
                'Expected Answer': expected_answer
            }
            
            # Add data for each model
            for model in model_names:
                if model in model_data and i < len(model_data[model]):
                    prompt_data = model_data[model][i]
                    
                    # Extract metrics
                    row[f"{model} - Actual Answer"] = prompt_data.get('actual_answer', 'N/A')
                    row[f"{model} - Score"] = prompt_data.get('score', 'N/A')
                    row[f"{model} - Standard Input Tokens"] = prompt_data.get('standard_input_tokens', 'N/A')
                    row[f"{model} - Cached Input Tokens"] = prompt_data.get('cached_input_tokens', 'N/A')
                    row[f"{model} - Output Tokens"] = prompt_data.get('output_tokens', 'N/A')
                    row[f"{model} - Latency (ms)"] = prompt_data.get('latency_ms', 'N/A')
                else:
                    # Set N/A for models without data for this prompt
                    row[f"{model} - Actual Answer"] = 'N/A'
                    row[f"{model} - Score"] = 'N/A'
                    row[f"{model} - Standard Input Tokens"] = 'N/A'
                    row[f"{model} - Cached Input Tokens"] = 'N/A'
                    row[f"{model} - Output Tokens"] = 'N/A'
                    row[f"{model} - Latency (ms)"] = 'N/A'
            
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
