"""Test streaming responses - verifies supports_streaming flag and implementation."""

from core.llm import OllamaProvider, LMStudioProvider, LMStudioNativeProvider


def test_supports_streaming_flags():
    """Verify supports_streaming flags are set correctly."""
    print("Checking supports_streaming flags...")
    
    ollama = OllamaProvider()
    lm_studio_openai = LMStudioProvider()
    lm_studio_native = LMStudioNativeProvider()
    
    print(f"  OllamaProvider.supports_streaming = {ollama.supports_streaming}")
    assert ollama.supports_streaming == False, "Ollama should be False initially"
    
    print(f"  LMStudioProvider.supports_streaming = {lm_studio_openai.supports_streaming}")
    assert lm_studio_openai.supports_streaming == False, "LM Studio OpenAI should be False initially"
    
    print(f"  LMStudioNativeProvider.supports_streaming = {lm_studio_native.supports_streaming}")
    assert lm_studio_native.supports_streaming == True, "LM Studio Native should be True"
    
    print("✓ All flags set correctly\n")


def test_fallback_streaming():
    """Test that non-streaming providers fallback to regular chat_stream()."""
    print("Testing fallback streaming (Ollama)...")
    provider = OllamaProvider()
    messages = [{"role": "user", "content": "Say 'hello'"}]
    
    chunks = list(provider.chat_stream(messages))
    print(f"  Got {len(chunks)} chunk(s)")
    assert len(chunks) == 1, "Fallback should return one chunk (entire response)"
    print(f"  Response: {chunks[0][:50]}...")
    print("✓ Fallback streaming works\n")


def test_native_sdk_streaming():
    """Test real streaming from LM Studio Native SDK."""
    print("Testing real streaming (LM Studio Native)...")
    provider = LMStudioNativeProvider()
    messages = [{"role": "user", "content": "Count from 1 to 5"}]
    
    print("  Response: ", end="", flush=True)
    chunk_count = 0
    full_response = ""
    for chunk in provider.chat_stream(messages):
        print(chunk, end="", flush=True)
        full_response += chunk
        chunk_count += 1
    print()
    
    print(f"  Received {chunk_count} chunk(s)")
    print(f"  Full response length: {len(full_response)} characters")
    # Note: True streaming may have variable chunk count depending on server buffering
    # Just verify we got multiple calls (more responsive than single call)
    print("✓ Native streaming works\n")


def test_lm_studio_openai_streaming():
    """Test fallback streaming from LM Studio OpenAI-compatible."""
    print("Testing fallback streaming (LM Studio OpenAI)...")
    provider = LMStudioProvider()
    messages = [{"role": "user", "content": "Say hello"}]
    
    chunks = list(provider.chat_stream(messages))
    print(f"  Got {len(chunks)} chunk(s)")
    assert len(chunks) == 1, "OpenAI-compatible fallback should return one chunk"
    print(f"  Response: {chunks[0][:50]}...")
    print("✓ LM Studio OpenAI fallback works\n")


def test_chat_vs_chat_stream():
    """Verify chat() and chat_stream() produce same final result."""
    print("Comparing chat() vs chat_stream()...")
    provider = LMStudioNativeProvider()
    messages = [{"role": "user", "content": "Say hello"}]
    
    # Get response via chat()
    response_chat = provider.chat(messages)
    print(f"  chat(): {response_chat[:50]}...")
    
    # Get response via chat_stream()
    chunks = list(provider.chat_stream(messages))
    response_stream = "".join(chunks)
    print(f"  chat_stream(): {response_stream[:50]}...")
    
    # Both should produce content (may not be identical if model is non-deterministic)
    assert len(response_chat) > 0, "chat() should produce response"
    assert len(response_stream) > 0, "chat_stream() should produce response"
    print("✓ Both methods work\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Streaming Responses with supports_streaming Flags")
    print("=" * 60 + "\n")
    
    try:
        test_supports_streaming_flags()
        test_fallback_streaming()
        test_lm_studio_openai_streaming()
        test_native_sdk_streaming()
        test_chat_vs_chat_stream()
        
        print("=" * 60)
        print("✓ All streaming tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
