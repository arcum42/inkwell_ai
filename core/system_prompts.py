import os
from pathlib import Path


class SystemPromptsManager:
    """Manages system prompts loaded from files in assets/SystemPrompts folder."""
    
    def __init__(self, assets_folder: str = "assets"):
        """Initialize the manager with the assets folder path.
        
        Args:
            assets_folder: Path to the assets folder (default: "assets")
        """
        self.assets_folder = assets_folder
        self.prompts_folder = os.path.join(assets_folder, "SystemPrompts")
        self._ensure_prompts_folder()
    
    def _ensure_prompts_folder(self):
        """Ensure the SystemPrompts folder exists."""
        if not os.path.exists(self.prompts_folder):
            os.makedirs(self.prompts_folder, exist_ok=True)
    
    def get_all_prompts(self) -> dict:
        """Load all system prompts from files.
        
        Returns:
            Dict of {name: content} where name is the filename without extension.
        """
        prompts = {}
        
        if not os.path.exists(self.prompts_folder):
            return prompts
        
        try:
            for filename in os.listdir(self.prompts_folder):
                # Support .txt and .md files
                if filename.endswith(('.txt', '.md')):
                    file_path = os.path.join(self.prompts_folder, filename)
                    
                    # Skip directories
                    if not os.path.isfile(file_path):
                        continue
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        
                        # Use filename without extension as the name
                        name = os.path.splitext(filename)[0]
                        if content:
                            prompts[name] = content
                    except Exception as e:
                        print(f"WARN: Failed to load system prompt {filename}: {e}")
        except Exception as e:
            print(f"WARN: Failed to read system prompts folder: {e}")
        
        return prompts
    
    def get_prompt(self, name: str) -> str | None:
        """Get a specific system prompt by name.
        
        Args:
            name: Name of the prompt (filename without extension)
            
        Returns:
            The prompt content, or None if not found.
        """
        prompts = self.get_all_prompts()
        return prompts.get(name)
    
    def save_prompt(self, name: str, content: str, use_markdown: bool = False) -> bool:
        """Save a system prompt to file.
        
        Args:
            name: Name of the prompt (will be used as filename without extension)
            content: The prompt content
            use_markdown: If True, save as .md file; otherwise use .txt
            
        Returns:
            True if successful, False otherwise.
        """
        if not name or not name.strip():
            return False
        if not content or not content.strip():
            return False
        
        self._ensure_prompts_folder()
        
        # Clean up the name
        clean_name = name.strip()
        extension = ".md" if use_markdown else ".txt"
        filename = clean_name + extension
        file_path = os.path.join(self.prompts_folder, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            return True
        except Exception as e:
            print(f"ERROR: Failed to save system prompt {filename}: {e}")
            return False
    
    def delete_prompt(self, name: str) -> bool:
        """Delete a system prompt file.
        
        Args:
            name: Name of the prompt (filename without extension)
            
        Returns:
            True if successful, False otherwise.
        """
        if not name or not name.strip():
            return False
        
        # Try both .txt and .md extensions
        for ext in ['.txt', '.md']:
            file_path = os.path.join(self.prompts_folder, name.strip() + ext)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    return True
                except Exception as e:
                    print(f"ERROR: Failed to delete system prompt {name}: {e}")
                    return False
        
        return False
    
    def rename_prompt(self, old_name: str, new_name: str) -> bool:
        """Rename a system prompt file.
        
        Args:
            old_name: Current name of the prompt (filename without extension)
            new_name: New name for the prompt
            
        Returns:
            True if successful, False otherwise.
        """
        if not old_name or not new_name:
            return False
        
        # Find the existing file
        old_path = None
        for ext in ['.txt', '.md']:
            candidate = os.path.join(self.prompts_folder, old_name.strip() + ext)
            if os.path.exists(candidate):
                old_path = candidate
                extension = ext
                break
        
        if not old_path:
            return False
        
        new_path = os.path.join(self.prompts_folder, new_name.strip() + extension)
        
        try:
            os.rename(old_path, new_path)
            return True
        except Exception as e:
            print(f"ERROR: Failed to rename system prompt {old_name} to {new_name}: {e}")
            return False
