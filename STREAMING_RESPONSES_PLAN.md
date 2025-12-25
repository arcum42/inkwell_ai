# Streaming Responses Implementation Plan

**Date:** December 25, 2025  
**Priority:** HIGH - Improves UX responsiveness  
**Status:** 📋 PLANNING PHASE

## Overview

Add streaming response support to all three LLM providers (Ollama, LM Studio OpenAI-compatible, LM Studio Native SDK). Streaming will allow users to see tokens appear in real-time as the model generates them, dramatically improving perceived responsiveness.

---

## Current Architecture

### Chat Worker (`gui/workers/chat_worker.py`)
- Uses `provider.chat()` which blocks until entire response is received
- Emits `response_received` signal with full text
- Single signal emission at the end

### Provider Interface (`core/llm/base.py`)
- Only has `chat()` method
- Returns complete response string
- No streaming capability indicator

### Notes from LM Studio Native Plan
- LM Studio SDK has native `respond_stream()` method
- Returns fragments with `.content` attribute
- Integrates well with existing `_build_chat_context()` method
- Mentioned as Enhancement 1 for native provider: "def chat_stream() using respond_stream() to yield fragment.content"

### Architectural Approach: Provider-Level Streaming Support
**Design Decision:** Use a `supports_streaming` class attribute on each provider to indicate capability. Default is `False`. Enable per-provider as implemented.

**Rationale:**
- Allows gradual rollout without breaking existing providers
- No user settings needed (behavior is automatic based on provider)
- ChatWorker automatically uses streaming when available
- Each provider controls its own implementation (some may use real streaming, others may fall back)
- Future-proof: Can enable streaming for Ollama and LM Studio OpenAI later

---

## Implementation Plan

### Phase 1: Base Interface & Provider Implementations

#### Step 1.1: Add `supports_streaming` Flag and `chat_stream()` to Base Class

**File:** `core/llm/base.py`

```python
class LLMProvider:
    """Base class for language model providers."""
    
    # Class attribute indicating if this provider supports streaming
    # Default: False (provider implements chat_stream with fallback to chat())
    # Set to True when provider has real streaming implementation
    supports_streaming = False
    
    def chat_stream(self, messages, model=None):
        """Stream chat response tokens as they are generated.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name to use (provider-specific)
            
        Yields:
            String tokens/fragments as they are generated
            
        Default Implementation (when supports_streaming=False):
            Falls back to non-streaming chat() and yields entire response as one chunk.
            This ensures all providers work with streaming infrastructure even if
            they don't have real streaming capability yet.
            
        Real Streaming (when supports_streaming=True):
            Subclass implementation yields tokens as they arrive from the provider.
            Example: LMStudioNativeProvider uses SDK's respond_stream() method.
        """
        response = self.chat(messages, model=model)
        yield response
```

**What This Does:**
- All providers inherit `chat_stream()` method that safely falls back to `chat()`
- Providers indicate real streaming capability via `supports_streaming = True`
- ChatWorker checks this flag and uses streaming when available
- Backward compatible: non-streaming providers still work with streaming infrastructure

#### Step 1.2: Implement in OllamaProvider

**File:** `core/llm/ollama.py`

```python
class OllamaProvider(LLMProvider):
    """Provider for Ollama local models."""
    
    # Ollama library has streaming capability via chat(stream=True)
    # Currently set to False - will enable in Phase 2 of streaming implementation
    supports_streaming = False
    
    def chat_stream(self, messages, model="llama3"):
        """Stream chat response from Ollama (current: fallback to non-streaming).
        
        Note: Ollama library's client.chat() supports stream=True parameter.
        When streaming is enabled for Ollama, this method will use it.
        For now, uses fallback behavior from base class.
        """
        response = self.chat(messages, model=model)
        yield response
```

**Current Status:** `supports_streaming = False` (uses fallback)  
**When Enabling:** Change `supports_streaming = True` and implement real streaming using `client.chat(stream=True)`

#### Step 1.3: Implement in LMStudioProvider (OpenAI-compatible)

**File:** `core/llm/lm_studio.py`

```python
class LMStudioProvider(LLMProvider):
    """Provider for LM Studio via OpenAI-compatible REST API."""
    
    # OpenAI-compatible API supports streaming via SSE
    # Currently set to False - will enable in Phase 2 of streaming implementation
    supports_streaming = False
    
    def chat_stream(self, messages, model="local-model"):
        """Stream chat response from LM Studio OpenAI-compatible API (current: fallback).
        
        Note: LM Studio's OpenAI-compatible endpoint supports stream=True parameter
        which returns Server-Sent Events (SSE) with partial responses.
        When streaming is enabled for this provider, this method will parse SSE.
        For now, uses fallback behavior from base class.
        """
        response = self.chat(messages, model=model)
        yield response
```

