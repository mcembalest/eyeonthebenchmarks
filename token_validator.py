"""
Token validation system for pre-run checking of context limits.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

# Import token counting functions from each provider
from models_openai import count_tokens_openai, get_context_limit_openai
from models_anthropic import count_tokens_anthropic, get_context_limit_anthropic
from models_google import count_tokens_google, get_context_limit_google


def validate_token_limits_with_upload(prompts: List[Dict], pdf_paths: List[str], model_names: List[str]) -> Dict[str, Any]:
    """
    Validate token limits by uploading files first, then counting tokens accurately.
    This function ensures files are uploaded to providers before token counting.
    
    Args:
        prompts: List of prompt dictionaries with 'prompt_text' keys
        pdf_paths: List of PDF file paths
        model_names: List of model names to check
        
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "warnings": List[str],
            "model_results": {
                "model_name": {
                    "actual_tokens": int,
                    "context_limit": int,
                    "will_exceed": bool,
                    "provider": str
                }
            }
        }
    """
    results = {
        "valid": True,
        "warnings": [],
        "model_results": {}
    }
    
    # Convert PDF paths to Path objects
    pdf_path_objects = [Path(path) for path in pdf_paths]
    
    for model_name in model_names:
        try:
            provider = get_provider_from_model(model_name)
            
            # Count tokens for each prompt + all PDFs (ensuring upload first)
            max_tokens_for_model = 0
            
            for prompt in prompts:
                prompt_text = prompt.get('prompt_text', '')
                
                # Prepare content based on provider format
                if provider == "openai":
                    content = [{"type": "input_text", "text": prompt_text}]
                    for pdf_path in pdf_path_objects:
                        content.append({"type": "input_file", "file_path": str(pdf_path)})
                    
                    actual_tokens = count_tokens_openai(content, model_name)
                    context_limit = get_context_limit_openai(model_name)
                    
                elif provider == "anthropic":
                    content = [{"type": "text", "text": prompt_text}]
                    for pdf_path in pdf_path_objects:
                        content.append({"type": "file", "file_path": str(pdf_path)})
                    
                    actual_tokens = count_tokens_anthropic(content, model_name)
                    context_limit = get_context_limit_anthropic(model_name)
                    
                elif provider == "google":
                    # For Google: prepare content with proper format
                    from models_google import prepare_google_content_for_files
                    
                    # Prepare content using the same method as in actual Google model calls
                    contents = prepare_google_content_for_files(prompt_text, pdf_path_objects)
                    
                    actual_tokens = count_tokens_google(contents, model_name)
                    context_limit = get_context_limit_google(model_name)
                    
                else:
                    logging.warning(f"Unknown provider for model {model_name}")
                    continue
                
                # Track the maximum tokens needed for any prompt with this model
                max_tokens_for_model = max(max_tokens_for_model, actual_tokens)
            
            # Check if this model will exceed its context limit
            will_exceed = max_tokens_for_model > context_limit
            
            results["model_results"][model_name] = {
                "actual_tokens": max_tokens_for_model,
                "context_limit": context_limit,
                "will_exceed": will_exceed,
                "provider": provider
            }
            
            if will_exceed:
                results["valid"] = False
                results["warnings"].append(
                    f"{model_name}: {max_tokens_for_model:,} tokens exceeds limit of {context_limit:,} tokens"
                )
                
        except Exception as e:
            logging.error(f"Error validating tokens for model {model_name}: {e}")
            results["warnings"].append(f"{model_name}: Token validation failed - {str(e)}")
            results["valid"] = False
    
    return results


def get_provider_from_model(model_name: str) -> str:
    """
    Determine the provider from a model name.
    
    Args:
        model_name: Model name
        
    Returns:
        Provider name ("openai", "anthropic", or "google")
    """
    model_lower = model_name.lower()
    
    if any(x in model_lower for x in ["gpt", "o3", "o4"]):
        return "openai"
    elif any(x in model_lower for x in ["claude"]):
        return "anthropic"
    elif any(x in model_lower for x in ["gemini"]):
        return "google"
    else:
        # Default to openai for unknown models
        return "openai"


def format_token_validation_message(validation_results: Dict[str, Any]) -> str:
    """
    Format validation results into a user-friendly message.
    
    Args:
        validation_results: Results from validate_token_limits_with_upload()
        
    Returns:
        Formatted message string
    """
    if validation_results["valid"]:
        return "✅ All selected models can handle the provided content within their context limits."
    
    message_parts = ["⚠️ Some models may exceed their context limits:"]
    
    # Group models by whether they'll exceed limits
    exceeding_models = []
    safe_models = []
    
    for model_name, result in validation_results["model_results"].items():
        if result["will_exceed"]:
            exceeding_models.append(f"• {model_name}: {result['actual_tokens']:,} tokens (limit: {result['context_limit']:,})")
        else:
            safe_models.append(f"• {model_name}: {result['actual_tokens']:,} tokens (limit: {result['context_limit']:,})")
    
    if exceeding_models:
        message_parts.append("\n🚫 Models that will likely fail:")
        message_parts.extend(exceeding_models)
    
    if safe_models:
        message_parts.append("\n✅ Models that should work:")
        message_parts.extend(safe_models)
    
    message_parts.append("\n💡 Consider using models with larger context windows or reducing the number of PDF files.")
    
    return "\n".join(message_parts) 