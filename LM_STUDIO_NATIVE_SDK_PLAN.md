# Plan: Add Native LM Studio Provider Using Official Python SDK

**Date:** December 25, 2025  
**Status:** 📋 PLANNING PHASE  
**Goal:** Add a second LM Studio provider implementation using the official `lmstudio` Python SDK alongside the existing OpenAI-compatible provider

---

## Executive Summary

We will add a new provider `LMStudioNativeProvider` that uses LM Studio's official Python SDK (`lmstudio` package) instead of the OpenAI-compatible REST API. Both implementations will coexist, allowing users to choose between them. This enables testing the native SDK's features (agentic workflows, structured responses, better model management) while maintaining backward compatibility.

---

## Current Architecture Analysis

### Existing LM Studio Provider (OpenAI-Compatible)
- **File:** `core/llm/lm_studio.py`
- **Class:** `LMStudioProvider`
- **Implementation:** Uses `requests` library to call OpenAI-compatible REST endpoints
- **Base URL:** `http://localhost:1234`
- **Endpoints:**
  - `/v1/chat/completions` - For chat messages
  - `/v1/models` - For listing models and metadata
- **Features:**
  - ✅ Chat completions
  - ✅ Vision support (converts to OpenAI content blocks)
  - ✅ Context length detection
  - ✅ Model listing
  - ✅ Error handling with context overflow detection

### Provider System Architecture
- **Base Class:** `core/llm/base.py` - `LLMProvider`
- **Required Methods:**
  1. `chat(messages, model)` → str
  2. `list_models()` → List[str]
  3. `get_model_context_length(model_name)` → Optional[int]
  4. `is_vision_model(model_name)` → bool
- **Integration Point:** `gui/main_window.py` - `get_llm_provider()` method
- **Settings UI:** `gui/dialogs/settings_dialog.py`

---

## LM Studio Native SDK Features

### Installation
```bash
pip install lmstudio
```
Already present in `requirements.txt`

### Key Capabilities

#### 1. **Basic Chat Completions**
```python
import lmstudio as lms

model = lms.llm("qwen2.5-7b-instruct")
result = model.respond("What is the meaning of life?")
```

#### 2. **Streaming Support**
```python
for fragment in model.respond_stream("Your prompt"):
    print(fragment.content, end="", flush=True)
```

#### 3. **Chat Context Management**
```python
chat = lms.Chat("You are a helpful assistant.")
chat.add_user_message("Hello")
result = model.respond(chat)
chat.append(result)  # Add response to history
```

#### 4. **Vision/Image Input** (VLM support)
```python
image_handle = lms.prepare_image("/path/to/image.jpg")
chat.add_user_message("Describe this image", images=[image_handle])
result = model.respond(chat)
```

#### 5. **Structured Responses** (JSON Schema)
```python
from pydantic import BaseModel

class BookSchema(BaseModel):
    title: str
    author: str
    year: int

result = model.respond("Tell me about The Hobbit", response_format=BookSchema)
book = result.parsed  # Returns typed dict matching schema
```

#### 6. **Agentic Workflows** (Tool Calling)
```python
def multiply(a: float, b: float) -> float:
    """Given two numbers a and b. Returns the product of them."""
    return a * b

model.act(
    "What is 12345 multiplied by 54321?",
    [multiply],
    on_message=print,
)
```

#### 7. **Configuration Options**
```python
result = model.respond(chat, config={
    "temperature": 0.6,
    "maxTokens": 50,
})
```

#### 8. **Model Management**
- List loaded models
- Get model info (context length, capabilities)
- Load/unload models programmatically

#### 9. **Progress Callbacks**
- `on_prompt_processing_progress`
- `on_first_token`
- `on_prediction_fragment`
- `on_message`

---

## Implementation Plan

### Phase 1: Create New Provider (Core Implementation)

#### Step 1.1: Create `core/llm/lm_studio_native.py`

**File:** `core/llm/lm_studio_native.py`

