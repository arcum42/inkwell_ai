"""Markdown document chunking with structure awareness."""

import re
from typing import List, Tuple, Optional
from .metadata import ChunkMetadata


# Token estimation settings
TOKENS_PER_CHAR = 0.25
MIN_CHUNK_TOKENS = 50
DEFAULT_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 1500
CHUNK_OVERLAP_TOKENS = 50


class MarkdownChunker:
    """Intelligent chunker for Markdown documents."""
    
    def __init__(self, min_tokens=MIN_CHUNK_TOKENS, default_tokens=DEFAULT_CHUNK_TOKENS, 
                 max_tokens=MAX_CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS):
        self.min_tokens = min_tokens
        self.default_tokens = default_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return max(1, int(len(text) * TOKENS_PER_CHAR))
    
    def _extract_frontmatter(self, text: str) -> Tuple[Optional[str], str]:
        """Extract YAML/TOML frontmatter if present. Returns (frontmatter, remaining_text)."""
        if text.startswith('---'):
            match = re.match(r'^---\n(.*?)\n---\n(.*)', text, re.DOTALL)
            if match:
                return match.group(1), match.group(2)
        elif text.startswith('+++'):
            match = re.match(r'^\+\+\+\n(.*?)\n\+\+\+\n(.*)', text, re.DOTALL)
            if match:
                return match.group(1), match.group(2)
        return None, text
    
    def _is_heading(self, line: str) -> Tuple[bool, int, str]:
        """Check if line is a heading. Returns (is_heading, level, text)."""
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            return True, level, text
        return False, 0, ""
    
    def _is_code_fence(self, line: str) -> Tuple[bool, str]:
        """Check if line starts a code fence. Returns (is_fence, language)."""
        match = re.match(r'^```(\w*)', line)
        if match:
            return True, match.group(1) or "text"
        return False, ""
    
    def chunk(self, text: str, file_path: str) -> List[Tuple[str, ChunkMetadata]]:
        """
        Intelligently chunk Markdown text respecting structure.
        Returns list of (chunk_text, metadata) tuples.
        """
        chunks = []
        frontmatter, text = self._extract_frontmatter(text)
        
        # Add frontmatter as its own chunk if present
        if frontmatter:
            metadata = ChunkMetadata(
                source=file_path,
                heading_path=["Frontmatter"],
                start_line=1,
                end_line=frontmatter.count('\n'),
                content_type="frontmatter",
                chunk_index=0
            )
            chunks.append((frontmatter, metadata))
        
        lines = text.split('\n')
        current_chunk = []
        current_tokens = 0
        heading_stack = []  # Stack to track heading hierarchy: list of (level, text)
        chunk_start_line = 0
        chunk_index = 1 if frontmatter else 0
        in_code_block = False
        
        for line_idx, line in enumerate(lines):
            is_heading, level, heading_text = self._is_heading(line)
            is_fence, language = self._is_code_fence(line)
            
            # Track code blocks
            if is_fence:
                in_code_block = not in_code_block
            
            line_tokens = self.estimate_tokens(line)
            
            # Decide whether to flush chunk BEFORE updating heading stack
            should_flush = False
            
            if is_heading and len(current_chunk) > 0:
                # Always flush before a new heading (except the very first)
                should_flush = True
            elif current_tokens + line_tokens > self.max_tokens:
                # Flush if adding this line exceeds max tokens
                should_flush = True
            elif in_code_block and current_tokens + line_tokens > self.default_tokens * 2:
                # Code blocks can be larger, but cap at 2x default
                should_flush = current_tokens > self.default_tokens
            
            # Flush current chunk if needed
            if should_flush and len(current_chunk) > 0:
                chunk_text = '\n'.join(current_chunk).strip()
                if self.estimate_tokens(chunk_text) >= self.min_tokens:
                    # Use heading stack at time of flush
                    metadata = ChunkMetadata(
                        source=file_path,
                        heading_path=[h[1] for h in heading_stack],
                        start_line=chunk_start_line,
                        end_line=line_idx,
                        content_type="code" if in_code_block else "text",
                        chunk_index=chunk_index
                    )
                    chunks.append((chunk_text, metadata))
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_lines = []
                overlap_tokens = 0
                for prev_line in reversed(current_chunk):
                    prev_tokens = self.estimate_tokens(prev_line)
                    if overlap_tokens + prev_tokens <= self.overlap_tokens:
                        overlap_lines.insert(0, prev_line)
                        overlap_tokens += prev_tokens
                    else:
                        break
                
                current_chunk = overlap_lines
                current_tokens = overlap_tokens
                chunk_start_line = line_idx
            
            # NOW update heading stack for next iteration
            if is_heading:
                # Remove headings of equal or greater level from stack
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
            
            # Add line to current chunk
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Flush remaining chunk
        if len(current_chunk) > 0:
            chunk_text = '\n'.join(current_chunk).strip()
            # Always include the final chunk, even if smaller than min_tokens
            # This ensures small documents and tail sections aren't lost
            if chunk_text:
                metadata = ChunkMetadata(
                    source=file_path,
                    heading_path=[h[1] for h in heading_stack],
                    start_line=chunk_start_line,
                    end_line=len(lines),
                    content_type="code" if in_code_block else "text",
                    chunk_index=chunk_index
                )
                chunks.append((chunk_text, metadata))
        
        return chunks
