# Inkwell AI - Refactoring and Cleanup Plan

**Generated:** December 24, 2025  
**Total Lines of Code:** 8,472 (excluding test files and venv)

## Executive Summary

This document outlines a strategic plan for cleaning up and refactoring Inkwell AI's codebase. The project has grown organically and several files have exceeded reasonable size limits. The primary goal is to separate UI and business logic, break down monolithic files, and eliminate code duplication.

---

## 1. Line Count Analysis

### Top 10 Largest Files

| Rank | File | Lines | Type | Status |
|------|------|-------|------|--------|
| 1 | `gui/main_window.py` | 2,613 | **[CRITICAL]** | UI - Monolithic |
| 2 | `core/rag_engine.py` | 921 | Core | Mixed concerns |
| 3 | `gui/editor.py` | 605 | UI | Mixed concerns |
| 4 | `gui/chat.py` | 537 | UI | Single responsibility |
| 5 | `gui/image_gen.py` | 361 | UI | Moderate size |
| 6 | `gui/sidebar.py` | 312 | UI | Moderate size |
| 7 | `core/tools.py` | 303 | Core | Single file with many tools |
| 8 | `core/llm_provider.py` | 292 | Core | Multiple providers |
| 9 | `gui/dialogs/settings_dialog.py` | 272 | UI | Single responsibility |
| 10 | `gui/workers.py` | 262 | UI/Core | Threading abstraction |

### Assessment

- **Immediate Action:** `gui/main_window.py` (2,613 lines) is significantly oversized
- **High Priority:** `core/rag_engine.py` (921 lines) has mixed responsibilities
- **Medium Priority:** `gui/editor.py` (605 lines) combines multiple editor types
- **Low Priority:** Others are reasonably sized but could benefit from organization

---

## 2. Detailed File Analysis

### 🔴 CRITICAL: `gui/main_window.py` (2,613 lines)

**Current Issues:**
- Combines application orchestration, menu setup, signal handling, and data management
- Contains embedded utility functions (`estimate_tokens`, etc.)
- Handles project management, chat coordination, image generation, and file operations
- Multiple responsibilities violating Single Responsibility Principle

**Identified Sections:**
1. **Application setup** (~100 lines) - Window initialization, settings
2. **Menu bar creation** (~200 lines) - File, Edit, View, Tools, Help menus
3. **Signal connections** (~300 lines) - Connecting all widgets
4. **Project management** (~400 lines) - Open, close, save operations
5. **Chat interface** (~400 lines) - Message handling, context management
6. **Editor management** (~300 lines) - Tab management, file operations
7. **Image generation** (~250 lines) - Image generation workflow
8. **RAG/indexing** (~200 lines) - Search indexing, retrieval
9. **Utility functions** (~100+ lines) - Token estimation, data processing
10. **Event handlers** (~350+ lines) - Various slot methods

**Recommended Refactoring:**

```
gui/
├── main_window.py              (~300 lines) - Main window frame only
├── menubar/
│   ├── menu_manager.py         (~200 lines) - All menu creation
│   ├── file_menu.py            (~100 lines) - File menu actions
│   ├── edit_menu.py            (~80 lines)  - Edit menu actions
│   └── tools_menu.py           (~80 lines)  - Tools menu actions
├── orchestration/
│   ├── project_orchestrator.py (~300 lines) - Project operations
│   ├── chat_orchestrator.py    (~300 lines) - Chat flow coordination
│   └── editor_orchestrator.py  (~200 lines) - Editor/tab management
├── utils/
│   └── token_utils.py          (~50 lines)  - Token estimation
└── dialogs/
    └── [existing dialogs]
```

**Backup Strategy:**
```bash
# Before refactoring main_window.py
cp gui/main_window.py gui/main_window.py.backup_pre_refactor_v1
```

---

### 🟠 HIGH PRIORITY: `core/rag_engine.py` (921 lines)

**Current Issues:**
- Combines chunking logic, search functionality, caching, and embedding
- Multiple classes (ChunkMetadata, QueryCache, RAGEngine) in single file
- Chunking strategy is intertwined with search logic
- No separation between different chunking algorithms

