"""Guide to Adding New LLM Providers

This document explains how to add new LLM providers to the inkwell_ai project.
The modular structure makes it easy to add new providers without modifying
existing code.

## Quick Start

To add a new LLM provider:

1. Create a new file in core/llm/ named <provider_name>.py
2. Import the base class: from .base import LLMProvider
3. Create a class inheriting from LLMProvider
4. Implement the required abstract methods
5. Add the import to core/llm/__init__.py
6. Update the __all__ list in __init__.py

## Example: Adding OpenAI Provider

### Step 1: Create core/llm/openai.py

from .base import LLMProvider
import openai

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
    
    def chat(self, messages, model="gpt-4"):
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    
    def list_models(self):
        # Return list of available models
        return ["gpt-4", "gpt-3.5-turbo"]
    
    def get_model_context_length(self, model_name):
        # Return context length in tokens
        if "gpt-4" in model_name:
            return 8192
        return 4096
    
    def is_vision_model(self, model_name):
        # Override if provider has different vision models
        return "gpt-4-vision" in model_name

### Step 2: Update core/llm/__init__.py

from .base import LLMProvider
from .ollama import OllamaProvider
from .lm_studio import LMStudioProvider
from .openai import OpenAIProvider  # Add this line

__all__ = [
    'LLMProvider',
    'OllamaProvider',
    'LMStudioProvider',
    'OpenAIProvider',  # Add this line
]

### Step 3: Use the new provider

from core.llm import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
response = provider.chat([{"role": "user", "content": "Hello"}])

## Abstract Methods to Implement

All providers must implement these methods from LLMProvider:

### chat(messages, model=None) -> str
Send a chat message to the LLM.

Args:
    messages: List of message dicts with 'role' and 'content' keys
              Example: [{"role": "user", "content": "Hello"}]
              Vision images can be attached as additional fields
    model: Model name to use (provider-specific)

Returns:
    String response from the model

### list_models() -> List[str]
List available models from the provider.

Returns:
    List of model names/identifiers

### get_model_context_length(model_name) -> Optional[int]
Get the context length (token limit) for a model.

Args:
    model_name: Name of the model

Returns:
    Context length in tokens, or None if unknown

### is_vision_model(model_name) -> bool
Detect if a model supports vision inputs.

Args:
    model_name: Name of the model

Returns:
    True if the model supports vision inputs

## Base Class Helper Methods

The LLMProvider base class provides:

- is_vision_model(model_name) - Default implementation using keyword heuristics
  - Looks for keywords: 'vision', 'llava', 'moondream', etc.
  - Can be overridden by subclasses for provider-specific detection
  - Call super().is_vision_model(model_name) for fallback

## Current Providers

### OllamaProvider
- **Location:** core/llm/ollama.py
- **Service:** Ollama (localhost:11434)
- **Models:** Any model available in Ollama
- **Features:** Vision image support, model metadata retrieval

### LMStudioProvider
- **Location:** core/llm/lm_studio.py
- **Service:** LM Studio (localhost:1234, OpenAI-compatible API)
- **Models:** Any model loaded in LM Studio
- **Features:** Vision image support via OpenAI format, context overflow detection
- **Note:** Uses OpenAI-compatible API, not official LM Studio SDK

## Future Improvements

When redesigning LMStudioProvider in the future:

1. Create a new file: core/llm/lm_studio_v2.py
2. Implement the new provider class
3. Update core/llm/__init__.py to import the new class
4. Old LMStudioProvider can be kept, renamed to LMStudioProvider_legacy, or removed
5. No changes needed to other code that uses the interface

The abstract base class ensures any provider replacement maintains compatibility.

## Testing New Providers

Create a test file following the pattern of test_llm_refactor.py:

from core.llm import MyNewProvider

def test_imports():
    provider = MyNewProvider(...)
    assert provider is not None
    
    # Test required methods
    models = provider.list_models()
    assert isinstance(models, list)
    
    context = provider.get_model_context_length(models[0])
    # context should be int or None
    
    is_vision = provider.is_vision_model(models[0])
    assert isinstance(is_vision, bool)

## Import Paths

After adding a new provider to __all__, it's accessible through both:

# Direct import (preferred)
from core.llm import MyNewProvider

# Module import
from core.llm.my_new_provider import MyNewProvider

## Summary

The LLM provider system is designed for:
✅ Easy addition of new providers
✅ Independent testing of each provider
✅ Consistent interface across all providers
✅ Backward compatibility when replacing providers
✅ Clear separation of concerns

"""
