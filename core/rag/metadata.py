"""Metadata classes for RAG chunks."""

from typing import List


class ChunkMetadata:
    """Metadata for a chunk with heading hierarchy and location info."""
    def __init__(self, source: str, heading_path: List[str], start_line: int, end_line: int, 
                 content_type: str = "text", chunk_index: int = 0):
        self.source = source
        self.heading_path = heading_path  # e.g., ["Chapter 1", "Section A", "Subsection"]
        self.start_line = start_line
        self.end_line = end_line
        self.content_type = content_type  # "text", "code", "frontmatter", "heading"
        self.chunk_index = chunk_index
    
    def to_dict(self):
        return {
            "source": self.source,
            "heading_path": " > ".join(self.heading_path) if self.heading_path else "Root",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_type": self.content_type,
            "chunk_index": self.chunk_index
        }