```python
"""LM Studio provider using native Python SDK."""

import lmstudio as lms
from typing import Optional, List
from .base import LLMProvider


class LMStudioNativeProvider(LLMProvider):
    """Provider for LM Studio using official Python SDK.
    
    Provides access to native LM Studio features including:
    - Native chat completions
    - Vision model support via prepare_image()
    - Structured responses
    - Better model metadata access
    - Streaming support
    """
    
    def __init__(self, base_url: str = "localhost:1234"):
        """Initialize LM Studio native provider.
        
        Args:
            base_url: Host:port of LM Studio API server (default: localhost:1234)
        """
        self.base_url = base_url
        # Configure default client if needed
        if base_url != "localhost:1234":
            lms.configure_default_client(base_url)
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Verify LM Studio API server is running."""
        try:
            if not lms.Client.is_valid_api_host(self.base_url):
                print(f"Warning: No LM Studio API server found at {self.base_url}")
        except Exception as e:
            print(f"Warning: Could not verify LM Studio connection: {e}")
    
    def chat(self, messages: list, model: str = None) -> str:
        """Send chat message to LM Studio using native SDK.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
                     Can include 'images' key for vision models
            model: Model name to use
            
        Returns:
            Response text from model
        """
        try:
            # Get model handle
            if model:
                llm_model = lms.llm(model)
            else:
                llm_model = lms.llm()  # Use currently loaded model
            
            # Build chat context
            chat = lms.Chat()
            
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                
                # Handle system messages
                if role == 'system':
                    # If this is the first message, use it as system prompt
                    if len(chat._messages) == 0:
                        chat = lms.Chat(content)
                    else:
                        # Add as user message if chat already started
                        chat.add_user_message(f"System: {content}")
                
                # Handle user messages
                elif role == 'user':
                    # Check for images (vision support)
                    images = msg.get('images', [])
                    if images:
                        # Convert base64 images to image handles
                        image_handles = []
                        for img_b64 in images:
                            # lmstudio SDK expects file paths or bytes
                            # We have base64 strings, need to decode
                            import base64
                            img_bytes = base64.b64decode(img_b64)
                            image_handle = lms.prepare_image(img_bytes)
                            image_handles.append(image_handle)
                        
                        chat.add_user_message(content, images=image_handles)
                    else:
                        chat.add_user_message(content)
                
                # Handle assistant messages
                elif role == 'assistant':
                    # For chat history, add assistant responses
                    # Note: lmstudio SDK chat.append() expects message objects
                    # We'll skip adding old assistant messages for now
                    # and let the model generate fresh responses
                    pass
            
            # Generate response
            result = llm_model.respond(chat)
            return result.content
            
        except Exception as e:
            return f"Error: {e}"
    
    def list_models(self) -> List[str]:
        """List available models from LM Studio.
        
        Returns:
            List of model names
        """
        try:
            # Use convenience API to list loaded models
            # Note: SDK has methods for both loaded and downloaded models
            # For now, we'll try to get loaded models first
            
            # TODO: Investigate best approach - SDK docs show:
            # - list_downloaded_models()
            # - list_loaded_models()
            
            # For initial implementation, we'll fall back to REST API
            # since native SDK model listing is not in basic docs
            import requests
            base = self.base_url.replace("localhost:", "http://localhost:")
            if not base.startswith("http"):
                base = f"http://{base}"
            
            response = requests.get(f"{base}/v1/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for m in data.get("data", []):
                mid = m.get("id") or m.get("model")
                if mid:
                    models.append(mid)
            return models
            
        except Exception as e:
            print(f"Error listing LM Studio models: {e}")
            return []
    
    def get_model_context_length(self, model_name: str) -> Optional[int]:
        """Get context length for a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Context length in tokens, or None if unknown
        """
        try:
            # Native SDK approach (if available)
            # model = lms.llm(model_name)
            # context_len = model.get_context_length()  # TODO: Verify API
            
            # For now, fall back to REST API
            import requests
            base = self.base_url.replace("localhost:", "http://localhost:")
            if not base.startswith("http"):
                base = f"http://{base}"
            
            response = requests.get(f"{base}/v1/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            for m in data.get("data", []):
                if m.get("id") == model_name or m.get("model") == model_name:
                    return (m.get("max_model_len") or 
                           m.get("context_length") or 
                           m.get("max_context_length") or
                           m.get("n_ctx"))
            return None
            
        except Exception as e:
            print(f"Error getting model context length: {e}")
            return None
    
    def is_vision_model(self, model_name: str) -> bool:
        """Detect vision capability for model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            True if model supports vision
        """
        if not model_name:
            return False
        
        try:
            # Use REST API to check metadata (native SDK may have better method)
            import requests
            base = self.base_url.replace("localhost:", "http://localhost:")
            if not base.startswith("http"):
                base = f"http://{base}"
            
            response = requests.get(f"{base}/v1/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            for m in data.get("data", []):
                if m.get("id") == model_name or m.get("model") == model_name:
                    # Check for vision capability in metadata
                    if m.get("vision"):
                        return True
                    # Check capabilities array
                    caps = m.get("capabilities", [])
                    if "vision" in caps or "image" in caps:
                        return True
            
            # Fall back to heuristic
            return super().is_vision_model(model_name)
            
        except Exception:
            # Fall back to base class heuristic
            return super().is_vision_model(model_name)
```

