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

class LMStudioProvider(LLMProvider):
    def __init__(self, base_url="http://localhost:1234"):
        self.base_url = base_url.rstrip("/")

    def chat(self, messages, model="local-model"):
        # LM Studio provides an OpenAI-compatible API
        # We can use requests to hit /v1/chat/completions
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error: {e}"
