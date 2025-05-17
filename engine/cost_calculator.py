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

# Web search context size costs (applies to OpenAI only)
OPENAI_SEARCH_CONTEXT_COSTS: Dict[SearchContext, float] = {
    "low": 0.03,    # $30/1k searches
    "medium": 0.035,  # $35/1k searches (default)
    "high": 0.05,   # $50/1k searches
}

""" gemini web search cost info included in this comment

Gemini Developer API Pricing


The Gemini API "free tier" is offered through the API service with lower rate limits for testing purposes. Google AI Studio usage is completely free in all available countries. The Gemini API "paid tier" comes with higher rate limits, additional features, and different data handling.

Upgrade to the Paid Tier
Gemini 2.5 Flash Preview
Try it in Google AI Studio

Our first hybrid reasoning model which supports a 1M token context window and has thinking budgets.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Free of charge	$0.15 (text / image / video)
$1.00 (audio)
Output price	Free of charge	Non-thinking: $0.60
Thinking: $3.50
Context caching price	Not available	$0.0375 (text / image / video)
$0.25 (audio)
$1.00 / 1,000,000 tokens per hour
Grounding with Google Search	Free of charge, up to 500 RPD	1,500 RPD (free), then $35 / 1,000 requests
Used to improve our products	Yes	No
Gemini 2.5 Pro Preview
Try it in Google AI Studio

Our state-of-the-art multipurpose model, which excels at coding and complex reasoning tasks.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Not available	$1.25, prompts <= 200k tokens
$2.50, prompts > 200k tokens
Output price (including thinking tokens)	Not available	$10.00, prompts <= 200k tokens
$15.00, prompts > 200k
Context caching price	Not available	$0.31, prompts <= 200k tokens
$0.625, prompts > 200k
$4.50 / 1,000,000 tokens per hour
Grounding with Google Search	Not available	1,500 RPD (free), then $35 / 1,000 requests

"""

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
        model_name: The name of the model (e.g., 'gpt-image-1', 'imagen-3')
        num_images: Number of images to generate (default: 1)
        size: Image size (e.g., '1024x1024', '1024x1792')
        quality: Image quality ('standard' or 'hd' for GPT-Image-1)
        
    Returns:
        Dictionary containing cost breakdown
    """
    if model_name.startswith('gpt-image-1'):
        # OpenAI GPT-Image-1 models
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
    
    # Calculate search cost
    search_cost_total = 0.0
    search_details = {} # To store details about how search cost was calculated

    if search_queries > 0:
        provider = get_model_provider(model_name)
        search_rate_per_query = 0.0
        
        if provider == 'openai':
            # For OpenAI, use OPENAI_SEARCH_CONTEXT_COSTS based on search_context
            actual_search_context = search_context if search_context in OPENAI_SEARCH_CONTEXT_COSTS else "medium"
            search_rate_per_query = OPENAI_SEARCH_CONTEXT_COSTS[actual_search_context]
            
            search_details = {
                'type': 'openai_web_search',
                'queries': search_queries,
                'context_used': actual_search_context,
                'rate_per_query': search_rate_per_query
            }
            
        elif provider == 'google':
            # For Google (Gemini), prioritize 'search_grounding' cost
            if 'search_grounding' in model_rates:
                search_rate_per_query = model_rates['search_grounding']
            elif 'search_cost' in model_rates: # Fallback to generic search_cost for Google
                search_rate_per_query = model_rates['search_cost']
            else:
                search_rate_per_query = 0.035 # Default Google search cost ($35/1k requests)
            
            search_details = {
                'type': 'google_search_grounding',
                'queries': search_queries,
                'rate_per_query': search_rate_per_query
            }
            
        else: # For 'unknown' provider or if a model has a generic 'search_cost'
            if 'search_cost' in model_rates:
                search_rate_per_query = model_rates['search_cost']
                search_details = {
                    'type': 'generic_search',
                    'queries': search_queries,
                    'rate_per_query': search_rate_per_query
                }
            else:
                search_details = {
                    'type': 'search_not_costed',
                    'queries': search_queries,
                    'reason': 'No search cost defined for model/provider'
                }
        
        search_cost_total = search_queries * search_rate_per_query

    # Calculate image generation cost
    image_cost_total = 0.0
    image_breakdown = None
    if image_generation and isinstance(image_generation, dict):
        image_result = calculate_image_cost(
            model_name=image_generation.get('model', ''),
            num_images=image_generation.get('count', 1),
            size=image_generation.get('size', '1024x1024'),
            quality=image_generation.get('quality', 'standard')
        )
        image_cost_total = image_result.get('total_cost', 0.0)
        image_breakdown = image_result
    
    total_cost = standard_input_cost + cached_input_cost + output_cost + search_cost_total + image_cost_total
    
    # Prepare result dictionary
    cost_breakdown = {
        'model_name': model_name,
        'provider': get_model_provider(model_name),
        'standard_input_tokens': standard_input_tokens,
        'cached_input_tokens': cached_input_tokens,
        'output_tokens': output_tokens,
        'standard_input_cost': round(standard_input_cost, 5),
        'cached_input_cost': round(cached_input_cost, 5),
        'output_cost': round(output_cost, 5),
    }
    
    if search_queries > 0:
        cost_breakdown['search_cost'] = round(search_cost_total, 5)
        cost_breakdown['search_details'] = search_details # Updated to provide more detail
        
    if image_breakdown:
        cost_breakdown['image_generation_cost'] = round(image_cost_total, 5)
        cost_breakdown['image_generation'] = image_breakdown
    
    cost_breakdown['total_cost'] = round(total_cost, 5)
    
    return cost_breakdown

def get_model_provider(model_name: str) -> str:
    """
    Determine the provider for a given model name.
    
    Args:
        model_name: The name of the model
        
    Returns:
        Provider name ('openai', 'google', or 'unknown')
    """
    if 'gpt' in model_name:
        return 'openai'
    elif any(name in model_name for name in ['gemini', 'imagen']):
        return 'google'
    return 'unknown'