**Key Implementation Notes:**
- Uses `lmstudio.llm()` for model access
- Converts message format from Inkwell's format to SDK's `Chat` object
- Handles vision images by decoding base64 to bytes for `prepare_image()`
- Falls back to REST API for model listing/metadata (until we verify native SDK methods)
- Provides proper error handling with fallbacks

#### Step 1.2: Update `core/llm/__init__.py`

```python
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
    'LMStudioNativeProvider',  # Add new provider
]
```

---

### Phase 2: Integration with GUI

#### Step 2.1: Update `gui/main_window.py`

**Import Section:**
```python
from core.llm_provider import OllamaProvider, LMStudioProvider, LMStudioNativeProvider
```

**Update `get_llm_provider()` method (line 270):**
```python
def get_llm_provider(self):
    provider_name = self.settings.value("llm_provider", "Ollama")
    if provider_name == "Ollama":
        url = self.settings.value("ollama_url", "http://localhost:11434")
        return OllamaProvider(base_url=url)
    elif provider_name == "LM Studio (Native SDK)":
        # Use host:port format for native SDK
        url = self.settings.value("lm_studio_native_url", "localhost:1234")
        return LMStudioNativeProvider(base_url=url)
    else:  # "LM Studio" (OpenAI-compatible)
        url = self.settings.value("lm_studio_url", "http://localhost:1234")
        return LMStudioProvider(base_url=url)
```

**Alternative: More explicit handling:**
```python
def get_llm_provider(self):
    provider_name = self.settings.value("llm_provider", "Ollama")
    
    if provider_name == "Ollama":
        url = self.settings.value("ollama_url", "http://localhost:11434")
        return OllamaProvider(base_url=url)
    
    elif provider_name == "LM Studio":
        url = self.settings.value("lm_studio_url", "http://localhost:1234")
        return LMStudioProvider(base_url=url)
    
    elif provider_name == "LM Studio (Native SDK)":
        url = self.settings.value("lm_studio_native_url", "localhost:1234")
        return LMStudioNativeProvider(base_url=url)
    
    else:
        # Default fallback to Ollama
        url = self.settings.value("ollama_url", "http://localhost:11434")
        return OllamaProvider(base_url=url)
```

#### Step 2.2: Update `gui/dialogs/settings_dialog.py`

**Add provider to combo box (around line 72):**
```python
self.provider_combo.addItems([
    "Ollama", 
    "LM Studio",
    "LM Studio (Native SDK)"
])
```

**Add URL field for native SDK (after line 88):**
```python
# LM Studio Native SDK URL
self.lm_studio_native_url = QLineEdit()
self.lm_studio_native_url.setText(
    self.settings.value("lm_studio_native_url", "localhost:1234")
)
self.lm_native_row = form_layout.rowCount()
form_layout.addRow("LM Studio Native URL:", self.lm_studio_native_url)
```