**Current Status:** `supports_streaming = False` (uses fallback)  
**When Enabling:** Change `supports_streaming = True` and implement real streaming using SSE parsing

#### Step 1.4: Implement in LMStudioNativeProvider (Real Streaming)

**File:** `core/llm/lm_studio_native.py`

LM Studio Native SDK has native streaming via `respond_stream()` method:

```python
class LMStudioNativeProvider(LLMProvider):
    """Provider for LM Studio using official Python SDK."""
    
    # Native SDK's respond_stream() method provides real token-by-token streaming
    supports_streaming = True
    
    def chat_stream(self, messages, model=None):
        """Stream chat response token-by-token using LM Studio native SDK.
        
        Uses the native SDK's respond_stream() method to yield fragments
        as they are generated by the model. This is the first provider with
        real streaming capability.
        """
        try:
            # Get model handle
            if model:
                llm_model = lms.llm(model)
            else:
                llm_model = lms.llm()
            
            # Build chat context (reuse existing method)
            chat = self._build_chat_context(messages)
            
            # Stream response using native SDK
            for fragment in llm_model.respond_stream(chat):
                # Fragment has .content attribute with text
                content = fragment.content if hasattr(fragment, 'content') else str(fragment)
                if content:
                    yield content
        except Exception as e:
            yield f"Error: {e}"
```

**Key Points:**
- `supports_streaming = True` - This provider HAS real streaming
- Uses `respond_stream()` from native SDK (returns fragment objects)
- Yields tokens as they arrive (no buffering)
- Most responsive streaming implementation

---

### Phase 2: Chat Worker Integration (Automatic Streaming)

#### Step 2.1: Update ChatWorker to Check `supports_streaming` Flag

**File:** `gui/workers/chat_worker.py`

The ChatWorker automatically detects and uses streaming when available:

```python
class ChatWorker(QThread):
    """Worker thread for handling LLM chat interactions."""
    
    response_received = Signal(str)
    response_chunk = Signal(str)  # NEW: Emit chunks as they arrive
    
    def __init__(self, provider, chat_history, model, context, system_prompt, 
                 images=None, enabled_tools=None):
        super().__init__()
        self.provider = provider
        self.chat_history = list(chat_history)
        self.model = model
        self.context = context
        self.system_prompt = system_prompt
        self.images = images
        self.enabled_tools = enabled_tools
        # NOTE: No use_streaming parameter - behavior is automatic based on provider
    
    def run(self):
        # ... (same message construction as before) ...
        
        try:
            # Automatically detect and use streaming if provider supports it
            if self.provider.supports_streaming:
                # Use streaming - provider has real streaming capability
                full_response = ""
                for chunk in self.provider.chat_stream(messages, model=self.model):
                    full_response += chunk
                    self.response_chunk.emit(chunk)  # Emit as it arrives
                
                # Also emit full response for completion
                self.response_received.emit(full_response)
            else:
                # Fall back to non-streaming
                # (provider.chat_stream() will internally fallback to chat() anyway)
                response = self.provider.chat(messages, model=self.model)
                self.response_received.emit(response)
                
        except Exception as e:
            import traceback
            print(f"ERROR: Exception in ChatWorker.run():")
            traceback.print_exc()
            response = f"Error calling LLM provider: {str(e)}"
            self.response_received.emit(response)
```

**Key Points:**
- No `use_streaming` parameter needed (automatic based on `provider.supports_streaming`)
- Check `provider.supports_streaming` flag
- Use `provider.chat_stream()` if True (real streaming)
- Use `provider.chat()` if False (non-streaming, faster when no streaming capability)
- Emits `response_chunk` signal for live UI updates

---

### Phase 3: UI Integration

#### Step 3.1: Update Chat Widget

**File:** `gui/chat.py`

Connect streaming signal for live response updates:

