"""Base provider interface for LLM interactions."""


class LLMProvider:
    """Base class for language model providers."""
    
    # Class attribute indicating if this provider supports streaming responses
    # Default: False (provider implements chat_stream with fallback to chat())
    # Set to True when provider has real streaming implementation
    supports_streaming = False

    # Class attribute indicating if this provider supports structured (JSON schema) output
    # Default: False. Providers should set to True if they can accept a schema
    # and return structured responses matching it.
    supports_structured_output = False
    
    def chat(self, messages, model=None):
        """Send a chat message to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name to use (provider-specific)
            
        Returns:
            String response from the model
        """
        raise NotImplementedError
    
    def chat_stream(self, messages, model=None):
        """Stream chat response tokens as they are generated.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name to use (provider-specific)
            
        Yields:
            String tokens/fragments as they are generated
            
        Default Implementation (when supports_streaming=False):
            Falls back to non-streaming chat() and yields entire response as one chunk.
            This ensures all providers work with streaming infrastructure even if
            they don't have real streaming capability yet.
            
        Real Streaming (when supports_streaming=True):
            Subclass implementation yields tokens as they arrive from the provider.
            Example: LMStudioNativeProvider uses SDK's respond_stream() method.
        """
        response = self.chat(messages, model=model)
        yield response
    
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
