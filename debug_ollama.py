import ollama
import sys

try:
    client = ollama.Client(host="http://localhost:11434")
    print("--- Listing Models ---")
    models = client.list()
    print(f"Type of models: {type(models)}")
    print(f"Raw models response: {models}")
    
    if 'models' in models:
        for m in models['models']:
            print(f"Model item: {m}")
            
except Exception as e:
    print(f"Error: {e}")
