#!/usr/bin/env python3
"""Simple test to verify Ollama connection and response structure."""

import ollama

def test_ollama():
    client = ollama.Client(host="http://localhost:11434")
    
    messages = [
        {"role": "user", "content": "Say hello in 5 words."}
    ]
    
    print("Sending test message to Ollama...")
    try:
        response = client.chat(model="llama3", messages=messages)
        print(f"Response type: {type(response)}")
        print(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
        print(f"Full response: {response}")
        
        if isinstance(response, dict) and 'message' in response:
            print(f"Message type: {type(response['message'])}")
            print(f"Message content: {response['message'].get('content', 'NO CONTENT')}")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_ollama()
