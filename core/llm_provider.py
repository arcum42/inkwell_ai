import requests
import json
import ollama
# import lmstudio # Commenting out for now until we verify usage, standard OpenAI client is often used for LM Studio but user requested this.
# Actually, let's stick to requests/openai for LM Studio if the library is complex, 
# but for Ollama the library is very simple.
# The user linked https://github.com/lmstudio-ai/lmstudio-python. 
# It seems to be a client SDK.
# Let's implement Ollama first using the library.

class LLMProvider:
    def chat(self, messages, model=None):
        raise NotImplementedError
    
    def list_models(self):
        return []

    def is_vision_model(self, model_name):
        """Heuristic to determine if a model supports vision inputs.
        Subclasses may override for provider-specific checks.
        """
        if not model_name:
            return False
        vision_keywords = [
            'vision', 'llava', 'moondream', 'minicpm', 'yi-vl', 'bakllava',
            'vl', 'multimodal', 'image'
        ]
        name = str(model_name).lower()
        return any(k in name for k in vision_keywords)

class OllamaProvider(LLMProvider):
    def __init__(self, base_url="http://localhost:11434"):
        self.client = ollama.Client(host=base_url.rstrip("/"))

    def chat(self, messages, model="llama3"):
        # Convert messages to format expected by ollama lib if needed
        # The lib expects [{'role': 'user', 'content': '...'}, ...] which matches our internal format
        print(f"DEBUG: Sending chat to Ollama. Model: {model}, URL: {self.client._client.base_url}")
        print(f"DEBUG: Messages structure: {[{k: type(v).__name__ if k != 'content' else (v[:50] + '...' if len(v) > 50 else v) for k, v in msg.items()} for msg in messages]}")
        try:
            response = self.client.chat(model=model, messages=messages)
            print(f"DEBUG: Ollama response type: {type(response)}, keys: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
            # Validate response structure
            if isinstance(response, dict):
                message = response.get('message')
                if isinstance(message, dict):
                    content = message.get('content')
                    if content is not None:
                        return content
                    return f"Error: No content in Ollama response. Response structure: {list(message.keys())}"
                return f"Error: Invalid message format in Ollama response. Type: {type(message)}, Response keys: {list(response.keys())}"
            return f"Error: Ollama returned non-dict response. Type: {type(response)}, Value: {response}"
        except ollama.ResponseError as e:
            return f"Error: {e.error}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {e}"

    def list_models(self):
        try:
            response = self.client.list()
            # response['models'] is a list of objects, usually with a 'model' attribute
            return [m.model for m in response['models']]
        except Exception as e:
            print(f"Error listing models: {e}")
            return []

    def is_vision_model(self, model_name):
        """Detect vision capability for Ollama models.
        Prefer provider metadata; fallback to keyword heuristic.
        """
        if not model_name:
            return False
        # Try to read model details from Ollama
        try:
            info = self.client.show(model=model_name)
            # Capabilities may be present at top-level or under details
            caps = info.get('capabilities')
            if caps is None:
                caps = info.get('details', {}).get('capabilities')
            # Handle list of strings ["completion", "vision"]
            if isinstance(caps, list):
                return any(str(c).lower() == 'vision' for c in caps)
            # Handle dict {"completion": true, "vision": true}
            if isinstance(caps, dict):
                v = caps.get('vision')
                return bool(v)
        except Exception:
            # Ignore and fall back
            pass
        # Fallback heuristic
        vision_keywords = ['vision', 'llava', 'moondream', 'minicpm', 'yi-vl', 'bakllava', 'vl', 'multimodal', 'image']
        return any(k in str(model_name).lower() for k in vision_keywords)

class LMStudioProvider(LLMProvider):
    def __init__(self, base_url="http://localhost:1234"):
        self.base_url = base_url.rstrip("/")

    def chat(self, messages, model="local-model"):
        # LM Studio provides an OpenAI-compatible API
        # Convert messages to handle images in OpenAI format
        converted_messages = []
        for msg in messages:
            new_msg = dict(msg)  # Copy to avoid modifying original
            
            # If message has 'images' field (from Ollama format), convert to OpenAI content blocks
            if 'images' in new_msg:
                images = new_msg.pop('images')  # Remove images key
                content = []
                
                # Add text content if present
                if new_msg.get('content'):
                    content.append({"type": "text", "text": new_msg['content']})
                
                # Add images as content blocks
                for img_b64 in images:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })
                
                new_msg['content'] = content
            else:
                # Ensure content is a plain string for non-vision messages
                if isinstance(new_msg.get('content'), list):
                    try:
                        txt = " ".join(
                            part.get('text', '') if isinstance(part, dict) else str(part)
                            for part in new_msg['content']
                        ).strip()
                        new_msg['content'] = txt or ""
                    except Exception:
                        new_msg['content'] = str(new_msg['content'])
            
            converted_messages.append(new_msg)
        
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": converted_messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as e:
            # Provide more detailed error info
            status = e.response.status_code if e.response is not None else "HTTPError"
            body_text = None
            body_json = None
            try:
                body_json = e.response.json()
            except Exception:
                try:
                    body_text = e.response.text
                except Exception:
                    body_text = None
            # Summarize payload for debugging without dumping full content
            payload_summary = {
                "model": payload.get("model"),
                "messages_count": len(payload.get("messages", [])),
                "last_role": payload.get("messages", [{}])[-1].get("role"),
                "last_content_type": type(payload.get("messages", [{}])[-1].get("content")).__name__,
            }
            # Handle body_json whether it's dict, string, or other
            if body_json is not None:
                if isinstance(body_json, dict):
                    # Extract error message from dict
                    # Try nested error.message first, then top-level error or message
                    if 'error' in body_json:
                        error_val = body_json['error']
                        if isinstance(error_val, dict):
                            msg = error_val.get('message', str(error_val))
                        else:
                            msg = str(error_val)
                    elif 'message' in body_json:
                        msg = str(body_json['message'])
                    else:
                        msg = str(body_json)
                    
                    # Check if this is a context length error and provide helpful info
                    if 'context length' in msg.lower() or 'context overflow' in msg.lower():
                        context_len = self.get_model_context_length(model)
                        if context_len:
                            msg += f"\n\nℹ️ Model '{model}' has context length: {context_len} tokens. Try:\n" \
                                   f"  • Reload model in LM Studio with larger context (e.g., 8192 or 16384)\n" \
                                   f"  • Reduce chat history or RAG context"
                        else:
                            msg += f"\n\nℹ️ Try reloading model '{model}' in LM Studio with larger context length"
                else:
                    msg = str(body_json)
                return f"Error: {status} - {msg}"
            if body_text:
                return f"Error: {status} - {body_text} | Payload: {payload_summary}"
            return f"Error: {status} - {str(e)} | Payload: {payload_summary}"
        except Exception as e:
            return f"Error: {e}"

    def list_models(self):
        """List available models from LM Studio using OpenAI-compatible /v1/models endpoint."""
        try:
            url = f"{self.base_url}/v1/models"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            # Expected shape: {"data": [{"id": "...", ...}, ...]}
            models = []
            for m in data.get("data", []):
                mid = m.get("id") or m.get("model")
                if mid:
                    models.append(mid)
            return models
        except Exception as e:
            print(f"Error listing LM Studio models: {e}")
            return []

    def get_model_context_length(self, model_name):
        """Get the context length for a specific model from LM Studio.
        Returns None if unable to retrieve.
        """
        try:
            url = f"{self.base_url}/v1/models"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            for m in data.get("data", []):
                if m.get("id") == model_name or m.get("model") == model_name:
                    # Try various possible field names for context length
                    return (m.get("max_model_len") or 
                           m.get("context_length") or 
                           m.get("max_context_length") or
                           m.get("n_ctx"))
            return None
        except Exception as e:
            print(f"Error getting model context length: {e}")
            return None

    def is_vision_model(self, model_name):
        """Detect vision capability for LM Studio models via /v1/models metadata.
        Falls back to the base heuristic if unavailable.
        """
        if not model_name:
            return False
        try:
            url = f"{self.base_url}/v1/models"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            for m in data.get('data', []):
                mid = m.get('id') or m.get('model')
                if str(mid) == str(model_name):
                    caps = m.get('capabilities')
                    # list of strings
                    if isinstance(caps, list):
                        return any(str(c).lower() == 'vision' for c in caps)
                    # dict of booleans
                    if isinstance(caps, dict):
                        return bool(caps.get('vision'))
                    break
        except Exception:
            pass
        # Fallback to base heuristic
        return super().is_vision_model(model_name)
