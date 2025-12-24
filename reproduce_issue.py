import sys
import os

# Mock PySide6 components since we are in headless environment
from unittest.mock import MagicMock
sys.modules["PySide6"] = MagicMock()
sys.modules["PySide6.QtCore"] = MagicMock()
sys.modules["PySide6.QtWidgets"] = MagicMock()
sys.modules["PySide6.QtGui"] = MagicMock()

# Now we can import the worker
# We need to fix the import in workers.py locally or mock it? 
# workers.py imports: from PySide6.QtCore import QThread, Signal
# Our mock above should handle it.

# However, QThread needs to be a class we can inherit from
class MockQThread:
    def __init__(self):
        pass
    def start(self):
        self.run()

sys.modules["PySide6.QtCore"].QThread = MockQThread
sys.modules["PySide6.QtCore"].Signal = lambda *args: MagicMock()

from gui.workers import ChatWorker

class MockProvider:
    def chat(self, messages, model=None):
        return "Mock response"

def test_worker():
    provider = MockProvider()
    history = [{"role": "user", "content": "Hello"}]
    model = "test-model"
    context = []
    system_prompt = "SYSTEM PROMPT: You are a coding assistant."
    
    worker = ChatWorker(provider, history, model, context, system_prompt)
    print("Running worker...")
    worker.run()

if __name__ == "__main__":
    test_worker()
