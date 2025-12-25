"""Base provider interface for LLM interactions."""


class LLMProvider:
    """Base class for language model providers."""
    
    def chat(self, messages, model=None):
        """Send a chat message to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name to use (provider-specific)
            
        Returns:
            String response from the model
        """
        raise NotImplementedError
    
    def list_models(self):
        """List available models.
        
        Returns:
            List of model names
        """
        return []

    def get_model_context_length(self, model_name):
        """Return the model context length if known; default None.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Context length in tokens, or None if unknown
        """
        return None

    def is_vision_model(self, model_name):
        """Heuristic to determine if a model supports vision inputs.
        Subclasses may override for provider-specific checks.
        
        Args:
            model_name: Name of the model
            
        Returns:
            True if the model supports vision inputs
        """
        if not model_name:
            return False
        vision_keywords = [
            'vision', 'llava', 'moondream', 'minicpm', 'yi-vl', 'bakllava',
            'vl', 'multimodal', 'image'
        ]
        name = str(model_name).lower()
        return any(k in name for k in vision_keywords)
