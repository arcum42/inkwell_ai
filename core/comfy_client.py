import requests
import json
import time
import urllib.request
import urllib.parse

class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188"):
        self.base_url = base_url

    def queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow}
        data = json.dumps(p).encode('utf-8')
        try:
            req = urllib.request.Request(f"{self.base_url}/prompt", data=data)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"Error queuing prompt: {e}")
            return None

    def get_history(self, prompt_id):
        try:
            with urllib.request.urlopen(f"{self.base_url}/history/{prompt_id}") as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"Error getting history: {e}")
            return None

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        try:
            with urllib.request.urlopen(f"{self.base_url}/view?{url_values}") as response:
                return response.read()
        except Exception as e:
            print(f"Error getting image: {e}")
            return None