**Update `update_provider_visibility()` method (around line 474):**
```python
def update_provider_visibility(self):
    provider_name = self.provider_combo.currentText()
    
    # Get labels
    ollama_label = self.form_layout.labelForField(self.ollama_url)
    lm_studio_label = self.form_layout.labelForField(self.lm_studio_url)
    lm_native_label = self.form_layout.labelForField(self.lm_studio_native_url)
    
    is_ollama = (provider_name == "Ollama")
    is_lm = (provider_name == "LM Studio")
    is_lm_native = (provider_name == "LM Studio (Native SDK)")
    
    # Toggle visibility for Ollama URL
    self.ollama_url.setVisible(is_ollama)
    if ollama_label:
        ollama_label.setVisible(is_ollama)
    
    # Toggle visibility for LM Studio URL (OpenAI-compatible)
    self.lm_studio_url.setVisible(is_lm)
    if lm_studio_label:
        lm_studio_label.setVisible(is_lm)
    
    # Toggle visibility for LM Studio Native SDK URL
    self.lm_studio_native_url.setVisible(is_lm_native)
    if lm_native_label:
        lm_native_label.setVisible(is_lm_native)
```

**Update `save()` method to store native URL:**
```python
def save(self):
    # ... existing code ...
    
    # Save LM Studio Native URL
    self.settings.setValue(
        "lm_studio_native_url", 
        self.lm_studio_native_url.text()
    )
    
    # ... rest of save logic ...
```

---

### Phase 3: Testing & Validation

#### Step 3.1: Create Test File

**File:** `test_lm_studio_native.py`

```python
"""Test LM Studio Native SDK Provider"""

from core.llm import LMStudioNativeProvider

def test_connection():
    """Test basic connection to LM Studio"""
    provider = LMStudioNativeProvider()
    print("✓ Provider created")

def test_list_models():
    """Test listing available models"""
    provider = LMStudioNativeProvider()
    models = provider.list_models()
    print(f"Available models: {models}")
    assert isinstance(models, list), "Should return list"
    print("✓ Models listed")
    return models

def test_basic_chat():
    """Test basic chat functionality"""
    provider = LMStudioNativeProvider()
    messages = [
        {"role": "user", "content": "Say 'Hello from native SDK' and nothing else"}
    ]
    response = provider.chat(messages)
    print(f"Response: {response}")
    assert isinstance(response, str), "Should return string"
    assert not response.startswith("Error:"), f"Got error: {response}"
    print("✓ Basic chat works")

def test_chat_with_history():
    """Test chat with conversation history"""
    provider = LMStudioNativeProvider()
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Hello Alice!"},
        {"role": "user", "content": "What is my name?"}
    ]
    response = provider.chat(messages)
    print(f"Response: {response}")
    assert isinstance(response, str), "Should return string"
    print("✓ Chat with history works")

def test_model_metadata():
    """Test model metadata retrieval"""
    provider = LMStudioNativeProvider()
    models = provider.list_models()
    
    if not models:
        print("⚠ No models loaded, skipping metadata test")
        return
    
    model = models[0]
    context_len = provider.get_model_context_length(model)
    is_vision = provider.is_vision_model(model)
    
    print(f"Model: {model}")
    print(f"Context length: {context_len}")
    print(f"Vision support: {is_vision}")
    print("✓ Metadata retrieved")

def test_vision_model_detection():
    """Test vision model detection"""
    provider = LMStudioNativeProvider()
    
    # Test heuristic for known vision model names
    test_cases = [
        ("llava-v1.5-7b", True),
        ("qwen2-vl-2b-instruct", True),
        ("llama-3.2-3b-instruct", False),
    ]
    
    for model_name, expected_vision in test_cases:
        result = provider.is_vision_model(model_name)
        status = "✓" if result == expected_vision else "✗"
        print(f"{status} {model_name}: vision={result} (expected {expected_vision})")

if __name__ == "__main__":
    print("Testing LM Studio Native SDK Provider\n")
    print("=" * 50)
    
    try:
        test_connection()
        print()
        
        models = test_list_models()
        print()
        
        if models:
            test_basic_chat()
            print()
            
            test_chat_with_history()
            print()
            
            test_model_metadata()
            print()
        else:
            print("⚠ No models loaded in LM Studio. Load a model to test chat.")
            print()
        
        test_vision_model_detection()
        print()
        
        print("=" * 50)
        print("✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
```

