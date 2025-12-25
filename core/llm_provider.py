"""Backward compatibility wrapper for LLM provider imports.

This module maintains backward compatibility with code using the old import path:
    from core.llm_provider import LLMProvider, OllamaProvider, LMStudioProvider

The actual implementations are now in the core.llm module:
    from core.llm import LLMProvider, OllamaProvider, LMStudioProvider

This wrapper file is deprecated and will be removed in a future version.
Please update your imports to use core.llm directly.
"""

# Import from the new modular location and re-export for backward compatibility
from core.llm import (
    LLMProvider,
    OllamaProvider,
    LMStudioProvider,
)

__all__ = [
    'LLMProvider',
    'OllamaProvider',
    'LMStudioProvider',
]
