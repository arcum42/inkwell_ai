from PySide6.QtCore import QThread, Signal
from core.tools import WebReader, WebSearcher, WikiTool, ImageSearcher
import os

class ToolWorker(QThread):
    finished = Signal(str, object) # result_text, extra_data (e.g. image results)

    def __init__(self, tool_name, query):
        super().__init__()
        self.tool_name = tool_name
        self.query = query

    def run(self):
        try:
            result_text = ""
            extra_data = None
            
            if self.tool_name == "WEB_READ":
                reader = WebReader()
                result_text = reader.read(self.query)
            elif self.tool_name == "SEARCH":
                searcher = WebSearcher()
                result_text = searcher.search(self.query)
            elif self.tool_name == "WIKI":
                wiki = WikiTool()
                result_text = wiki.search(self.query)
            elif self.tool_name == "IMAGE":
                img = ImageSearcher()
                results = img.search(self.query)
                if isinstance(results, str): # Error message
                    result_text = results
                else:
                    result_text = f"Found {len(results)} images. Asking user to select..."
                    extra_data = results
            
            self.finished.emit(result_text, extra_data)
        except Exception as e:
            self.finished.emit(f"Tool Error: {e}", None)

class ChatWorker(QThread):
    response_received = Signal(str)

    def __init__(self, provider, chat_history, model, context, system_prompt, images=None):
        super().__init__()
        self.provider = provider
        # Create a copy of the history so we don't modify the original reference if we tweak it for the API
        self.chat_history = list(chat_history) 
        self.model = model
        self.context = context
        self.system_prompt = system_prompt
        self.images = images

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
            
            # Add Tool Capabilities
            content += (
                "\n\nYou have access to the following tools:\n"
                "1. Read Web Page: :::TOOL:WEB_READ:https://url...::: (Use this for full article content)\n"
                "2. Web Search: :::TOOL:SEARCH:query...:::\n"
                "3. Wikipedia: :::TOOL:WIKI:query...::: (Returns summary only. Use WEB_READ on the returned link for full details)\n"
                "4. Image Search: :::TOOL:IMAGE:query...:::\n"
                "Use these formats to request information or images. Stop generating after the tool command."
            )
            
            msg = {"role": last_msg['role'], "content": content}
            if self.images:
                msg['images'] = self.images
            messages.append(msg)

        try:
            response = self.provider.chat(messages, model=self.model)
        except Exception as e:
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

    def __init__(self, rag_engine):
        super().__init__()
        self.rag_engine = rag_engine
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        project_path = self.rag_engine.project_path
        for root, dirs, files in os.walk(project_path):
            if self.is_cancelled:
                break
            if ".inkwell_rag" in root:
                continue
            for file in files:
                if self.is_cancelled:
                    break
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if self.is_cancelled:
                            break
                        self.rag_engine.index_file(path, content)
                    except Exception as e:
                        print(f"Error indexing {path}: {e}")
        self.finished.emit()