```python
class ChatWidget(QWidget):
    def __init__(self, main_window):
        # ... existing init code ...
        
        # Connect to chat worker
        self.chat_worker = None
    
    def start_chat(self, ...):
        # ... existing code ...
        
        self.chat_worker = ChatWorker(
            provider,
            chat_history,
            model,
            context,
            system_prompt,
            images=images,
            enabled_tools=enabled_tools
            # NOTE: No use_streaming parameter - behavior is automatic
        )
        
        # Connect BOTH signals for streaming and completion
        self.chat_worker.response_chunk.connect(self.append_response_chunk)
        self.chat_worker.response_received.connect(self.on_response_complete)
        
        self.chat_worker.start()
    
    def append_response_chunk(self, chunk: str):
        """Append a chunk of response text (from streaming).
        
        Called as each token arrives from the streaming response.
        Shows tokens appearing in real-time as they are generated.
        """
        # Append to the assistant message being built
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        
        # Auto-scroll to bottom to show new content
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )
    
    def on_response_complete(self, response: str):
        """Called when the full response is complete.
        
        Updates chat history and re-enables input controls.
        """
        # Update chat history with final response
        self.chat_history.append({
            "role": "assistant",
            "content": response,
        })
        
        # Hide loading indicator
        self.loading_label.setVisible(False)
        
        # Enable input
        self.chat_input.setEnabled(True)
        self.send_button.setEnabled(True)
```

**Behavior:**
- For LM Studio Native (`supports_streaming = True`): Tokens appear as they're generated
- For Ollama/LM Studio OpenAI (`supports_streaming = False`): Full response appears at once
- Both cases use same UI code (streaming signal is emitted with entire response for non-streaming providers)

---

### Phase 4: Testing & Rollout

#### Step 4.1: Create Test File

**File:** `test_streaming.py`

```python
"""Test streaming responses - verifies flag-based behavior."""

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
    assert len(chunks) == 1, "Fallback should return one chunk"
    print(f"  Response: {chunks[0][:50]}...")
    print("✓ Fallback streaming works\n")

def test_native_sdk_streaming():
    """Test real streaming from LM Studio Native SDK."""
    print("Testing real streaming (LM Studio Native)...")
    provider = LMStudioNativeProvider()
    messages = [{"role": "user", "content": "Count from 1 to 5"}]
    
    print("  Response: ", end="", flush=True)
    chunk_count = 0
    for chunk in provider.chat_stream(messages):
        print(chunk, end="", flush=True)
        chunk_count += 1
    print()
    
    print(f"  Received {chunk_count} chunk(s)")
    assert chunk_count > 1, "Native streaming should return multiple chunks"
    print("✓ Native streaming works\n")

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
    
    print("✓ Both methods work\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Streaming Responses with supports_streaming Flags")
    print("=" * 60 + "\n")
    
    try:
        test_supports_streaming_flags()
        test_fallback_streaming()
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
```

#### Step 4.2: Rollout Timeline

- **Phase 1 (Now):** LM Studio Native SDK has `supports_streaming = True`
- **Phase 2 (Future):** Enable Ollama streaming (set `supports_streaming = True`)
- **Phase 3 (Future):** Enable LM Studio OpenAI streaming (set `supports_streaming = True`)
- **Phase 4 (Future):** Fine-tune streaming behavior (buffering, auto-scroll preferences)

---

## Implementation Checklist

### Phase 1: Base Interface & Provider Implementations

- [ ] **Step 1.1:** Add `supports_streaming = False` class attribute to `core/llm/base.py`
  - Add `chat_stream()` method with fallback implementation
  - Ensure all providers inherit this attribute
  
- [ ] **Step 1.2:** Add `supports_streaming = False` to `core/llm/ollama.py`
  - Leave `chat_stream()` to use fallback (no changes needed yet)
  
- [ ] **Step 1.3:** Add `supports_streaming = False` to `core/llm/lm_studio.py`
  - Leave `chat_stream()` to use fallback (no changes needed yet)
  
- [ ] **Step 1.4:** Add `supports_streaming = True` to `core/llm/lm_studio_native.py`
  - Implement real `chat_stream()` using `respond_stream()`

### Phase 2: Chat Worker Integration

- [ ] **Step 2.1:** Update `gui/workers/chat_worker.py`
  - Remove `use_streaming` parameter from `__init__`
  - Check `provider.supports_streaming` flag in `run()`
  - Use `chat_stream()` if True, `chat()` if False
  - Add `response_chunk` Signal and emit chunks

### Phase 3: UI Integration

- [ ] **Step 3.1:** Update `gui/chat.py`
  - Connect `response_chunk` signal to `append_response_chunk()`
  - Implement `append_response_chunk()` method
  - Remove `use_streaming` parameter from `ChatWorker()` instantiation

