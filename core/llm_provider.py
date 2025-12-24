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
        try:
            response = self.client.chat(model=model, messages=messages)
            return response['message']['content']
        except ollama.ResponseError as e:
            return f"Error: {e.error}"
        except Exception as e:
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
            
            converted_messages.append(new_msg)
        
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": converted_messages,
            "temperature": 0.7
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as e:
            # Provide more detailed error info
            try:
                error_detail = e.response.json()
                return f"Error: {e.response.status_code} - {error_detail.get('error', {}).get('message', str(e))}"
            except:
                return f"Error: {e}"
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