**Identified Components:**
1. **Constants** (~30 lines) - Token settings, cache settings
2. **ChunkMetadata class** (~25 lines) - Metadata storage
3. **QueryCache class** (~120 lines) - Result caching
4. **Chunking logic** (~300 lines) - Markdown/text chunking
5. **RAGEngine class** (~400+ lines) - Main orchestrator
6. **Search algorithms** (~100 lines) - Keyword and semantic search

**Recommended Refactoring:**

```
core/
├── rag/
│   ├── __init__.py
│   ├── engine.py               (~300 lines) - RAGEngine main class
│   ├── chunking/
│   │   ├── __init__.py
│   │   ├── base.py             (~50 lines)  - Chunking interface
│   │   ├── markdown_chunker.py (~150 lines) - Markdown-specific
│   │   └── code_chunker.py     (~100 lines) - Code-specific
│   ├── search/
│   │   ├── __init__.py
│   │   ├── keyword_search.py   (~60 lines)  - Keyword search
│   │   ├── semantic_search.py  (~60 lines)  - Semantic search
│   │   └── hybrid_search.py    (~80 lines)  - Combined search
│   ├── cache.py                (~120 lines) - QueryCache
│   └── metadata.py             (~30 lines)  - ChunkMetadata
└── rag_engine.py               (import wrapper - backward compat)
```

**Benefits:**
- Easy to add new chunking strategies
- Search algorithms can be tested independently
- Caching can be swapped out
- Core RAG logic stays clean and testable

**Backup Strategy:**
```bash
cp core/rag_engine.py core/rag_engine.py.backup_pre_refactor_v1
```

---

### 🟠 HIGH PRIORITY: `gui/editor.py` (605 lines)

**Current Issues:**
- Combines three distinct editor types in single file
- Heavy use of inheritance and composition
- Markdown preview and code display mixed with code editing
- Large number of formatting methods with boilerplate

**Identified Classes:**
1. **LinkDialog** (~30 lines) - Link insertion dialog
2. **CodeEditor** (~200 lines) - Code editing with syntax formatting
3. **DocumentWidget** (~150 lines) - Markdown document view
4. **ImageViewerWidget** (~80 lines) - Image display
5. **EditorWidget** (~150 lines) - Tab management and coordination

**Recommended Refactoring:**

```
gui/
├── editors/
│   ├── __init__.py
│   ├── code_editor.py          (~200 lines) - Code editor with formatting
│   ├── document_viewer.py      (~150 lines) - Markdown viewer
│   ├── image_viewer.py         (~80 lines)  - Image display
│   └── dialogs.py              (~30 lines)  - Link/insert dialogs
└── editor.py                   (~100 lines) - EditorWidget (tab manager only)
```

**Bonus:**
- Extract formatting logic into separate formatters module
- Create TextFormattingHelper class for reusable formatting

**Backup Strategy:**
```bash
cp gui/editor.py gui/editor.py.backup_pre_refactor_v1
```

---

### 🟡 MEDIUM PRIORITY: `core/tools.py` (303 lines)

**Current Issues:**
- Single file containing multiple tool implementations
- Each tool is a separate class but no clear organization
- Tool discovery/registry not visible from file structure

**Current Structure:**
- Web search tool
- Wikipedia tool
- File operations tools
- Other utility tools

**Recommended Refactoring:**

```
core/tools/
├── __init__.py
├── base.py                     (from tool_base.py reference)
├── web_search.py               (~80 lines)
├── wikipedia_tool.py           (~60 lines)
├── file_tools.py               (~100 lines)
└── registry.py                 (~50 lines)  - Tool discovery
```

**Backup Strategy:**
```bash
cp core/tools.py core/tools.py.backup_pre_refactor_v1
```

---

### 🟡 MEDIUM PRIORITY: `core/llm_provider.py` (292 lines)

**Current Issues:**
- Multiple provider implementations in single file
- Base provider class mixed with implementations
- No clear interface/abstraction layer

**Identified Sections:**
1. **Base provider** (~80 lines)
2. **OllamaProvider** (~100 lines)
3. **LMStudioProvider** (~100 lines)
4. **Utility functions** (~12 lines)

