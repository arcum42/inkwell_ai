from PySide6.QtCore import QThread, Signal
from core.tool_base import get_registry
import os


class ToolWorker(QThread):
    """Worker thread for executing LLM tools."""
    
    finished = Signal(str, object) # result_text, extra_data (e.g. image results)

    def __init__(self, tool_name, query, enabled_tools=None, project_manager=None):
        super().__init__()
        self.tool_name = tool_name
        self.query = query
        self.enabled_tools = enabled_tools  # Optional set of allowed tool names
        self.project_manager = project_manager  # For accessing tool settings

    def run(self):
        """Execute the requested tool."""
        try:
            registry = get_registry()
            if self.enabled_tools is not None and self.tool_name not in self.enabled_tools:
                self.finished.emit(f"Error: Tool '{self.tool_name}' is disabled in this project", None)
                return
            tool = registry.get_tool(self.tool_name)
            
            if tool is None:
                self.finished.emit(f"Error: Unknown tool '{self.tool_name}'", None)
                return
            
            if not tool.is_available():
                self.finished.emit(f"Error: Tool '{self.tool_name}' is not available (missing dependencies)", None)
                return
            
            # Get tool settings from project config
            settings = None
            if self.project_manager:
                settings = self.project_manager.get_tool_settings(self.tool_name)
            
            # Execute the tool with settings
            result_text, extra_data = tool.execute(self.query, settings=settings)
            self.finished.emit(result_text, extra_data)
            
        except Exception as e:
            self.finished.emit(f"Tool Error: {e}", None)

class ChatWorker(QThread):
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
            content += "\n\nREMINDER: To propose edits, you MUST use the :::UPDATE path/to/file:::\n...content...\n:::END::: format. Do not just print the code."
            
            # Add Tool Capabilities from registry
            from core.tool_base import get_registry
            tool_instructions = get_registry().get_tool_instructions(self.enabled_tools)
            if tool_instructions:
                content += "\n\n" + tool_instructions
            
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

class BatchWorker(QThread):
    progress_updated = Signal(int, int) # current, total
    finished = Signal(str) # final content
    error_occurred = Signal(str)

    def __init__(self, provider, model, full_content, instruction):
        super().__init__()
        self.provider = provider
        self.model = model
        self.full_content = full_content
        self.instruction = instruction
        self.is_cancelled = False

    def run(self):
        # 1. Split content into chunks
        # Simple splitting by lines (e.g. 50 lines per chunk)
        lines = self.full_content.split('\n')
        chunk_size = 50
        chunks = []
        for i in range(0, len(lines), chunk_size):
            chunks.append("\n".join(lines[i:i+chunk_size]))
            
        if not chunks:
            self.finished.emit("")
            return

        total_chunks = len(chunks)
        final_parts = []
        
        for i, chunk in enumerate(chunks):
            if self.is_cancelled:
                return
                
            self.progress_updated.emit(i + 1, total_chunks)
            
            # Construct prompt for this chunk
            # We treat each chunk as a separate task for now. 
            # Ideally context could be passed, but for "formatting" or "translation" independent chunks are okay.
            prompt = (
                f"You are a file processing assistant. \n"
                f"Instruction: {self.instruction}\n"
                f"Content to process:\n"
                f"```\n{chunk}\n```\n"
                f"Output ONLY the processed content. Do not output code blocks or markdown, just the raw text of the result."
            )
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response = self.provider.chat(messages, model=self.model)
                # Cleanup potential code blocks if LLM adds them despite instructions
                if response.startswith("```"):
                     # Remove first line
                     response = "\n".join(response.split('\n')[1:])
                if response.endswith("```"):
                     # Remove last line
                     response = response[:-3].strip()
                     
                final_parts.append(response)
                
            except Exception as e:
                self.error_occurred.emit(str(e))
                return

        self.finished.emit("\n".join(final_parts))

    def cancel(self):
        self.is_cancelled = True

class IndexWorker(QThread):
    """Indexes the entire project with cancel support to allow clean shutdown."""
    finished = Signal()
    progress = Signal(int, int, str)  # current, total, current_file

    def __init__(self, rag_engine):
        super().__init__()
        self.rag_engine = rag_engine
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        project_path = self.rag_engine.project_path
        
        # Collect all files to index with their sizes
        files_to_index = []
        for root, dirs, files in os.walk(project_path):
            if ".inkwell_rag" in root:
                continue
            for file in files:
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(path)
                        files_to_index.append((path, size))
                    except Exception:
                        # If we can't get size, add with size 0
                        files_to_index.append((path, 0))
        
        # Sort by size (smallest first)
        files_to_index.sort(key=lambda x: x[1])
        
        total_files = len(files_to_index)
        
        # Index files in order of size
        for current, (path, size) in enumerate(files_to_index, 1):
            if self.is_cancelled:
                break
            
            self.progress.emit(current, total_files, path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if self.is_cancelled:
                    break
                self.rag_engine.index_file(path, content)
            except Exception as e:
                print(f"Error indexing {path}: {e}")
        
        self.finished.emit()

