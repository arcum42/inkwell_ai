"""Custom dictionary management for spell-checking."""

import os
import json
from pathlib import Path


class CustomDictionary:
    """Manages a persistent custom dictionary for spell-checking."""
    
    def __init__(self, project_root: str | None = None):
        """Initialize custom dictionary.
        
        Args:
            project_root: Project root path. If provided, uses project-specific dictionary.
                         Otherwise uses global dictionary in user home.
        """
        self.project_root = project_root
        self.words = set()
        self.dictionary_path = self._get_dictionary_path()
        self._ensure_directory()
        self.load()
    
    def _get_dictionary_path(self) -> Path:
        """Get path to dictionary file."""
        if self.project_root:
            # Project-specific dictionary
            return Path(self.project_root) / ".inkwell" / "custom_dictionary.json"
        else:
            # Global dictionary in user home
            home = Path.home()
            return home / ".inkwell" / "custom_dictionary.json"
    
    def _ensure_directory(self):
        """Ensure directory exists."""
        self.dictionary_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self):
        """Load dictionary from file."""
        if self.dictionary_path.exists():
            try:
                with open(self.dictionary_path, 'r') as f:
                    data = json.load(f)
                    self.words = set(data.get('words', []))
            except Exception as e:
                print(f"Error loading custom dictionary: {e}")
                self.words = set()
        else:
            self.words = set()
    
    def save(self):
        """Save dictionary to file."""
        try:
            data = {'words': sorted(list(self.words))}
            with open(self.dictionary_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving custom dictionary: {e}")
    
    def add_word(self, word: str):
        """Add a word to the dictionary.
        
        Args:
            word: Word to add
        """
        if word and word.lower() not in self.words:
            self.words.add(word.lower())
            self.save()
    
    def remove_word(self, word: str):
        """Remove a word from the dictionary.
        
        Args:
            word: Word to remove
        """
        self.words.discard(word.lower())
        self.save()
    
    def contains(self, word: str) -> bool:
        """Check if word is in dictionary.
        
        Args:
            word: Word to check
            
        Returns:
            True if word is in dictionary
        """
        return word.lower() in self.words
    
    def get_all_words(self) -> list[str]:
        """Get all words in dictionary.
        
        Returns:
            Sorted list of words
        """
        return sorted(list(self.words))
    
    def clear(self):
        """Clear all words from dictionary."""
        self.words = set()
        self.save()
