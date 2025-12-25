# LLM Provider Documentation Reference

**Purpose:** Central reference for documentation and resources for each LLM provider integrated into Inkwell AI.

**Last Updated:** December 25, 2025

---

## LM Studio Native SDK Provider

**Status:** ✅ Actively Implemented  
**Provider Class:** `core/llm/lm_studio_native.py`  
**Package:** `lmstudio` (PyPI)

### Documentation

#### Main Documentation
- **Developer Docs Home:** https://lmstudio.ai/docs/developer
  - Overview of LM Studio platform and APIs
  - Links to all developer documentation

#### Python SDK Documentation
- **Python SDK Overview:** https://lmstudio.ai/docs/python
  - Official Python SDK documentation
  - Installation and setup information
  - API reference for Python

- **Getting Started:** https://lmstudio.ai/docs/python/getting-started/project-setup
  - Environment setup
  - Installation via pip
  - Basic project configuration
  - **Used for:** Initial setup and environment configuration

#### Core Features
- **Chat Completion:** https://lmstudio.ai/docs/python/llm-prediction/chat-completion
  - Chat API usage
  - Message format and structure
  - Response handling
  - **Used for:** Base `chat()` and `chat_stream()` implementations
  - **Streaming:** Uses `respond_stream()` method (mentioned in this section)
  - **Key Classes:** `lms.Chat`, `lms.ChatMessage`, fragment objects

- **Image Input:** https://lmstudio.ai/docs/python/llm-prediction/image-input
  - Vision model support
  - Image format conversion (base64 to bytes)
  - **Used for:** `_build_chat_context()` vision handling in native provider
  - **Key Methods:** Vision message construction, base64 image encoding

- **Structured Response:** https://lmstudio.ai/docs/python/llm-prediction/structured-response
  - JSON/structured output generation
  - `response_format` parameter
  - Validation and parsing
  - **Future Enhancement:** Can enable structured output for deterministic responses

#### Agent Features
- **Agent.act():** https://lmstudio.ai/docs/python/agent/act
  - Agentic capabilities
  - Function calling and tool use
  - Action planning and execution
  - **Future Enhancement:** For tool-calling workflows

- **Agent Tools:** https://lmstudio.ai/docs/python/agent/tools
  - Tool/function definition
  - Tool parameter specification
  - Result handling
  - **Future Enhancement:** Integration with Inkwell AI tool system

### Key Implementation Details

**Chat Context Building:**
- Methods use `_build_chat_context()` to convert messages to `lms.Chat` objects
- Vision images are converted from base64 to bytes
- Message roles (user/assistant/system) map to `lms.ChatMessage` types

**Streaming Implementation:**
- Uses `respond_stream()` method on llm model
- Returns fragment objects with `.content` attribute
- Yields tokens as they arrive (true streaming)
- No buffering—responsive for long responses

**Client Initialization:**
- Format: `lms.llm(model_name)` to get model handle
- No explicit connection needed (handles connection internally)
- Localhost:1234 by default (configurable via environment)

---

## Ollama Provider

**Status:** ✅ Implemented (Non-Streaming Currently)  
**Provider Class:** `core/llm/ollama.py`  
**Package:** `ollama` (PyPI)

### Documentation

#### Main Resources
- **GitHub Repository:** https://github.com/ollama/ollama-python
  - Official Python client for Ollama
  - Source code reference
  - Issue tracking
  - **Used for:** API reference and implementation examples

- **Examples Directory:** https://github.com/ollama/ollama-python/tree/main/examples
  - Chat example
  - Streaming example
  - Multi-modal example
  - Function calling example
  - **Used for:** Code samples and best practices

- **Ollama Documentation:** https://docs.ollama.com/
  - Model information
  - API reference
  - Deployment guides
  - Model library
  - **Used for:** Available models and general information

### Key Implementation Details

**Client Initialization:**
- `client = Client(host="http://localhost:11434")`
- Handles connection to local Ollama instance
- Fallback if not running

**Chat API:**
- `client.chat(model=model, messages=messages)`
- Message format: `{"role": "...", "content": "..."}`
- Returns response dict with message content

**Streaming Support:**
- `client.chat(model=model, messages=messages, stream=True)`
- Returns generator of response chunks
- Each chunk has `message.content` with partial response
- **Current Status:** Implemented but `supports_streaming = False` (fallback used)
- **Can Enable:** Set `supports_streaming = True` and use streaming in `chat_stream()` method

**Vision Support:**
- Multi-modal capable for supported models
- Images passed as base64 in messages
- Model detection via `client.list()` model list

---

## LM Studio OpenAI-Compatible Provider

**Status:** ✅ Implemented (Non-Streaming Currently)  
**Provider Class:** `core/llm/lm_studio.py`  
**Package:** `requests` (standard library for HTTP)

### Documentation

#### OpenAI API Documentation (Compatibility Layer)
- **OpenAI API Reference:** https://platform.openai.com/docs/api-reference
  - Chat Completions endpoint
  - Message format
  - Response format
  - Parameters and options

- **LM Studio OpenAI Compatibility:** https://lmstudio.ai/docs/python
  - LM Studio provides OpenAI-compatible endpoints
  - Localhost:1234/v1/chat/completions
  - Same API as OpenAI models (when streaming is enabled)

### Key Implementation Details

**Endpoint Configuration:**
- Default: `http://localhost:1234/v1/chat/completions`
- REST-based (no SDK needed, uses requests library)
- Configurable base URL

**API Request Format:**
- POST to `/v1/chat/completions`
- JSON payload with:
  - `model`: Model name
  - `messages`: List of message objects
  - `temperature`, `max_tokens`: Generation parameters
  - `stream`: Boolean flag for streaming

