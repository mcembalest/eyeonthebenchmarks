"""
Token Management Module

This module handles token validation and budget management for different AI models.
It provides functionality to validate that inputs don't exceed model context limits
and processes CSV files with token-aware truncation.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from token_validator import validate_token_limits_with_upload, format_token_validation_message


class TokenManager:
    """Manages token validation and budget calculations for AI models."""
    
    def __init__(self):
        """Initialize the TokenManager."""
        pass
    
    def validate_tokens(self, prompts: List[Dict], pdfPaths: List[str], modelNames: List[str]) -> Dict[str, Any]:
        """
        Validate that prompts + PDFs don't exceed context limits for the selected models.
        
        Args:
            prompts: List of prompt dictionaries with 'prompt_text' keys
            pdfPaths: List of PDF file paths
            modelNames: List of model names to check
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Validate inputs
            if not prompts:
                return {"status": "error", "message": "No prompts provided"}
            if not modelNames:
                return {"status": "error", "message": "No models provided"}
            
            # Run token validation
            validation_results = validate_token_limits_with_upload(prompts, pdfPaths or [], modelNames)
            
            return {
                "status": "success",
                "validation_results": validation_results,
                "formatted_message": format_token_validation_message(validation_results)
            }
            
        except Exception as e:
            logging.error(f"Error validating tokens: {str(e)}")
            return {"status": "error", "message": f"Token validation failed: {str(e)}"}

    def get_model_token_budget(self, model_name: str) -> int:
        """Get the token budget for a specific model (context limit minus buffer)."""
        model_budgets = {
            # OpenAI models
            'gpt-4o': 120000,  # 128k - 8k buffer
            'gpt-4o-mini': 120000,  # 128k - 8k buffer
            'gpt-4.1': 120000,  # 128k - 8k buffer
            'gpt-4.1-mini': 120000,  # 128k - 8k buffer
            'o3': 120000,  # 128k - 8k buffer
            'o4-mini': 120000,  # 128k - 8k buffer
            
            # Anthropic models
            'claude-opus-4-20250514': 190000,  # 200k - 10k buffer
            'claude-opus-4-20250514-thinking': 190000,
            'claude-sonnet-4-20250514': 190000,
            'claude-sonnet-4-20250514-thinking': 190000,
            'claude-3-7-sonnet-20250219': 190000,
            'claude-3-7-sonnet-20250219-thinking': 190000,
            'claude-3-5-haiku-20241022': 190000,
            
            # Google models
            'gemini-2.5-flash-preview-05-20': 990000,  # 1M - 10k buffer
            'gemini-2.5-pro-preview-05-06': 990000,
        }
        
        return model_budgets.get(model_name, 120000)  # Default to GPT-4o budget

    def process_csv_for_model(self, csv_file_path: str, model_name: str) -> Dict[str, Any]:
        """
        Process CSV file for a specific model, applying token budget limits.
        
        Returns:
            Dict with 'data' (markdown string), 'truncation_info', 'included_rows', 'total_rows'
        """
        try:
            from file_store import parse_csv_to_markdown_format, estimate_markdown_tokens
            
            # Get model's token budget
            token_budget = self.get_model_token_budget(model_name)
            
            # Parse full CSV
            csv_data = parse_csv_to_markdown_format(Path(csv_file_path))
            total_rows = csv_data['total_rows']
            
            # Estimate tokens for full dataset
            full_tokens = estimate_markdown_tokens(csv_data['markdown_data'])
            
            if full_tokens <= token_budget:
                # No truncation needed
                return {
                    'data': csv_data['markdown_data'],
                    'truncation_info': None,
                    'included_rows': total_rows,
                    'total_rows': total_rows,
                    'estimated_tokens': full_tokens
                }
            
            # Need to truncate - binary search for optimal row count
            left, right = 1, total_rows
            best_rows = 1
            
            while left <= right:
                mid = (left + right) // 2
                subset_data = parse_csv_to_markdown_format(Path(csv_file_path), max_rows=mid)
                subset_tokens = estimate_markdown_tokens(subset_data['markdown_data'])
                
                if subset_tokens <= token_budget:
                    best_rows = mid
                    left = mid + 1
                else:
                    right = mid - 1
            
            # Get the final truncated data
            truncated_data = parse_csv_to_markdown_format(Path(csv_file_path), max_rows=best_rows)
            final_tokens = estimate_markdown_tokens(truncated_data['markdown_data'])
            
            # Create truncation info
            truncation_info = {
                'csv_truncations': [{
                    'file_name': Path(csv_file_path).name,
                    'original_rows': total_rows,
                    'included_rows': best_rows,
                    'token_budget': token_budget,
                    'actual_tokens': final_tokens,
                    'strategy': 'first_n_rows',
                    'model': model_name
                }]
            }
            
            return {
                'data': truncated_data['markdown_data'],
                'truncation_info': truncation_info,
                'included_rows': best_rows,
                'total_rows': total_rows,
                'estimated_tokens': final_tokens
            }
            
        except Exception as e:
            logging.error(f"Error processing CSV for model {model_name}: {e}")
            raise