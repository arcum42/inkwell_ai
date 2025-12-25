# .debug Folder Exclusion Implementation

## Problem
Files from the `.debug` folder (containing debug session logs) were being indexed by RAG and included in context, wasting tokens on non-relevant debug information.

## Solution
Implemented comprehensive blacklisting of `.debug` folder at multiple levels:

### 1. Module-Level Constant
Added `EXCLUDED_DIRS` constant in [core/rag/engine.py](core/rag/engine.py):
```python
EXCLUDED_DIRS = {".inkwell_rag", ".debug", ".git", "node_modules", "__pycache__", "venv", ".venv"}
```

### 2. Runtime Filtering Helper
Added `_should_exclude_file(file_path)` method to check if any path component matches an excluded directory.

### 3. Query-Time Filtering
- **Semantic search**: Filter results to exclude `.debug` files before returning
- **Hybrid search**: Skip excluded files when building final result list
- Both search modes now request extra results (`n_results * 2`) to account for filtering

### 4. Database Cleanup
Added `clean_excluded_files()` method to:
- Scan existing database for chunks from excluded directories
- Remove those chunks from ChromaDB collection
- Remove from BM25 index and chunk tracking
- Invalidate query cache

This method is automatically called when opening a project ([gui/controllers/project_controller.py](gui/controllers/project_controller.py#L87)).

### 5. Context Collection Filtering
- **Active file**: Check exclusion before adding to system prompt
- **Open tabs**: Skip excluded files when iterating tabs

## Files Modified
- [core/rag/engine.py](core/rag/engine.py): Added EXCLUDED_DIRS constant, exclusion checking, query filtering, cleanup method
- [gui/controllers/project_controller.py](gui/controllers/project_controller.py): Call `clean_excluded_files()` on project open
- [gui/controllers/chat_controller.py](gui/controllers/chat_controller.py): Filter active file and open tabs

## Testing
1. Open project with existing `.debug` files in RAG index
2. Check terminal output for cleanup messages: `[RAG] Removing N chunks from excluded directories...`
3. Send chat message with RAG context
4. Verify no `.debug` files appear in context breakdown

## Persistence
- Exclusions persist across sessions (baked into code)
- Database cleanup runs on every project open (removes any stale entries)
- New indexing automatically skips excluded directories