**Recommended Refactoring:**

```
core/llm/
├── __init__.py
├── base.py                     (~80 lines)  - Provider interface
├── ollama.py                   (~100 lines) - Ollama implementation
├── lm_studio.py                (~100 lines) - LM Studio implementation
└── provider_factory.py         (~30 lines)  - Provider selection
```

**Backup Strategy:**
```bash
cp core/llm_provider.py core/llm_provider.py.backup_pre_refactor_v1
```

---

### 🟡 MEDIUM PRIORITY: `gui/workers.py` (262 lines)

**Current Issues:**
- All worker threads in single file
- Each worker handles different domain (chat, indexing, image gen, tools)
- Could benefit from domain-specific worker grouping

**Identified Workers:**
1. **ChatWorker** (~80 lines) - LLM chat responses
2. **IndexWorker** (~70 lines) - RAG indexing
3. **ImageGenWorker** (~50 lines) - Image generation
4. **BatchWorker** (~30 lines) - Batch operations
5. **ToolWorker** (~30 lines) - Tool execution

**Recommended Refactoring:**

```
gui/workers/
├── __init__.py
├── base.py                     (~40 lines)  - Base worker class
├── chat_worker.py              (~80 lines)  - Chat operations
├── index_worker.py             (~70 lines)  - Indexing operations
├── image_gen_worker.py         (~50 lines)  - Image generation
└── tool_worker.py              (~30 lines)  - Tool execution
```

**Minor benefit but improves navigation and testing.**

---

## 3. Code Duplication Analysis

### Identified Duplication Patterns

1. **Token estimation logic**
   - Found in: `main_window.py::estimate_tokens()`, possibly in `rag_engine.py`
   - **Action:** Consolidate to `core/utils/tokens.py`

2. **File I/O operations**
   - Found in: `main_window.py`, `project.py`, potentially others
   - **Action:** Review for duplication, potentially use `ProjectManager` consistently

3. **Dialog patterns**
   - Found in: Multiple dialogs with similar setup
   - **Action:** Create base dialog class if patterns emerge

4. **Worker thread patterns**
   - Found in: `workers.py` - multiple workers with similar signal/slot patterns
   - **Action:** Consolidate base worker class patterns

5. **Markdown parsing/processing**
   - Found in: `editor.py`, `rag_engine.py` (chunking)
   - **Action:** Consolidate to shared markdown utility module

---

## 4. Dead Code Candidates

**Areas to audit for dead code:**

1. **`gui/main_window.py`**
   - Check for menu items without handlers
   - Look for signal connections to deleted methods
   - Search for unused local variables and helper functions

2. **`core/rag_engine.py`**
   - Check for deprecated chunking strategies
   - Look for unused cache invalidation logic
   - Review hybrid search weight calculations for unused branches

3. **`gui/dialogs/settings_dialog.py`**
   - Check for controls that aren't wired to settings
   - Look for settings keys that aren't used

4. **Test files**
   - `test_*.py` files that have been superseded by others
   - Debug files like `debug_*.py` should be archived or removed

---

## 5. Code Quality Issues to Address

### High Priority

1. **Type hints**
   - Many functions lack type annotations
   - Especially in: `main_window.py`, `rag_engine.py`, `editor.py`

2. **Docstring coverage**
   - Many large methods lack documentation
   - Especially orchestration methods in main_window.py

3. **Magic numbers**
   - Window sizes, layout margins, etc.
   - **Action:** Move to `core/config.py` or `gui/constants.py`

4. **Error handling**
   - Some error paths not fully handled
   - Dialog error messages could be more user-friendly

### Medium Priority

1. **Constants organization**
   - Scattered across files
   - **Action:** Consolidate to `constants.py` files in each module

2. **Import organization**
   - Some circular imports possible
   - Large import lists in main_window.py

3. **Method length**
   - Some methods in main_window.py exceed 50 lines
   - **Action:** Break down into smaller units

---

## 6. Separation of UI and Backend

### Current State

**UI-Only Files (✅ Good):**
- `gui/editor.py`
- `gui/chat.py`
- `gui/image_gen.py`
- `gui/sidebar.py`
- `gui/welcome.py`
- `gui/dialogs/*`

