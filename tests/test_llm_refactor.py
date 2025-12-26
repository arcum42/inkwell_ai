#!/usr/bin/env python3
"""Pytest: verify LLM provider refactor retains backward compatibility."""

def test_llm_import_paths_and_instantiation():
    """Ensure both new and legacy import paths work and classes match."""
    # New import path
    from core.llm import LLMProvider as LLMProvider_new
    from core.llm import OllamaProvider as OllamaProvider_new
    from core.llm import LMStudioProvider as LMStudioProvider_new

    # Legacy import path
    from core.llm_provider import LLMProvider as LLMProvider_old
    from core.llm_provider import OllamaProvider as OllamaProvider_old
    from core.llm_provider import LMStudioProvider as LMStudioProvider_old

    # Class identity checks
    assert LLMProvider_new is LLMProvider_old
    assert OllamaProvider_new is OllamaProvider_old
    assert LMStudioProvider_new is LMStudioProvider_old

    # Basic instantiation checks (without network calls)
    ollama = OllamaProvider_new(base_url="http://localhost:11434")
    assert type(ollama).__name__ == "OllamaProvider"

    lmstudio = LMStudioProvider_new(base_url="http://localhost:1234")
    assert type(lmstudio).__name__ == "LMStudioProvider"
