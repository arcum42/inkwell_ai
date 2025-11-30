import requests
import json
import time
import urllib.request
import urllib.parse
import uuid
import websocket # pip install websocket-client

class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188"):
        self.base_url = base_url
        self.client_id = str(uuid.uuid4())
        self.ws = None

    def connect(self):
        # Extract host:port from base_url
        # base_url is http://host:port
        host = self.base_url.replace("http://", "").replace("https://", "")
        ws_url = f"ws://{host}/ws?clientId={self.client_id}"
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(ws_url)
            return True
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self.ws = None
            return False

    def disconnect(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        print(f"DEBUG: Sending prompt payload: {json.dumps(p, indent=2)}")
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

    def generate_image(self, workflow):
        """
        Full generation loop: Queue -> Wait -> Download
        Returns a list of image bytes.
        """
        if not self.ws:
            if not self.connect():
                return None

        # Queue Prompt
        response = self.queue_prompt(workflow)
        if not response:
            return None
        
        prompt_id = response['prompt_id']
        print(f"DEBUG: Queued prompt {prompt_id}")
        
        # Wait for completion
        while True:
            try:
                out = self.ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break # Execution is done
            except Exception as e:
                print(f"WebSocket receive error: {e}")
                break
        
        # Fetch History
        history = self.get_history(prompt_id)
        if not history:
            return []
            
        history = history[prompt_id]
        images_output = []
        
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                    if image_data:
                        images_output.append(image_data)
                        
        return images_output
