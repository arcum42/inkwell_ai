"""Worker thread for batch processing operations."""

from PySide6.QtCore import QThread, Signal


class BatchWorker(QThread):
    """Worker thread for batch processing content."""
    
    progress_updated = Signal(int, int)  # current, total
    finished = Signal(str)  # final content
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
