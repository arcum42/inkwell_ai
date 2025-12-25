"""Spell-checker with custom dictionary support."""

import re
from spellchecker import SpellChecker
from core.dictionary import CustomDictionary


class InkwellSpellChecker:
    """Spell-checker integrated with custom dictionary."""
    
    def __init__(self, project_root: str | None = None, language: str = 'en'):
        """Initialize spell-checker.
        
        Args:
            project_root: Project root path for project-specific dictionary
            language: Language code (default: 'en' for English)
        """
        self.spell_checker = SpellChecker(language=language)
        self.custom_dict = CustomDictionary(project_root)
        self.project_root = project_root
        self.language = language
        self.enabled = True
        
        # Common technical terms and words to exclude
        self.common_words = {
            'inkwell', 'comfyui', 'ollama', 'lmstudio', 'chromadb',
            'github', 'pytorch', 'python', 'javascript', 'typescript',
            'markdown', 'json', 'yaml', 'html', 'css', 'sql',
            'api', 'http', 'url', 'uri', 'uuid', 'async', 'await',
            'const', 'let', 'var', 'class', 'def', 'import', 'export'
        }
        
        # Add common words and custom dictionary to spell-checker
        self.spell_checker.word_probability.update({word: 1.0 for word in self.common_words})
        self.spell_checker.word_probability.update({word: 1.0 for word in self.custom_dict.get_all_words()})
    
    def check_text(self, text: str) -> set[str]:
        """Check text for misspelled words.
        
        Args:
            text: Text to check
            
        Returns:
            Set of misspelled words
        """
        if not self.enabled:
            return set()
        
        # Extract words (alphanumeric + apostrophes/hyphens)
        words = re.findall(r'\b[a-z]+(?:\'[a-z]+|(?<!\')[-][a-z]+)?\b', text.lower())
        
        # Find misspelled words
        misspelled = self.spell_checker.unknown(words)
        
        # Remove words from custom dictionary
        misspelled = {word for word in misspelled if not self.custom_dict.contains(word)}
        
        return misspelled
    
    def get_corrections(self, word: str, max_suggestions: int = 5) -> list[str]:
        """Get correction suggestions for a word.
        
        Args:
            word: Misspelled word
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of suggested corrections
        """
        suggestions = self.spell_checker.correction(word)
        if isinstance(suggestions, str):
            return [suggestions]
        
        # Get multiple suggestions
        known = self.spell_checker.known([word])
        if known:
            return list(known)[:max_suggestions]
        
        # Fallback: use edit distance
        candidates = self.spell_checker.candidates(word)
        if candidates:
            return sorted(list(candidates))[:max_suggestions]
        
        return []
    
    def add_word_to_custom_dict(self, word: str):
        """Add word to custom dictionary.
        
        Args:
            word: Word to add
        """
        self.custom_dict.add_word(word)
        # Also add to spell-checker's known words
        self.spell_checker.word_probability[word.lower()] = 1.0
    
    def remove_word_from_custom_dict(self, word: str):
        """Remove word from custom dictionary.
        
        Args:
            word: Word to remove
        """
        self.custom_dict.remove_word(word)
        # Also remove from spell-checker
        if word.lower() in self.spell_checker.word_probability:
            del self.spell_checker.word_probability[word.lower()]
    
    def get_custom_words(self) -> list[str]:
        """Get all words in custom dictionary.
        
        Returns:
            Sorted list of custom words
        """
        return self.custom_dict.get_all_words()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable spell-checking.
        
        Args:
            enabled: Whether to enable spell-checking
        """
        self.enabled = enabled
    
    def is_enabled(self) -> bool:
        """Check if spell-checking is enabled.
        
        Returns:
            True if enabled
        """
        return self.enabled
