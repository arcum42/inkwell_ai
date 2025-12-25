"""Worker thread for LLM chat responses."""

from PySide6.QtCore import QThread, Signal


class ChatWorker(QThread):
    """Worker thread for handling LLM chat interactions."""
    
    response_received = Signal(str)
    response_chunk = Signal(str)  # Emit answer chunks as they arrive
    response_thinking_start = Signal()  # Signal when model enters thinking phase
    response_thinking_chunk = Signal(str)  # Emit thinking tokens
    response_thinking_done = Signal()  # Signal when thinking phase ends

    def __init__(self, provider, chat_history, model, context, system_prompt, images=None, enabled_tools=None, mode="edit"):
        super().__init__()
        self.provider = provider
        # Create a copy of the history so we don't modify the original reference if we tweak it for the API
        self.chat_history = list(chat_history) 
        self.model = model
        self.context = context
        self.system_prompt = system_prompt
        self.images = images
        self.enabled_tools = enabled_tools  # Optional set of enabled tool names
        self.mode = mode  # "edit" or "ask"

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
            print(f"DEBUG: About to call provider with supports_streaming={self.provider.supports_streaming}")
            print(f"DEBUG: Provider type: {type(self.provider).__name__}")
            
            # Check if provider supports streaming
            if self.provider.supports_streaming:
                # Use streaming - provider has real streaming capability
                full_response = ""
                thinking_started = False
                in_thinking = False
                thinking_buffer = ""

                start_markers = ["<think>", "<THINK>", "<|start_of_thought|>", "<|startofthought|>"]
                end_markers = ["</think>", "<|end_of_thought|>", "<|endofthought|>"]

                def find_first(marker_list, text):
                    positions = [text.find(m) for m in marker_list if m in text]
                    return min([p for p in positions if p != -1], default=-1)

                def marker_len(marker_list, text, idx):
                    for m in marker_list:
                        pos = text.find(m)
                        if pos == idx:
                            return len(m)
                    return 0

                for raw_chunk in self.provider.chat_stream(messages, model=self.model):
                    chunk = str(raw_chunk)
                    # Process markers to separate thinking vs final answer
                    text = chunk
                    while text:
                        if not in_thinking:
                            start_idx = find_first(start_markers, text)
                            if start_idx == -1:
                                # Entire text is normal answer
                                full_response += text
                                self.response_chunk.emit(text)
                                break
                            # Emit any leading answer text before thinking starts
                            leading = text[:start_idx]
                            if leading:
                                full_response += leading
                                self.response_chunk.emit(leading)
                            in_thinking = True
                            if not thinking_started:
                                thinking_started = True
                                self.response_thinking_start.emit()
                            # Skip marker
                            consumed = marker_len(start_markers, text, start_idx)
                            text = text[start_idx + consumed:]
                        else:
                            end_idx = find_first(end_markers, text)
                            if end_idx == -1:
                                # Entire chunk is thinking
                                thinking_buffer += text
                                self.response_thinking_chunk.emit(text)
                                break
                            # Emit thinking up to end marker
                            thinking_part = text[:end_idx]
                            if thinking_part:
                                thinking_buffer += thinking_part
                                self.response_thinking_chunk.emit(thinking_part)
                            # Exit thinking state and skip marker
                            consumed_end = marker_len(end_markers, text, end_idx)
                            in_thinking = False
                            self.response_thinking_done.emit()
                            text = text[end_idx + consumed_end:]

                # If stream ends while still in thinking, close it
                if in_thinking:
                    self.response_thinking_done.emit()
                
                # Emit full response for completion (answer only)
                self.response_received.emit(full_response)
            else:
                # Fall back to non-streaming
                response = self.provider.chat(messages, model=self.model)
                self.response_received.emit(response)
        except Exception as e:
            import traceback
            print(f"ERROR: Exception in ChatWorker.run():")
            traceback.print_exc()
            response = f"Error calling LLM provider: {str(e)}"
            self.response_received.emit(response)
