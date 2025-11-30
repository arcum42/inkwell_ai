import os

class ProjectManager:
    def __init__(self):
        self.root_path = None

    def open_project(self, path):
        """Sets the root path for the project."""
        if os.path.exists(path) and os.path.isdir(path):
            self.root_path = path
            return True
        return False

    def get_root_path(self):
        return self.root_path

    def read_file(self, path):
        """Reads a file. Path can be absolute or relative to root."""
        if not self.root_path:
            raise ValueError("No project opened")
        
        if not os.path.isabs(path):
            full_path = os.path.join(self.root_path, path)
        else:
            full_path = path
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            return None

    def save_file(self, path, content):
        """Saves content to a file. Path can be absolute or relative to root."""
        if not self.root_path:
            raise ValueError("No project opened")
            
        if not os.path.isabs(path):
            full_path = os.path.join(self.root_path, path)
        else:
            full_path = path

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving file {full_path}: {e}")
            return False
