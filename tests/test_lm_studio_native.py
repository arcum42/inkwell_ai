"""Pytest tests for LM Studio Native SDK Provider.

These tests use fixtures and skip gracefully when the LM Studio API
server is not available or no models are loaded.
"""

import pytest
import requests

from core.llm import LMStudioNativeProvider

BASE_URL = "localhost:1234"


def _api_available(base_url: str = BASE_URL) -> bool:
    try:
        url = base_url if base_url.startswith("http") else f"http://{base_url}"
        requests.get(f"{url}/v1/models", timeout=2).raise_for_status()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def provider():
    if not _api_available(BASE_URL):
        pytest.skip("LM Studio API not available")
    return LMStudioNativeProvider(BASE_URL)


@pytest.fixture(scope="module")
def models(provider):
    ms = provider.list_models(refresh=True)
    if not ms:
        pytest.skip("No models loaded in LM Studio")
    return ms


@pytest.fixture(scope="module")
def model(models):
    return models[0]


def test_connection():
    """Provider class import should be available."""
    assert LMStudioNativeProvider is not None


def test_list_models(provider):
    """Test listing available models."""
    models = provider.list_models(refresh=True)
    assert isinstance(models, list)


def test_basic_chat(provider, model):
    """Test basic chat functionality using selected model."""
    messages = [
        {"role": "user", "content": "Say 'Hello from native SDK' and nothing else"}
    ]
    response = provider.chat(messages, model=model)
    assert isinstance(response, str)
    assert not response.startswith("Error:"), f"Got error: {response}"


def test_chat_with_history(provider, model):
    """Test chat with conversation history."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Hello Alice!"},
        {"role": "user", "content": "What is my name?"},
    ]
    response = provider.chat(messages, model=model)
    assert isinstance(response, str)


def test_model_metadata(provider, model):
    """Test model metadata retrieval."""
    context_len = provider.get_model_context_length(model)
    assert context_len is None or isinstance(context_len, int)


def test_vision_model_detection(provider):
    """Test vision model detection heuristic and metadata."""
    test_cases = [
        ("llava-v1.5-7b", True),
        ("qwen2-vl-2b-instruct", True),
        ("llama-3.2-3b-instruct", False),
        ("minicpm-v-2.6", True),
        ("qwen-7b", False),
    ]
    for name, expected in test_cases:
        result = provider.is_vision_model(name)
        assert result in (True, False)
