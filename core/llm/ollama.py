"""Ollama provider implementation."""

import ollama
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Provider for local Ollama models."""
    
    def __init__(self, base_url="http://localhost:11434"):
        """Initialize Ollama provider.
        
        Args:
            base_url: Base URL of Ollama service
        """
        self.client = ollama.Client(host=base_url.rstrip("/"))

    def chat(self, messages, model="llama3"):
        """Send chat message to Ollama.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name
            
        Returns:
            Response text from model
        """
        print(f"DEBUG: Sending chat to Ollama. Model: {model}, URL: {self.client._client.base_url}")
        print(f"DEBUG: Messages structure: {[{k: type(v).__name__ if k != 'content' else (v[:50] + '...' if len(v) > 50 else v) for k, v in msg.items()} for msg in messages]}")
        try:
            response = self.client.chat(model=model, messages=messages)
            # Normalize response to a plain string content
            print(f"DEBUG: Ollama response type: {type(response)}, keys: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
            # Dict shape
            if isinstance(response, dict):
                message = response.get('message')
                if isinstance(message, dict):
                    content = message.get('content')
                    if content is not None:
                        return content
                    return f"Error: No content in Ollama response. Response structure: {list(message.keys())}"
                # Some versions may return a Message object inside dict
                if hasattr(message, 'content'):
                    return getattr(message, 'content')
                return f"Error: Invalid message format in Ollama response. Type: {type(message)}, Response keys: {list(response.keys())}"
            # Object shape (ollama._types.ChatResponse)
            if hasattr(response, 'message'):
                msg = getattr(response, 'message')
                if isinstance(msg, dict):
                    content = msg.get('content')
                    if content is not None:
                        return content
                if hasattr(msg, 'content'):
                    return getattr(msg, 'content')
            # Fallback to string
            if hasattr(response, 'content'):
                return str(getattr(response, 'content'))
            return str(response)
        except ollama.ResponseError as e:
            return f"Error: {e.error}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {e}"

    def list_models(self):
        """List available Ollama models.
        
        Returns:
            List of model names
        """
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
        
        Args:
            model_name: Name of the model
            
        Returns:
            True if model supports vision
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
