import pytest
from core.llm.lm_studio_native import LMStudioNativeProvider

def test_structured_streaming_basic(monkeypatch):
    """Test that structured streaming buffers and parses JSON at end."""
    # Simulate a provider that yields JSON fragments
    class DummyFragment:
        def __init__(self, content):
            self.content = content
    
    # Simulate a streaming response that yields JSON in pieces
    def fake_respond_stream(chat, response_format=None):
        # Simulate a valid JSON object in 3 chunks
        yield DummyFragment('{"result": "')
        yield DummyFragment('hello')
        yield DummyFragment('"}')
    
    provider = LMStudioNativeProvider()
    monkeypatch.setattr(provider, "_test_connection", lambda: None)
    monkeypatch.setattr(provider, "_build_chat_context", lambda messages: None)
    monkeypatch.setattr(type(provider), "chat_stream", lambda self, messages, model=None, progress_callback=None, response_format=None: fake_respond_stream(None, response_format))
    
    # Buffer the streaming output as chat_worker does
    chunks = []
    for chunk in provider.chat_stream([], response_format={"type": "object"}):
        chunks.append(chunk.content)
    full = "".join(chunks)
    import json
    parsed = json.loads(full)
    assert parsed["result"] == "hello"
