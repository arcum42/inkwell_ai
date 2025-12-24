from PySide6.QtCore import QThread, Signal

class ChatWorker(QThread):
    response_received = Signal(str)

    def __init__(self, provider, chat_history, model, context, system_prompt):
        super().__init__()
        self.provider = provider
        # Create a copy of the history so we don't modify the original reference if we tweak it for the API
        self.chat_history = list(chat_history) 
        self.model = model
        self.context = context
        self.system_prompt = system_prompt

    def run(self):
        # Construct the messages list for the LLM
        messages = []

        # 1. System Prompt
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 2. History (excluding the last message which we might want to augment with context)
        if len(self.chat_history) > 0:
            messages.extend(self.chat_history[:-1])
            
            # 3. Last User Message + RAG Context
            last_msg = self.chat_history[-1]
            content = last_msg['content']
            
            if self.context:
                # Assuming context is a list of strings (chunks)
                context_str = "\n\n".join(self.context)
                content += f"\n\nContext:\n{context_str}"

            # Reinforce the edit format instructions
            content += "\n\nREMINDER: To propose edits, you MUST use the :::UPDATE path/to/file:::\n...content...\n:::END::: format. Do not just print the code."
            
            messages.append({"role": last_msg['role'], "content": content})

        try:
            response = self.provider.chat(messages, model=self.model)
        except Exception as e:
            response = f"Error calling LLM provider: {str(e)}"
            
        self.response_received.emit(response)
