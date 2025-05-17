# Import models with error handling
import os
import sys
import logging

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def import_models():
    """Import model lists from provider modules with error handling"""
    models = {}
    has_imports = False

    from engine.models_openai import AVAILABLE_MODELS as OPENAI_MODELS
    models["openai"] = OPENAI_MODELS
    has_imports = True
    logging.info(f"Found {len(OPENAI_MODELS)} OpenAI models")
    
    from engine.models_google import AVAILABLE_MODELS as GOOGLE_MODELS
    models["google"] = GOOGLE_MODELS
    has_imports = True
    logging.info(f"Found {len(GOOGLE_MODELS)} Google models")
    
    # Note: We're not adding hardcoded Anthropic models per user request
    
    return models

def get_all_available_models():
    """
    Returns a dictionary with all available models grouped by provider.
    
    Returns:
        dict: Dictionary with provider names as keys and lists of model names as values
    """
    return import_models()

def get_available_models_as_list():
    """
    Returns a flat list of all available models from all providers.
    
    Returns:
        list: List of all model names
    """
    all_models = []
    models_by_provider = get_all_available_models()
    
    for provider, models in models_by_provider.items():
        all_models.extend(models)
    
    return all_models

if __name__ == "__main__":
    # Print all models when run directly
    import json
    
    # Print both formats - the dictionary by provider and the flat list
    # The main process will try to parse the last valid JSON line
    all_models = get_all_available_models()
    print(json.dumps(all_models))
    
    flat_list = get_available_models_as_list()
    print(json.dumps(flat_list))