**Backend-Only Files (✅ Good):**
- `core/project.py`
- `core/rag_engine.py`
- `core/llm_provider.py`
- `core/tools.py`
- `core/workflow_manager.py`

**Mixed Concerns (⚠️ Problematic):**
- `gui/main_window.py` - Contains orchestration logic that could be backend
- `gui/workers.py` - Threading abstraction (acceptable but could be refactored)

### Recommended Separation

Extract orchestration layer from `main_window.py`:

```
core/orchestration/
├── __init__.py
├── base_orchestrator.py        (~50 lines)  - Base class
├── project_orchestrator.py     (~200 lines) - Project operations
├── chat_orchestrator.py        (~250 lines) - Chat flow (no UI calls)
└── editor_orchestrator.py      (~150 lines) - Editor operations
```

**Principle:** These orchestrators handle business logic and emit signals; `main_window.py` connects signals to UI updates only.

---

## 7. Refactoring Roadmap

### Phase 1: Preparation (Week 1) ✅ COMPLETED
- [x] Create backup copies of all large files
- [x] Document current architecture
- [x] Set up branch for refactoring work
- [x] Identify and extract all test files to separate location
- [x] Documentation: [PHASE1_COMPLETION.md](PHASE1_COMPLETION.md)

### Phase 2: Core Components (Weeks 2-3)
- [x] Refactor `core/rag_engine.py` into `core/rag/` module ✅ COMPLETED
  - [x] Backup created: `core/rag_engine.py.backup_pre_refactor_v1`
  - [x] Extract chunking module → `core/rag/chunking.py`
  - [x] Extract search module → `core/rag/search.py`
  - [x] Extract cache module → `core/rag/cache.py`
  - [x] Extract metadata module → `core/rag/metadata.py`
  - [x] Extract context module → `core/rag/context.py`
  - [x] Extract engine module → `core/rag/engine.py`
  - [x] Maintain backward compatibility with wrapper
  - [x] Create completion doc: `PHASE2A_COMPLETION_RAG.md`
- [x] Refactor `core/llm_provider.py` into `core/llm/` module ✅ COMPLETED
  - [x] Backup created: `core/llm_provider.py.backup_pre_refactor_v1`
  - [x] Extract base class → `core/llm/base.py`
  - [x] Extract Ollama provider → `core/llm/ollama.py`
  - [x] Extract LM Studio provider → `core/llm/lm_studio.py`
  - [x] Create public API → `core/llm/__init__.py`
  - [x] Maintain backward compatibility with wrapper
  - [x] Create completion doc: `PHASE2B_COMPLETION_LLM.md`
  - [x] Import tests pass (both old and new paths)
- [ ] Refactor `core/tools.py` into `core/tools/` module (IN PROGRESS)
  - [ ] Backup first: `cp core/tools.py core/tools.py.backup_pre_refactor_v1`
  - [ ] Organize by tool type
  - [ ] Create registry

### Phase 3: UI Components (Weeks 4-5)
- [ ] Refactor `gui/editor.py` into `gui/editors/` module
  - Backup first: `cp gui/editor.py gui/editor.py.backup_v1`
  - Separate editor types
  - Extract formatting logic
  - Maintain backward compatibility
- [ ] Refactor `gui/workers.py` into `gui/workers/` module
  - Backup first
  - Organize workers by domain
  - Consolidate base worker patterns

### Phase 4: Main Window (Weeks 6-8)
- [ ] Refactor `gui/main_window.py` (LARGEST TASK)
  - Backup first: `cp gui/main_window.py gui/main_window.py.backup_v1`
  - Extract menu management
  - Extract orchestration logic to core
  - Break down into controllers
  - Reduce to ~300 lines focused on UI layout and signal routing
- [ ] Create `core/orchestration/` module
  - Extract project management logic
  - Extract chat orchestration logic
  - Extract editor orchestration logic

### Phase 5: Polish (Week 9)
- [ ] Remove backup files once confident
- [ ] Add missing type hints
- [ ] Add docstrings to public APIs
- [ ] Run tests and validation
- [ ] Update import statements across codebase

---

## 8. Backup Strategy