**Response Handling:**
- JSON response with `choices[0].message.content`
- Non-streaming: Single response object
- Streaming: Server-Sent Events (SSE) format

**Streaming Support (Future):**
- Set `stream=True` in payload
- Response returns Server-Sent Events
- Parse `data: {...}` lines with JSON
- **Current Status:** `supports_streaming = False` (fallback used)
- **Can Enable:** Implement SSE parsing in `chat_stream()` method

**Vision Support:**
- Uses base64 image encoding in message content
- Messages can include image URLs or base64 data
- Vision-capable models detect via metadata endpoint

---

## Documentation Organization by Feature

### Chat Completion
| Provider | Link | Status |
|----------|------|--------|
| LM Studio Native | https://lmstudio.ai/docs/python/llm-prediction/chat-completion | ✅ Implemented |
| Ollama | https://github.com/ollama/ollama-python/tree/main/examples | ✅ Implemented |
| LM Studio OpenAI | https://platform.openai.com/docs/api-reference/chat/create | ✅ Implemented |

### Streaming Responses
| Provider | Link | Status |
|----------|------|--------|
| LM Studio Native | https://lmstudio.ai/docs/python/llm-prediction/chat-completion | ✅ Implemented |
| Ollama | https://github.com/ollama/ollama-python/tree/main/examples | 🔄 Ready to enable |
| LM Studio OpenAI | https://platform.openai.com/docs/api-reference/chat/create | 🔄 Ready to enable |

### Vision/Multi-Modal
| Provider | Link | Status |
|----------|------|--------|
| LM Studio Native | https://lmstudio.ai/docs/python/llm-prediction/image-input | ✅ Implemented |
| Ollama | https://docs.ollama.com/ | ✅ Supported |
| LM Studio OpenAI | https://platform.openai.com/docs/guides/vision | ✅ Supported |

### Structured Output
| Provider | Link | Status |
|----------|------|--------|
| LM Studio Native | https://lmstudio.ai/docs/python/llm-prediction/structured-response | 📋 Planned |
| Ollama | https://docs.ollama.com/ | 📋 Research needed |
| LM Studio OpenAI | https://platform.openai.com/docs/guides/json-mode | 📋 Planned |

### Tool Calling / Agent Features
| Provider | Link | Status |
|----------|------|--------|
| LM Studio Native | https://lmstudio.ai/docs/python/agent/tools | 📋 Planned |
| Ollama | https://docs.ollama.com/ | 📋 Research needed |
| LM Studio OpenAI | https://platform.openai.com/docs/guides/function-calling | 📋 Planned |

---

## Reference Materials

### LM Studio Native Python SDK
**Repository:** https://github.com/LMStudio-ai/lmstudio-python  
**PyPI Package:** https://pypi.org/project/lmstudio/  
**Latest Docs:** https://lmstudio.ai/docs/python

**Quick Reference:**
```python
import lmstudio as lms

# Chat
llm = lms.llm("model-name")
chat = lms.Chat()
chat.user("Hello")
response = llm.respond(chat)

# Streaming
for fragment in llm.respond_stream(chat):
    print(fragment.content, end="", flush=True)
```

### Ollama Python Client
**Repository:** https://github.com/ollama/ollama-python  
**PyPI Package:** https://pypi.org/project/ollama/  
**Examples:** https://github.com/ollama/ollama-python/tree/main/examples

**Quick Reference:**
```python
from ollama import Client

client = Client(host="http://localhost:11434")

# Chat
response = client.chat(
    model="llama2",
    messages=[{"role": "user", "content": "Hi!"}]
)

# Streaming
for chunk in client.chat(
    model="llama2",
    messages=[...],
    stream=True
):
    print(chunk["message"]["content"], end="", flush=True)
```

### OpenAI API (LM Studio Compatible)
**Documentation:** https://platform.openai.com/docs/api-reference  
**Chat Completions:** https://platform.openai.com/docs/api-reference/chat/create

**Quick Reference:**
```python
import requests
import json

# Chat
response = requests.post(
    "http://localhost:1234/v1/chat/completions",
    json={
        "model": "local-model",
        "messages": [{"role": "user", "content": "Hi!"}]
    }
)
print(response.json()["choices"][0]["message"]["content"])

# Streaming
response = requests.post(
    "http://localhost:1234/v1/chat/completions",
    json={...,"stream": True},
    stream=True
)
for line in response.iter_lines():
    if line.startswith("data: "):
        print(json.loads(line[6:]))
```

---

## Notes for Implementation

### When Implementing New Features
1. **Check Relevant Documentation**
   - LM Studio Native: Check https://lmstudio.ai/docs/python for exact API
   - Ollama: Check https://github.com/ollama/ollama-python/tree/main/examples
   - OpenAI-compatible: Check https://platform.openai.com/docs/api-reference

2. **Streaming Implementation**
   - LM Studio Native: Use `respond_stream()` (already done)
   - Ollama: Use `client.chat(..., stream=True)` and iterate
   - OpenAI-compatible: Parse SSE format with `data: {...}` lines

3. **Vision Support**
   - All three providers support vision/multi-modal
   - Base64 encoding required for image transfer
   - Check documentation for exact message format

4. **Tool Calling**
   - LM Studio Native: Use `agent.act()` with tool definitions
   - Ollama: Limited, check latest docs
   - OpenAI-compatible: Use function calling format

### When Debugging Issues
1. Check provider documentation links for API changes
2. Reference example code in GitHub repositories
3. Consult official API documentation for latest features
4. Test with simple chat first, then add features

---

## Future Reference Updates

**Last Checked:** December 25, 2025

**To Update:** Check for new versions of:
- LM Studio Python SDK
- Ollama Python Client
- OpenAI API changes

**Known Limitations:**
- Documentation links may change over time
- Feature availability depends on provider versions
- Some features may require specific model versions