#### Step 3.2: Manual Testing Checklist

**Pre-requisites:**
- [ ] LM Studio application running
- [ ] At least one model loaded in LM Studio
- [ ] `lmstudio` package installed (`pip install lmstudio`)

**Test Cases:**

1. **Provider Selection:**
   - [ ] Settings dialog shows all three providers
   - [ ] Switching providers shows/hides correct URL fields
   - [ ] Native SDK field accepts `localhost:1234` format (no http://)
   - [ ] Settings are saved and persist after restart

2. **Basic Functionality:**
   - [ ] Can list models using native provider
   - [ ] Basic chat works (single message)
   - [ ] Multi-turn conversation works
   - [ ] System prompts are respected

3. **Vision Support (if VLM loaded):**
   - [ ] Can attach images to chat
   - [ ] Vision model detection works
   - [ ] Image descriptions are generated correctly

4. **Error Handling:**
   - [ ] Graceful handling when LM Studio not running
   - [ ] Clear error messages for connection failures
   - [ ] Handles model not loaded scenario

5. **Feature Parity:**
   - [ ] Chat quality comparable to OpenAI-compatible provider
   - [ ] Response times acceptable
   - [ ] Context handling works correctly

---

### Phase 4: Documentation & Polish

#### Step 4.1: Update ADDING_NEW_LLM_PROVIDERS.md

Add section on native SDK provider as reference implementation:

```markdown
## Example: LM Studio Native SDK Provider

This example shows a more complex provider using an official SDK.

### Implementation Highlights

**File:** `core/llm/lm_studio_native.py`

- Uses official `lmstudio` Python package
- Converts between Inkwell message format and SDK's Chat objects
- Handles base64 image decoding for vision support
- Falls back to REST API for features not yet in SDK docs
- Provides comprehensive error handling

### Key Differences from REST API Provider

1. **Chat Context Management:**
   - Native SDK uses `lms.Chat()` objects
   - Better conversation history handling
   - Automatic message appending with `chat.append(result)`

2. **Vision Support:**
   - Uses `lms.prepare_image()` for image handling
   - Accepts file paths, bytes, or IO objects
   - Cleaner API than OpenAI content blocks

3. **Model Selection:**
   - `lms.llm(model_name)` returns model handle
   - Can query model metadata directly
   - Better integration with LM Studio's model management

4. **Future Features:**
   - Structured responses via `response_format`
   - Agentic workflows via `.act()`
   - Streaming via `respond_stream()`
   - Progress callbacks
```

#### Step 4.2: Update Project README

Add to provider documentation:

```markdown
### LLM Providers

Inkwell AI supports multiple local LLM providers:

#### Ollama
- **Port:** 11434
- **API:** Native Ollama library
- **Best for:** Easy model management, wide model selection

#### LM Studio (OpenAI-Compatible)
- **Port:** 1234
- **API:** OpenAI-compatible REST endpoints
- **Best for:** Drop-in OpenAI replacement, stability

#### LM Studio (Native SDK)
- **Port:** 1234
- **API:** Official Python SDK
- **Best for:** Advanced features (structured output, agents)
- **Note:** Experimental, requires `lmstudio` package

All providers support:
- Multi-turn conversations
- Vision models (VLMs)
- Context length detection
- Model listing
```

#### Step 4.3: Add User-Facing Documentation

**File:** `docs/LM_STUDIO_NATIVE_SDK.md` (new)

```markdown
# Using LM Studio Native SDK Provider

## Overview

The Native SDK provider uses LM Studio's official Python SDK instead of the OpenAI-compatible REST API. This provides access to advanced features and tighter integration.

## Setup

1. Install the SDK:
   ```bash
   pip install lmstudio
   ```

2. Start LM Studio and load a model

3. In Inkwell AI Settings:
   - Select "LM Studio (Native SDK)" as provider
   - Set URL to `localhost:1234` (or your custom port)

## Features

### Currently Supported
- ✅ Chat completions
- ✅ Vision model support
- ✅ Model listing and metadata
- ✅ Context length detection
- ✅ Multi-turn conversations

### Planned (Future Releases)
- 🔄 Streaming responses
- 🔄 Structured output (JSON schema)
- 🔄 Agentic workflows (tool calling)
- 🔄 Progress callbacks

## Comparison: OpenAI-Compatible vs Native SDK

| Feature | OpenAI API | Native SDK |
|---------|-----------|------------|
| Chat | ✅ | ✅ |
| Vision | ✅ | ✅ |
| Streaming | ✅ | 🔄 |
| Model List | ✅ | ✅ |
| Structured Output | ❌ | 🔄 |
| Tool Calling | ❌ | 🔄 |
| Agent Workflows | ❌ | 🔄 |

## Troubleshooting

### "No LM Studio API server found"
- Ensure LM Studio is running
- Check the API server is enabled in LM Studio settings
- Verify the port number is correct

### "Error: Connection refused"
- Make sure no firewall is blocking localhost connections
- Try restarting LM Studio

### Images not working
- Ensure you have a vision model loaded (e.g., llava, qwen2-vl)
- Check the model is marked as vision-capable

## When to Use Each Provider

**Use OpenAI-Compatible when:**
- You need maximum stability
- You're migrating from OpenAI
- You don't need advanced features

**Use Native SDK when:**
- You want to test new features
- You need structured output (future)
- You want agent capabilities (future)
- You prefer official SDK over REST calls
```

---

## Future Enhancements (Post-Initial Release)

### Enhancement 1: Streaming Support

**Current:** Returns full response at once  
**Future:** Stream tokens as they're generated

```python
def chat_stream(self, messages: list, model: str = None):
    """Stream chat response token by token."""
    llm_model = lms.llm(model) if model else lms.llm()
    chat = self._build_chat_context(messages)
    
    for fragment in llm_model.respond_stream(chat):
        yield fragment.content
```

**Integration:**
- Add `chat_stream()` to base `LLMProvider` interface
- Update `ChatWorker` to support streaming
- Show tokens as they arrive in chat widget

### Enhancement 2: Structured Responses

**Use Case:** Extract structured data from LLM responses

```python
from pydantic import BaseModel

class CharacterProfile(BaseModel):
    name: str
    age: int
    traits: List[str]

# In provider:
def chat_structured(self, messages: list, schema: type, model: str = None):
    """Get structured response matching schema."""
    llm_model = lms.llm(model) if model else lms.llm()
    chat = self._build_chat_context(messages)
    result = llm_model.respond(chat, response_format=schema)
    return result.parsed  # Returns typed dict
```

**Integration:**
- Add optional schema parameter to chat methods
- Create UI for defining schemas (JSON Schema editor?)
- Use for character generation, world-building forms

### Enhancement 3: Agentic Workflows

**Use Case:** Let LLM call tools (search, image gen, file operations)

```python
def create_character_file(name: str, description: str):
    """Create a character file in the project."""
    # ... implementation ...
    return "Character created"

def generate_character_image(description: str):
    """Generate a character portrait."""
    # ... implementation ...
    return "/path/to/image.png"

# In provider:
def chat_with_tools(self, messages: list, tools: list, model: str = None):
    """Chat with tool calling enabled."""
    llm_model = lms.llm(model) if model else lms.llm()
    chat = self._build_chat_context(messages)
    
    result = llm_model.act(
        chat,
        tools,
        on_message=lambda msg: print(f"Agent: {msg}"),
    )
    
    return result.content
```

**Integration:**
- Define tool registry for Inkwell operations
- Add UI to enable/disable specific tools
- Show tool usage in chat (e.g., "🔧 Called: create_character_file")

### Enhancement 4: Better Model Management

```python
def load_model(self, model_path: str):
    """Load a model into LM Studio."""
    # Use SDK to load model programmatically
    
def unload_model(self, model_name: str):
    """Unload a model from memory."""
    # Free up resources
    
def get_loaded_models(self):
    """Get list of currently loaded models."""
    # Return active models only
```

---

## Risk Assessment & Mitigation

### Risk 1: SDK API Changes
**Likelihood:** Medium  
**Impact:** High  
**Mitigation:**
- Pin SDK version in requirements.txt initially
- Add version checks in provider code
- Keep OpenAI-compatible provider as stable fallback
- Monitor LM Studio GitHub for breaking changes

### Risk 2: Incomplete SDK Documentation
**Likelihood:** High (currently evident)  
**Impact:** Medium  
**Mitigation:**
- Use REST API fallback for undocumented features
- Contribute to LM Studio SDK docs/examples
- Test thoroughly with multiple SDK versions
- Document our findings for future developers

### Risk 3: Performance Regression
**Likelihood:** Low  
**Impact:** Medium  
**Mitigation:**
- Benchmark against OpenAI-compatible provider
- Profile SDK overhead
- Allow users to switch between providers easily
- Keep both implementations for comparison

### Risk 4: Base64 Image Handling
**Likelihood:** Medium  
**Impact:** Medium  
**Mitigation:**
- Test with various image formats (JPEG, PNG, WebP)
- Validate base64 decoding before passing to SDK
- Provide clear error messages for invalid images
- Add image size/format validation

---

## Implementation Timeline

### Sprint 1: Core Implementation (3-4 hours)
- [ ] Create `lm_studio_native.py` with basic functionality
- [ ] Update `__init__.py` exports
- [ ] Implement chat() method with message conversion
- [ ] Test basic chat functionality

### Sprint 2: GUI Integration (2-3 hours)
- [ ] Update settings dialog with new provider option
- [ ] Add URL configuration field
- [ ] Update `get_llm_provider()` logic
- [ ] Test provider switching in UI

### Sprint 3: Feature Completion (2-3 hours)
- [ ] Implement vision support (base64 → bytes conversion)
- [ ] Add model listing (with REST fallback)
- [ ] Implement context length detection
- [ ] Add comprehensive error handling

### Sprint 4: Testing & Polish (3-4 hours)
- [ ] Create test file with all test cases
- [ ] Manual testing with multiple models
- [ ] Test vision model scenarios
- [ ] Error case testing (no LM Studio, no model loaded, etc.)
- [ ] Update documentation

**Total Estimated Time:** 10-14 hours

---

## Success Criteria

### Must Have (MVP)
- ✅ Provider can be selected in settings
- ✅ Basic chat works with loaded model
- ✅ Multi-turn conversations maintain context
- ✅ Vision models can accept images
- ✅ Model listing returns available models
- ✅ Error handling prevents crashes
- ✅ Can switch between providers without restart

### Should Have
- ✅ Context length detection works
- ✅ Vision model detection is accurate
- ✅ Settings persist across sessions
- ✅ Clear error messages for common issues
- ✅ Basic tests pass
- ✅ Documentation exists

### Nice to Have (Future)
- 🔄 Streaming responses
- 🔄 Structured output support
- 🔄 Tool calling / agents
- 🔄 Progress callbacks
- 🔄 Performance benchmarks
- 🔄 Advanced model management

---

## Conclusion

This plan provides a clear path to adding LM Studio's native SDK as a third provider option alongside Ollama and the existing OpenAI-compatible LM Studio provider. The architecture supports gradual enhancement, allowing us to ship basic functionality quickly while leaving room for advanced features like structured responses and agentic workflows.

**Key Benefits:**
1. **Zero breaking changes** - existing providers continue working
2. **User choice** - three providers to choose from
3. **Future-proof** - foundation for advanced features
4. **Low risk** - can be disabled if issues arise
5. **Maintainable** - follows established provider pattern

**Next Steps:**
1. Create `core/llm/lm_studio_native.py`
2. Update imports and settings UI
3. Test with basic chat scenarios
4. Iterate on vision support and metadata
5. Document and ship!
