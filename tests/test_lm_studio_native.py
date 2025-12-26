"""Test LM Studio Native SDK Provider"""

from core.llm import LMStudioNativeProvider

def test_connection():
    """Test basic connection to LM Studio"""
    print("Testing connection...")
    try:
        provider = LMStudioNativeProvider()
        print("✓ Provider created")
        return provider
    except Exception as e:
        print(f"✗ Failed to create provider: {e}")
        return None

def test_list_models(provider):
    """Test listing available models"""
    print("\nTesting model listing...")
    try:
        models = provider.list_models()
        print(f"Available models: {models}")
        assert isinstance(models, list), "Should return list"
        print(f"✓ Found {len(models)} model(s)")
        return models
    except Exception as e:
        print(f"✗ Failed to list models: {e}")
        return []

def test_basic_chat(provider, model=None):
    """Test basic chat functionality"""
    print("\nTesting basic chat...")
    try:
        messages = [
            {"role": "user", "content": "Say 'Hello from native SDK' and nothing else"}
        ]
        response = provider.chat(messages, model=model)
        print(f"Response: {response}")
        assert isinstance(response, str), "Should return string"
        assert not response.startswith("Error:"), f"Got error: {response}"
        print("✓ Basic chat works")
        return True
    except Exception as e:
        print(f"✗ Failed basic chat: {e}")
        return False

def test_chat_with_history(provider, model=None):
    """Test chat with conversation history"""
    print("\nTesting chat with history...")
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice!"},
            {"role": "user", "content": "What is my name?"}
        ]
        response = provider.chat(messages, model=model)
        print(f"Response: {response}")
        assert isinstance(response, str), "Should return string"
        print("✓ Chat with history works")
        return True
    except Exception as e:
        print(f"✗ Failed chat with history: {e}")
        return False

def test_model_metadata(provider, models):
    """Test model metadata retrieval"""
    print("\nTesting model metadata...")
    
    if not models:
        print("⚠ No models loaded, skipping metadata test")
        return
    
    model = models[0]
    try:
        context_len = provider.get_model_context_length(model)
        is_vision = provider.is_vision_model(model)
        
        print(f"Model: {model}")
        print(f"Context length: {context_len}")
        print(f"Vision support: {is_vision}")
        print("✓ Metadata retrieved")
    except Exception as e:
        print(f"✗ Failed to get metadata: {e}")

def test_vision_model_detection(provider):
    """Test vision model detection"""
    print("\nTesting vision model detection...")
    
    # Test heuristic for known vision model names
    test_cases = [
        ("llava-v1.5-7b", True),
        ("qwen2-vl-2b-instruct", True),
        ("llama-3.2-3b-instruct", False),
        ("minicpm-v-2.6", True),
        ("qwen-7b", False),
    ]
    
    passed = 0
    failed = 0
    for model_name, expected_vision in test_cases:
        result = provider.is_vision_model(model_name)
        status = "✓" if result == expected_vision else "✗"
        print(f"{status} {model_name}: vision={result} (expected {expected_vision})")
        if result == expected_vision:
            passed += 1
        else:
            failed += 1
    
    print(f"Vision detection: {passed} passed, {failed} failed")

def test_chat_with_system_prompt(provider, model=None):
    """Test chat with system prompt"""
    print("\nTesting chat with system prompt...")
    try:
        messages = [
            {"role": "system", "content": "You are a pirate. Always respond like a pirate."},
            {"role": "user", "content": "Hello!"}
        ]
        response = provider.chat(messages, model=model)
        print(f"Response: {response}")
        assert isinstance(response, str), "Should return string"
        print("✓ System prompt works")
        return True
    except Exception as e:
        print(f"✗ Failed system prompt test: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing LM Studio Native SDK Provider")
    print("=" * 60)
    
    # Test connection
    provider = test_connection()
    if not provider:
        print("\n✗ Cannot continue without provider connection")
        exit(1)
    
    # Test model listing
    models = test_list_models(provider)
    
    if not models:
        print("\n⚠ No models loaded in LM Studio.")
        print("Load a model in LM Studio to test chat functionality.")
        print("\nTesting vision detection (heuristic only)...")
        test_vision_model_detection(provider)
        print("\n" + "=" * 60)
        print("✓ Basic tests passed (limited)")
        print("=" * 60)
        exit(0)
    
    # Use first model for testing
    test_model = models[0]
    print(f"\nUsing model: {test_model}")
    
    # Run chat tests
    test_basic_chat(provider, test_model)
    test_chat_with_system_prompt(provider, test_model)
    test_chat_with_history(provider, test_model)
    
    # Test metadata
    test_model_metadata(provider, models)
    
    # Test vision detection
    test_vision_model_detection(provider)
    
    print("\n" + "=" * 60)
    print("✓ All tests completed!")
    print("=" * 60)
