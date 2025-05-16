"""
Cost calculation utilities for different AI model providers.

This module provides functions to calculate costs for various AI model operations,
including text generation, web search, and image generation.
"""
from typing import Dict, Optional, Union, Literal

# Type aliases
SearchContext = Literal["low", "medium", "high"]
ImageQuality = Literal["standard", "hd"]

# Base model costs (per 1M tokens for input/cached/output)
MODEL_COSTS = {
    # OpenAI models
    "gpt-4.1": {"input": 2.00, "cached": 0.50, "output": 8.00, "search_cost": 0.035},
    "gpt-4.1-mini": {"input": 0.40, "cached": 0.10, "output": 1.60, "search_cost": 0.0275},
    "gpt-4.1-nano": {"input": 0.10, "cached": 0.025, "output": 0.40},
    "gpt-4o": {"input": 2.50, "cached": 1.25, "output": 10.00, "search_cost": 0.035},
    "gpt-4o-mini": {"input": 0.15, "cached": 0.075, "output": 0.60, "search_cost": 0.0275},
    
    # Google Gemini models
    "gemini-2.5-flash": {
        "input": 0.15, 
        "cached": 0.0375, 
        "output": 0.60,
        "search_cost": 0.035,
        "search_grounding": 0.035
    },
    "gemini-2.5-pro": {
        "input": 1.25, 
        "cached": 0.31, 
        "output": 10.00,
        "search_cost": 0.035,
        "search_grounding": 0.035
    },
    
    # Default fallback
    "default": {"input": 2.00, "cached": 0.50, "output": 8.00, "search_cost": 0.05},
}

# Web search context size costs (applies to both OpenAI and Google)
SEARCH_CONTEXT_COSTS: Dict[SearchContext, float] = {
    "low": 0.03,    # $30/1k searches
    "medium": 0.035,  # $35/1k searches (default)
    "high": 0.05,   # $50/1k searches
}

# OpenAI DALL-E models (per image)
OPENAI_IMAGE_COSTS = {
    "1024x1024": {
        "standard": 0.04,    # $0.04 per image
        "hd": 0.08,        # $0.08 per image
    },
    "1024x1792": {
        "standard": 0.08,    # $0.08 per image
        "hd": 0.12,        # $0.12 per image
    },
    "1792x1024": {
        "standard": 0.08,    # $0.08 per image
        "hd": 0.12,        # $0.12 per image
    },
}

# Google Imagen 3 model (simple flat rate per image)
GOOGLE_IMAGE_COST = 0.03  # $0.03 per image

def calculate_image_cost(
    model_name: str, 
    num_images: int = 1, 
    size: str = "1024x1024", 
    quality: ImageQuality = "standard"
) -> Dict[str, Union[str, int, float]]:
    """
    Calculate the cost of image generation.
    
    Args:
        model_name: The name of the model (e.g., 'dall-e-3', 'imagen-3')
        num_images: Number of images to generate (default: 1)
        size: Image size (e.g., '1024x1024', '1024x1792')
        quality: Image quality ('standard' or 'hd' for DALL-E)
        
    Returns:
        Dictionary containing cost breakdown
    """
    if model_name.startswith('dall-e'):
        # OpenAI DALL-E models
        if size not in OPENAI_IMAGE_COSTS:
            size = "1024x1024"  # Default to square format
        if quality not in OPENAI_IMAGE_COSTS[size]:
            quality = "standard"  # Default quality
        
        cost_per_image = OPENAI_IMAGE_COSTS[size][quality]
        total_cost = num_images * cost_per_image
        
        return {
            'provider': 'openai',
            'model': model_name,
            'num_images': num_images,
            'size': size,
            'quality': quality,
            'cost_per_image': cost_per_image,
            'total_cost': round(total_cost, 4)
        }
    
    elif model_name == 'imagen-3':
        # Google Imagen 3 (fixed rate per image)
        cost_per_image = GOOGLE_IMAGE_COST
        total_cost = num_images * cost_per_image
        
        return {
            'provider': 'google',
            'model': model_name,
            'num_images': num_images,
            'cost_per_image': cost_per_image,
            'total_cost': round(total_cost, 4)
        }
    
    # Unknown model
    return {
        'provider': 'unknown',
        'model': model_name,
        'num_images': num_images,
        'total_cost': 0.0,
        'error': f"Cost calculation not available for model: {model_name}"
    }

def calculate_cost(
    model_name: str,
    standard_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int, 
    search_queries: int = 0, 
    search_context: SearchContext = "medium",
    image_generation: Optional[dict] = None
) -> Dict[str, Union[float, int, str, dict]]:
    """
    Calculate the estimated cost of operations.
    
    Args:
        model_name: The name of the model used
        standard_input_tokens: Number of standard input tokens used
        cached_input_tokens: Number of cached input tokens used
        output_tokens: Number of output tokens generated
        search_queries: Number of web search queries made
        search_context: Search context size ('low', 'medium', or 'high')
        image_generation: Optional dict with 'model', 'count', 'size', 'quality'
        
    Returns:
        Dictionary containing cost breakdown
    """
    # Get cost rates for the model, or use default if not found
    model_rates = MODEL_COSTS.get(model_name, MODEL_COSTS['default'])
    
    # Calculate token costs
    cached_rate = model_rates.get('cached', model_rates['input'] * 0.5)
    standard_input_cost = (standard_input_tokens / 1_000_000) * model_rates['input']
    cached_input_cost = (cached_input_tokens / 1_000_000) * cached_rate
    output_cost = (output_tokens / 1_000_000) * model_rates['output']
    
    # Calculate search costs if any queries were made
    search_cost = 0.0
    if search_queries > 0:
        search_cost_per_query = model_rates.get('search_cost', 
                                              SEARCH_CONTEXT_COSTS.get(search_context, 0.035))
        search_cost = search_queries * search_cost_per_query
    
    # Calculate image generation costs if any
    image_cost = 0.0
    image_breakdown = None
    if image_generation and isinstance(image_generation, dict):
        image_result = calculate_image_cost(
            model_name=image_generation.get('model', ''),
            num_images=image_generation.get('count', 1),
            size=image_generation.get('size', '1024x1024'),
            quality=image_generation.get('quality', 'standard')
        )
        image_cost = image_result.get('total_cost', 0.0)
        image_breakdown = image_result
    
    total_cost = standard_input_cost + cached_input_cost + output_cost + search_cost + image_cost
    
    # Prepare result dictionary
    result: Dict[str, Union[float, int, str, dict]] = {
        'standard_input_cost': standard_input_cost,
        'cached_input_cost': cached_input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
    }
    
    # Only include these fields if they're non-zero/used
    if search_queries > 0:
        result.update({
            'search_cost': search_cost,
            'search_queries': search_queries,
            'search_context': search_context
        })
    
    if image_breakdown:
        result.update({
            'image_generation_cost': image_cost,
            'image_generation': image_breakdown
        })
    
    # Round all float values for cleaner output
    for key, value in result.items():
        if isinstance(value, float):
            result[key] = round(value, 8)
    
    return result

def get_model_provider(model_name: str) -> str:
    """
    Determine the provider for a given model name.
    
    Args:
        model_name: The name of the model
        
    Returns:
        Provider name ('openai', 'google', or 'unknown')
    """
    if any(name in model_name for name in ['gpt', 'dall-e']):
        return 'openai'
    elif any(name in model_name for name in ['gemini', 'imagen']):
        return 'google'
    return 'unknown'
