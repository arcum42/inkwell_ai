"""Worker thread for LLM chat responses."""

from PySide6.QtCore import QThread, Signal


class ChatWorker(QThread):
    """Worker thread for handling LLM chat interactions."""
    
    response_received = Signal(str)

    def __init__(self, provider, chat_history, model, context, system_prompt, images=None, enabled_tools=None):
        super().__init__()
        self.provider = provider
        # Create a copy of the history so we don't modify the original reference if we tweak it for the API
        self.chat_history = list(chat_history) 
        self.model = model
        self.context = context
        self.system_prompt = system_prompt
        self.images = images
        self.enabled_tools = enabled_tools  # Optional set of enabled tool names

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
                context_chunks = []
                footnotes = []
                for idx, chunk in enumerate(self.context, 1):
                    if isinstance(chunk, dict):
                        chunk_text = chunk.get("text", "")
                        meta = chunk.get("metadata", {})
                        source = meta.get("source", "unknown")
                        start_line = meta.get("start_line")
                        end_line = meta.get("end_line")
                        heading_path = " > ".join(meta.get("heading_path", [])) if meta.get("heading_path") else ""
                        line_str = ""
                        if start_line is not None and end_line is not None:
                            line_str = f"#L{start_line}-L{end_line}"
                        footnote = f"[^{idx}]: {source}{line_str}"
                        if heading_path:
                            footnote += f" — {heading_path}"
                        context_chunks.append(f"[^{idx}] {chunk_text}")
                        footnotes.append(footnote)
                    else:
                        context_chunks.append(str(chunk))

                context_str = "\n\n".join(context_chunks)
                if footnotes:
                    footnote_block = "\n".join(footnotes)
                    context_str += f"\n\nCitations:\n{footnote_block}"
                    content += "\n\nWhen referencing context, include footnotes like [^1] that match the Citations section."
                content += f"\n\nContext:\n{context_str}"

            # Reinforce the edit format instructions
            content += (
                "\n\nREMINDER: Prefer compact PATCH directives when small changes suffice. "
                "PATCH syntax: :::PATCH path:::\\nL42: old => new\\n...\\n:::END::: . "
                "Use :::UPDATE path:::\\n<full content>\\n:::END::: only when needed."
            )
            
            # Add Tool Capabilities from registry
            from core.tool_base import get_registry
            tool_instructions = get_registry().get_tool_instructions(self.enabled_tools)
            if tool_instructions:
                content += "\n\n" + tool_instructions
                print(f"DEBUG: Added tool instructions to prompt (enabled_tools={self.enabled_tools})")
            else:
                print(f"DEBUG: No tool instructions available (enabled_tools={self.enabled_tools})")
            
            msg = {"role": last_msg['role'], "content": content}
            if self.images:
                msg['images'] = self.images
            messages.append(msg)

        try:
            print(f"DEBUG: About to call provider.chat with model={self.model}")
            print(f"DEBUG: Provider type: {type(self.provider).__name__}")
            response = self.provider.chat(messages, model=self.model)
            print(f"DEBUG: Got response type: {type(response).__name__}")
        except Exception as e:
            import traceback
            print(f"ERROR: Exception in ChatWorker.run():")
            traceback.print_exc()
            response = f"Error calling LLM provider: {str(e)}"
            
        self.response_received.emit(response)
