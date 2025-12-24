# Inkwell AI - Coding Standards

## Project Overview
Inkwell AI is a writer-focused workspace application built with Python and PySide6/Qt. It integrates LLMs, RAG, and ComfyUI for creative writing projects with Markdown and images.

**Architecture:**
- `core/`: Business logic (ProjectManager, RAGEngine, LLMProvider, WorkflowManager, tools)
- `gui/`: UI components (MainWindow, Editor, Chat, Sidebar, ImageGen, dialogs)
- `workflows/`: ComfyUI JSON workflow templates

**Environment:**
- This application runs in a Python virtual environment located at `venv/` in the project root
- **ALWAYS activate the venv before running or testing:** `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- **NEVER attempt to run the application without activating the venv first**
- All dependencies are installed in the venv via `pip install -r requirements.txt`
- The venv ensures isolated dependency management and prevents conflicts with system Python packages

## Python Coding Standards

**Style:**
- Follow PEP 8 conventions
- Line length: prefer 120 characters max (flexible for readability)
- Use 4 spaces for indentation
- Imports: standard library → third-party → local (alphabetical within groups)

**Naming:**
- Classes: `PascalCase` (e.g., `ProjectManager`, `ChatWidget`)
- Functions/methods: `snake_case` (e.g., `handle_chat_message`, `open_project`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CHUNK_SIZE`)
- Private methods: prefix with `_` (e.g., `_perform_move`)
- Signals: descriptive names (e.g., `message_sent`, `file_renamed`)

**Type Hints:**
- Use type hints for function signatures where clarity helps
- Optional for obvious cases (e.g., event handlers returning None)
- Example: `def save_file(self, path: str, content: str) -> bool:`

**Documentation:**
- Docstrings for classes and non-trivial public methods
- Use triple-quoted strings: `"""Brief description."""`
- Include parameters and return values for complex methods
- Comment complex logic inline when intent isn't obvious

**Error Handling:**
- Use try/except for I/O, network, and user-facing operations
- Show user-friendly errors via QMessageBox (Warning/Critical)
- Log detailed errors to console with context
- Never silence exceptions without logging

## Qt/PySide6 Patterns

**Signals & Slots:**
- Define signals at class level: `message_sent = Signal(str)`
- Connect in `__init__` or setup methods
- Use lambdas for simple slot adapters: `lambda: self.editor.undo()`
- Disconnect when cleaning up long-lived connections

**Widgets:**
- Inherit from appropriate Qt base classes (QWidget, QDialog, QMainWindow)
- Initialize UI in `__init__`
- Use layouts (QVBoxLayout, QHBoxLayout, QFormLayout) not absolute positioning
- Set object properties for debugging: `widget.setProperty("file_path", path)`

**Threading:**
- Use QThread for long-running operations (LLM calls, indexing, image generation)
- Emit signals for progress and completion
- Never manipulate UI from worker threads
- Example: `ChatWorker`, `IndexWorker`, `ImageGenWorker`

**Settings:**
- Use QSettings for persistence: `QSettings("InkwellAI", "InkwellAI")`
- Store paths as relative when inside project
- Provide sensible defaults: `self.settings.value("key", "default")`

## Code Organization

**File Structure:**
- One class per file (exceptions: small helper classes)
- Group related UI components in gui/dialogs/
- Keep business logic separate from UI

**Dependencies:**
- Core modules should not import from gui/
- GUI can import from core/
- Minimize circular dependencies

**State Management:**
- MainWindow owns application-level state (project, settings, RAG, chat history)
- Child widgets emit signals for state changes
- Use properties for encapsulation where appropriate

## Common Patterns

**File Operations:**
- Use `ProjectManager` for file I/O within projects
- Validate paths before operations
- Emit signals after successful rename/move/delete
- Update editor tabs when files change

**LLM Integration:**
- Use `OllamaProvider` or `LMStudioProvider` via `get_llm_provider()`
- Check for vision capability: `provider.is_vision_model(model)`
- Pass system prompts and context explicitly
- Handle streaming/async responses via workers

**Edit Proposals:**
- Parse `:::UPDATE path:::...:::END:::` blocks from LLM responses
- Store in `pending_edits` dict with unique IDs
- Show DiffDialog for user review before applying
- Use `replace_content_undoable()` for text edits

**RAG Queries:**
- Check if `self.rag_engine` exists before querying
- Log queries and retrieved chunks for debugging
- Inject context into system prompts, not user messages
- Handle empty results gracefully

## Best Practices

**Do:**
- Keep UI responsive (use workers for slow operations)
- Provide visual feedback (progress bars, status messages)
- Allow cancellation of long operations
- Validate user input before processing
- Show confirmation dialogs for destructive actions
- Keep file paths relative to project root when storing
- Update UI state after async operations complete

**Don't:**
- Block the main thread with heavy computation
- Manipulate files outside the project without validation
- Store absolute paths in settings (use relative when possible)
- Assume file operations succeed (always handle exceptions)
- Create memory leaks (disconnect signals, clean up threads)
- Hardcode paths or URLs (use settings)

## Implementation Workflow

When implementing features:
1. Start with core logic (data model, business rules)
2. Add worker threads for async operations
3. Build UI components with signals for events
4. Wire signals in MainWindow or parent widgets
5. Test edge cases (empty inputs, missing files, cancellation)
6. Provide user feedback (dialogs, status bar, progress)
