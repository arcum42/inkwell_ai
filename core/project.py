import os
import base64
import json

class ProjectManager:
    def __init__(self):
        self.root_path = None
        self.tool_config = {}

    def open_project(self, path):
        """Sets the root path for the project."""
        if os.path.exists(path) and os.path.isdir(path):
            self.root_path = path
            self._load_tool_config()
            return True
        return False

    def _load_tool_config(self):
        """Load project-level tool configuration from .inkwell/config.json if present."""
        self.tool_config = {}
        if not self.root_path:
            return
        config_path = os.path.join(self.root_path, '.inkwell', 'config.json')
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.tool_config = data
        except Exception as e:
            print(f"WARN: Failed to load tool config {config_path}: {e}")

    def get_enabled_tools(self):
        """Return a set of enabled tool names, or None to allow all tools."""
        enabled = self.tool_config.get('enabled_tools') if isinstance(self.tool_config, dict) else None
        if isinstance(enabled, list):
            return set(enabled)
        return None

    def get_tool_settings(self, tool_name):
        """Return per-tool settings dict, or empty dict."""
        if not isinstance(self.tool_config, dict):
            return {}
        settings = self.tool_config.get('tool_settings', {})
        if isinstance(settings, dict):
            value = settings.get(tool_name, {})
            return value if isinstance(value, dict) else {}
        return {}

    def set_enabled_tools(self, enabled_list):
        """Update in-memory enabled tools list (None allows all)."""
        if enabled_list is None:
            self.tool_config['enabled_tools'] = None
        elif isinstance(enabled_list, (list, set)):
            self.tool_config.setdefault('enabled_tools', [])
            self.tool_config['enabled_tools'] = list(enabled_list)
        else:
            # invalid input; ignore
            pass

    def set_tool_settings(self, settings_dict):
        """Replace per-tool settings in memory with provided dict."""
        if isinstance(settings_dict, dict):
            self.tool_config['tool_settings'] = settings_dict

    def save_tool_config(self):
        """Persist current tool_config to .inkwell/config.json."""
        if not self.root_path:
            return False
        config_dir = os.path.join(self.root_path, '.inkwell')
        config_path = os.path.join(config_dir, 'config.json')
        try:
            os.makedirs(config_dir, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.tool_config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tool config {config_path}: {e}")
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

    def get_project_structure(self):
        """Returns a string representation of the project file structure."""
        if not self.root_path:
            return "No project opened."
            
        structure = []
        ignore_dirs = {'.git', '.idea', '__pycache__', 'venv', 'node_modules', '.gemini'}
        
        for root, dirs, files in os.walk(self.root_path):
            # Modify dirs in-place to exclude ignored
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            level = root.replace(self.root_path, '').count(os.sep)
            indent = '  ' * level
            if level == 0:
                structure.append(f"{os.path.basename(root)}/")
            else:
                structure.append(f"{indent}{os.path.basename(root)}/")
                
            subindent = '  ' * (level + 1)
            for f in files:
                structure.append(f"{subindent}{f}")
                
        return "\n".join(structure)

    def get_image_base64(self, path):
        """Reads an image file and returns base64 encoded string."""
        if not self.root_path:
            return None
            
        if not os.path.isabs(path):
            full_path = os.path.join(self.root_path, path)
        else:
            full_path = path

        if not os.path.exists(full_path):
            return None

        try:
            with open(full_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error reading image {full_path}: {e}")
            return None

    def find_images_in_text(self, text, max_images=10):
        """
        Scans project for images and returns paths of images mentioned in the text.
        Also handles 'all images' requests.
        """
        if not self.root_path:
            return []
            
        found_images = []
        all_images = []
        text_lower = text.lower()
        
        # Define image extensions
        valid_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        
        # Walk through project to find all images
        for root, dirs, files in os.walk(self.root_path):
            # Exclude hidden/ignored dirs (simple check)
            if any(part.startswith('.') for part in root.split(os.sep)):
                continue
                
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in valid_exts:
                    full_path = os.path.join(root, file)
                    all_images.append(full_path)
                    
                    # check for specific mention
                    # We check if filename (with or without extension) is in text
                    # "roseluck.png" or "roseluck"
                    fname = file.lower()
                    fname_no_ext = os.path.splitext(file)[0].lower()
                    
                    # Simple inclusion check. 
                    # Use word boundaries if possible, but basic strings for now.
                    if fname in text_lower or (len(fname_no_ext) > 3 and fname_no_ext in text_lower):
                        found_images.append(full_path)
        
        # Check for "all images" trigger
        triggers = ["all images", "all the images", "all pictures", "every image"]
        if any(t in text_lower for t in triggers):
            print(f"DEBUG: 'All images' trigger found. Returning {len(all_images)} images (max {max_images}).")
            return all_images[:max_images]
            
        return found_images
