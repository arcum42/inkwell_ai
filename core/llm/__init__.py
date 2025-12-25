"""LLM Provider module for handling different LLM backends.

This module provides an abstract interface (LLMProvider) with concrete implementations
for different local LLM services:
- OllamaProvider: For Ollama (default on localhost:11434)
- LMStudioProvider: For LM Studio OpenAI-compatible API (default on localhost:1234)
- LMStudioNativeProvider: For LM Studio native Python SDK (default on localhost:1234)

Usage:
    from core.llm import OllamaProvider, LMStudioProvider, LMStudioNativeProvider
    
    ollama_provider = OllamaProvider()
    response = ollama_provider.chat([{"role": "user", "content": "Hello"}])
"""

from .base import LLMProvider
from .ollama import OllamaProvider
from .lm_studio import LMStudioProvider
from .lm_studio_native import LMStudioNativeProvider

__all__ = [
    'LLMProvider',
    'OllamaProvider',
    'LMStudioProvider',
    'LMStudioNativeProvider',
]
