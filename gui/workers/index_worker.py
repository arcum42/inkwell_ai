"""Worker thread for RAG indexing operations."""

from PySide6.QtCore import QThread, Signal
import os


class IndexWorker(QThread):
    """Indexes the entire project with cancel support to allow clean shutdown."""
    
    finished = Signal()
    progress = Signal(int, int, str)  # current, total, current_file

    def __init__(self, rag_engine):
        super().__init__()
        self.rag_engine = rag_engine
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        project_path = self.rag_engine.project_path
        
        # Collect all files to index with their sizes
        files_to_index = []
        for root, dirs, files in os.walk(project_path):
            if ".inkwell_rag" in root:
                continue
            if "/.debug" in root or root.endswith(os.sep + ".debug"):
                continue
            for file in files:
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    if "/.debug/" in path or path.endswith(os.sep + ".debug"):
                        continue
                    try:
                        size = os.path.getsize(path)
                        files_to_index.append((path, size))
                    except Exception:
                        # If we can't get size, add with size 0
                        files_to_index.append((path, 0))
        
        # Sort by size (smallest first)
        files_to_index.sort(key=lambda x: x[1])
        
        total_files = len(files_to_index)
        
        # Index files in order of size
        for current, (path, size) in enumerate(files_to_index, 1):
            if self.is_cancelled:
                break
            
            self.progress.emit(current, total_files, path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if self.is_cancelled:
                    break
                self.rag_engine.index_file(path, content)
            except Exception as e:
                print(f"Error indexing {path}: {e}")
        
        self.finished.emit()