### Backup Naming Convention

```
original_file.py.backup_pre_refactor_v1
original_file.py.backup_pre_refactor_v2  (if multiple iterations)
```

### When to Remove Backups

- Keep for at least 2 weeks after refactoring
- Remove only after:
  - All tests pass
  - Code review is complete
  - Application runs successfully in production
  - Team agrees changes are final

### Backup Locations

All backups should remain in the same directory as the original file for easy reference.

---

## 9. Testing Strategy

### Before Refactoring Each File

1. Document current behavior with screenshots (for UI)
2. Run existing tests (if applicable)
3. Note any edge cases or special behavior

### After Refactoring Each File

1. Run unit tests for the component
2. Test integration with dependent components
3. Manual testing of UI features (if UI file)
4. Check imports don't create circular dependencies

### Critical Paths to Test

1. **Project operations:** Open, save, close, rename files
2. **Chat flow:** Send message, receive response, display in UI
3. **RAG operations:** Index project, search, retrieve context
4. **Image generation:** Generate image, display result
5. **Editor operations:** Edit files, format text, save changes

---

## 10. Success Criteria

✅ Refactoring is successful when:

1. **Size reduction**
   - `gui/main_window.py` ≤ 500 lines
   - No single file > 800 lines (except RAGEngine migration)

2. **Code organization**
   - Clear separation of UI and business logic
   - Each file/module has single responsibility
   - No circular imports

3. **Backward compatibility**
   - All existing imports still work
   - API surface unchanged for external consumers
   - Tests pass without modification

4. **Documentation**
   - All public methods have type hints
   - All public classes have docstrings
   - Architecture document updated

5. **Code quality**
   - Duplicated code eliminated
   - Dead code removed
   - Magic numbers extracted to constants

---

## 11. Quick Reference: Backup Commands

```bash
# Before starting each refactoring task:

# Main window
cp gui/main_window.py gui/main_window.py.backup_pre_refactor_v1

# RAG engine
cp core/rag_engine.py core/rag_engine.py.backup_pre_refactor_v1

# Editor
cp gui/editor.py gui/editor.py.backup_pre_refactor_v1

# Tools
cp core/tools.py core/tools.py.backup_pre_refactor_v1

# LLM provider
cp core/llm_provider.py core/llm_provider.py.backup_pre_refactor_v1

# Workers
cp gui/workers.py gui/workers.py.backup_pre_refactor_v1

# Verify backups exist
ls -lh *.backup_pre_refactor_v1
```

---

## 12. Notes and Considerations

### Important Points

1. **Maintain backward compatibility:** Existing code importing from these files should continue to work
2. **Gradual refactoring:** Don't refactor everything at once; do it incrementally
3. **Test frequently:** Run tests after each significant change
4. **Document as you go:** Update docs alongside code changes
5. **Keep backups during transition:** Don't delete old files immediately

### Potential Challenges

1. **Circular imports:** Be careful when breaking apart interdependent modules
2. **Large test impact:** Changes to main_window may require test updates
3. **Performance:** Ensure refactoring doesn't introduce import overhead
4. **Complexity:** New module structure might be harder for new contributors to navigate

### Future Considerations

- Consider adding `__all__` exports to module `__init__.py` files
- Consider using abstract base classes for extensibility
- Consider plugin architecture for tools if collection grows
- Consider dependency injection for better testability

---

## Summary Table

| File | Size | Priority | Effort | Impact |
|------|------|----------|--------|--------|
| `gui/main_window.py` | 2,613 | 🔴 CRITICAL | High | Very High |
| `core/rag_engine.py` | 921 | 🟠 HIGH | Medium | High |
| `gui/editor.py` | 605 | 🟠 HIGH | Medium | High |
| `core/tools.py` | 303 | 🟡 MEDIUM | Low | Medium |
| `core/llm_provider.py` | 292 | 🟡 MEDIUM | Low | Medium |
| `gui/workers.py` | 262 | 🟡 MEDIUM | Low | Low |

**Estimated Total Effort:** 4-6 weeks for complete refactoring with testing

**Expected Outcome:** Cleaner codebase with 20-30% more files but 50% better organization and maintainability.