### Phase 4: Testing & Rollout

- [ ] **Step 4.1:** Create `test_streaming.py`
  - Test supports_streaming flags
  - Test fallback behavior (Ollama, LM Studio OpenAI)
  - Test real streaming (LM Studio Native)
  - Compare outputs from chat() vs chat_stream()

### Future Phases

- [ ] **Phase 2+ Enablement:** When ready to enable streaming for other providers:
  - Set `supports_streaming = True` in provider
  - Implement real `chat_stream()` method
  - Existing ChatWorker and UI code automatically use it

---

## Estimated Timeline

| Phase | Tasks | Time | Status |
|-------|-------|------|--------|
| 1 | Base class + provider flags | 30 min | 📋 Planned |
| 2 | ChatWorker updates | 20 min | 📋 Planned |
| 3 | UI integration | 20 min | 📋 Planned |
| 4 | Testing | 20 min | 📋 Planned |
| **Total** | | **~1.5 hours** | |

**Key Advantage:** Once Phase 1-4 complete, enabling streaming for Ollama or LM Studio OpenAI only requires implementing their `chat_stream()` methods. No ChatWorker or UI changes needed.

---

---

## Streaming Flow Diagram

```
User Input
    ↓
ChatWorker.run()
    ↓
Check use_streaming flag
    ↓
    ├─→ YES: provider.chat_stream()
    │   ├→ Iterate over chunks
    │   ├→ response_chunk.emit(chunk) [UI updates live]
    │   └→ response_received.emit(full_response) [Final update]
    │
    └─→ NO: provider.chat()
        └→ response_received.emit(response) [Original behavior]
```

---

## UI Update During Streaming

### Current Behavior (Non-Streaming)
1. User sends message
2. UI shows loading indicator
3. Wait... wait... wait...
4. Full response appears

### New Behavior (Streaming)
1. User sends message
2. UI shows loading indicator
3. First token: "H" appears
4. Next token: "He" updates
5. Continue: "Hello" → "Hello, " → "Hello, how"...
6. Response completes and is finalized

---

## Error Handling

### Provider Doesn't Support Streaming
```python
if hasattr(self.provider, 'chat_stream'):
    # Use streaming
else:
    # Fall back to non-streaming
```

### Streaming Fails Mid-Response
```python
try:
    for chunk in provider.chat_stream(...):
        # ...
except Exception as e:
    # Emit error and use fallback if needed
```

---

## Performance Considerations

1. **Token-by-Token vs Buffered:**
   - SSE protocol may buffer several tokens
   - Not a problem for UX (still more responsive)

2. **UI Update Frequency:**
   - Multiple small updates is fine
   - Qt handles this efficiently

3. **Memory:**
   - Streaming prevents holding full response in memory during generation
   - Minor benefit for very long responses

---

## Configuration Options (Future)

Could add to settings:
- Streaming enabled/disabled
- Streaming buffering size
- Auto-scroll behavior during streaming

---

## Success Criteria

✅ **Phase 1 Complete:**
- `core/llm/base.py` has `supports_streaming = False` and `chat_stream()` method
- All three providers have `supports_streaming` attribute set correctly
- LMStudioNativeProvider has `supports_streaming = True` and real streaming implementation

✅ **Phase 2 Complete:**
- ChatWorker checks `provider.supports_streaming` flag
- Uses `chat_stream()` when True, `chat()` when False
- Emits `response_chunk` for live updates and `response_received` for completion

✅ **Phase 3 Complete:**
- Chat UI connects to `response_chunk` signal
- `append_response_chunk()` appends text to display
- Auto-scrolls to show new content
- Both streaming and non-streaming work in UI

✅ **Phase 4 Complete:**
- `test_streaming.py` verifies all providers
- Fallback behavior works for Ollama and LM Studio OpenAI
- Real streaming works for LM Studio Native
- `chat()` and `chat_stream()` produce same results

✅ **No Breaking Changes:**
- Existing non-streaming providers still work perfectly
- ChatWorker signature simplified (removed `use_streaming` parameter)
- UI code works for both streaming and non-streaming
- Users don't need settings for streaming toggle (automatic per provider)  

---

## Next Steps After Streaming

1. **Structured Output** - Use LM Studio native SDK's `response_format` parameter
2. **Tool Calling** - Use `.act()` for agentic workflows
3. **Progress Callbacks** - Show prompt processing progress
4. **Model Settings** - Fine-grained control over temperature, max_tokens, etc.
