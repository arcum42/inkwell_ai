# Diff Handling and Diff Dialog Refactoring Plan

**Status:** Planning  
**Created:** December 27, 2025  
**Target Version:** TBD

## Executive Summary

This document outlines a comprehensive refactoring plan for Inkwell AI's diff handling system and diff dialog UI. The current implementation has several pain points including multiple diff links cluttering the chat, difficult-to-read diff views, questionable diff recognition (especially with structured outputs), and scattered patch handling code that needs consolidation.

## Current Problems

### 1. Multiple Diff Links in Chat
**Problem:** When the LLM proposes edits to multiple files, each file gets its own clickable link in the chat. This creates:
- Visual clutter with many `[Review Changes for X]` links
- No way to see all pending changes at once
- Each file requires a separate dialog interaction
- No ability to accept/reject changes in batch

**Location:** `gui/controllers/chat_controller.py` lines 600-700 (parsing logic), lines 1220-1280 (link handling)

### 2. Diff View Readability Issues
**Problem:** The diff view at the bottom of the DiffDialog uses `difflib.HtmlDiff` with a fixed `wrapcolumn=120` parameter. This causes:
- Long lines are wrapped mid-content, breaking readability
- Wrapped lines show as separate diff entries
- Hard to distinguish what's actually changed vs. what's just wrapped
- Side-by-side comparison becomes confusing with different wrapping

**Location:** `gui/dialogs/diff_dialog.py` lines 143-175 (`_build_diff_html` method)

### 3. Diff Recognition Reliability
**Problem:** Diff/patch parsing is inconsistent, especially with:
- Structured outputs (JSON schema `diff_patch`)
- Multiple patch formats (UPDATE, PATCH, unified diff, code blocks)
- Path normalization issues
- Fallback code blocks being treated as full-file updates

**Locations:**
- `gui/controllers/chat_controller.py` lines 603-700 (`_parse_and_display_response`)
- Lines 1366-1440 (`_parse_patch_blocks`, `_process_patch_blocks`)
- Lines 1440-1520 (`_process_diff_blocks`, `_process_code_blocks`)

### 4. Code Organization Issues
**Problem:** Patch handling logic is scattered throughout chat_controller.py:
- Multiple parsing functions for different formats
- Duplication between UPDATE/PATCH/diff/structured handling
- 1700+ line controller file with too many responsibilities
- Hard to test individual components
- Path normalization duplicated in multiple places

## Proposed Solutions

### Phase 1: Unified Diff/Patch Data Model

**Goal:** Create a consistent internal representation for all types of edits regardless of source format.

#### 1.1 Create Core Data Classes

Create `core/diff_engine.py`:

```python
@dataclass
class FileEdit:
    """Represents a proposed edit to a single file."""
    edit_id: str
    file_path: str  # normalized, relative to project root
    old_content: str | None  # None for new files
    new_content: str
    edit_type: Literal["update", "create", "delete"]
    metadata: dict[str, Any]  # source format, line ranges, etc.
    enabled: bool = True  # for batch operations
    
    def compute_diff_stats(self) -> tuple[int, int, int]:
        """Returns (added_lines, deleted_lines, changed_lines)."""
        pass

@dataclass
class EditBatch:
    """Collection of related file edits that should be reviewed together."""
    batch_id: str
    edits: list[FileEdit]
    summary: str | None
    timestamp: datetime
    
    def get_enabled_edits(self) -> list[FileEdit]:
        """Return only edits marked as enabled."""
        pass
    
    def total_files_affected(self) -> int:
        pass
```

#### 1.2 Create Unified Parser

Create `core/diff_parser.py`:

```python
class DiffParser:
    """Unified parser for all diff/patch formats."""
    
    def parse_response(self, response: str, active_file: str | None) -> EditBatch:
        """Main entry point - detects format and delegates to specific parsers."""
        pass
    
    def _parse_update_blocks(self, response: str) -> list[FileEdit]:
        """Parse :::UPDATE path::: ... :::END::: blocks."""
        pass
    
    def _parse_patch_blocks(self, response: str) -> list[FileEdit]:
        """Parse :::PATCH path::: with L##: directives."""
        pass
    
    def _parse_unified_diffs(self, response: str) -> list[FileEdit]:
        """Parse ```diff blocks."""
        pass
    
    def _parse_structured_json(self, payload: dict) -> list[FileEdit]:
        """Parse diff_patch schema JSON responses."""
        pass
    
    def _parse_fallback_code_blocks(self, response: str, active_file: str) -> list[FileEdit]:
        """Parse plain code blocks as full-file updates."""
        pass
```

#### 1.3 Path Normalization Service

Create `core/path_resolver.py`:

```python
class PathResolver:
    """Centralized path normalization and resolution."""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._file_index = {}  # basename -> [full_paths]
        self._refresh_index()
    
    def normalize_path(self, raw_path: str, active_file: str | None = None) -> str:
        """Normalize and resolve a path from LLM output."""
        pass
    
    def resolve_basename(self, basename: str, active_file: str | None = None) -> str | None:
        """Resolve a bare filename to full project-relative path."""
        pass
    
    def _refresh_index(self):
        """Build index of all files in project for fast basename lookup."""
        pass
```

**Benefits:**
- Single source of truth for path handling
- Testable in isolation
- Can be cached/optimized
- Clear contract for what "normalized" means

### Phase 2: Multi-Edit Diff Dialog

**Goal:** Support reviewing and applying multiple file edits in a single dialog with granular control.

#### 2.1 New Dialog Structure

Redesign `gui/dialogs/diff_dialog.py` → `gui/dialogs/batch_diff_dialog.py`:

```
BatchDiffDialog
├── Header: "Review 5 Changes to 3 Files"
├── File List (Left Sidebar, 30% width)
│   ├── [ ] file1.md (+12 / -5)
│   ├── [x] file2.py (+3 / -1)
│   ├── [x] Characters/hero.md (+8 / -2)
│   └── Buttons: [Select All] [Select None]
├── Diff View (Right 70%)
│   ├── Tabs or dropdown to switch between files
│   ├── Side-by-side with improved wrapping
│   └── Enhanced diff view (see 2.2)
└── Footer
    ├── Status: "3 of 5 edits enabled"
    ├── [Apply Selected] [Apply All] [Cancel]
```

**Key Features:**
- Checkbox list of all files in the batch
- Click file to preview its diff on the right
- Enable/disable individual files
- Apply button respects enabled state
- Show cumulative stats

#### 2.2 Improved Diff Rendering

Replace `difflib.HtmlDiff` with custom implementation:

**Option A: Custom HTML Renderer**
```python
class ImprovedDiffRenderer:
    """Custom diff renderer with smart wrapping."""
    
    def render_side_by_side(
        self, 
        old_content: str, 
        new_content: str,
        max_width: int | None = None  # None = no wrapping
    ) -> str:
        """Render side-by-side diff with horizontal scrolling instead of wrapping."""
        # Use CSS with overflow-x: auto
        # Preserve all whitespace
        # Highlight changes at character level, not just line level
        pass
    
    def render_unified(self, old_content: str, new_content: str) -> str:
        """Render unified diff view."""
        pass
```

**Option B: Use QTextEdit with Custom Highlighting**
```python
class DiffTextEdit(QTextEdit):
    """Text edit with diff syntax highlighting."""
    
    def __init__(self):
        super().__init__()
        self.setLineWrapMode(QTextEdit.NoWrap)  # Horizontal scroll
        self.setReadOnly(True)
        self.highlighter = DiffHighlighter(self.document())
    
    def set_diff(self, old_lines: list[str], new_lines: list[str]):
        """Set content and apply diff highlighting."""
        pass

class DiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for diff content."""
    
    def highlightBlock(self, text: str):
        """Apply background colors for +/- lines, highlight changed chars."""
        pass
```

**Recommendations:**
- **Short term:** Fix wrapping by setting `wrapcolumn=None` or high value, use CSS `white-space: pre; overflow-x: auto`
- **Medium term:** Implement custom renderer with character-level diff highlighting
- **Long term:** Consider integrating a dedicated diff viewer library (monaco-diff, diff2html)

#### 2.3 Chat Integration

Update `gui/controllers/chat_controller.py`:

```python
def _parse_and_display_response(self, response):
    """Parse response and create edit batches."""
    
    # Parse all edits into a single batch
    edit_batch = self.diff_parser.parse_response(response, active_file)
    
    # Store batch
    batch_id = edit_batch.batch_id
    self.pending_edit_batches[batch_id] = edit_batch
    
    # Replace all individual edit links with single batch link
    if edit_batch.edits:
        files_affected = edit_batch.total_files_affected()
        total_edits = len(edit_batch.edits)
        return response + f'\n\n<b><a href="batch:{batch_id}">Review {total_edits} Changes to {files_affected} Files</a></b>'
    
    return response

def handle_chat_link(self, url):
    """Handle link clicks in chat."""
    if url.startswith("batch:"):
        batch_id = url[6:]
        batch = self.pending_edit_batches.get(batch_id)
        if batch:
            self._show_batch_diff_dialog(batch)
```

### Phase 3: Structured Output Integration

**Goal:** Make structured `diff_patch` schema the preferred format and improve parsing reliability.

#### 3.1 Enhanced Schema

Update `core/llm/schemas.py`:

```python
register_schema(
    'diff_patch_v2',
    {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string', 'description': 'Brief summary of all changes'},
            'edits': {
                'type': 'array',
                'description': 'List of file edits to apply',
                'items': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'File path relative to project root'
                        },
                        'edit_type': {
                            'type': 'string',
                            'enum': ['update', 'create', 'delete'],
                            'description': 'Type of operation'
                        },
                        'content': {
                            'type': 'string',
                            'description': 'New content for update/create operations'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'Why this change is being made'
                        }
                    },
                    'required': ['path', 'edit_type'],
                }
            },
        },
        'required': ['summary', 'edits'],
    },
    description='Structured file edits with explanations',
    providers=['LMStudioNativeProvider'],
)
```

#### 3.2 Structured Response Handler

Update chat_controller to prefer structured output:

```python
def _handle_structured_response(self, payload: dict, schema_id: str) -> str:
    """Handle structured JSON responses."""
    
    if schema_id in ('diff_patch', 'diff_patch_v2'):
        # Convert directly to EditBatch
        edits = []
        for item in payload.get('edits', []):
            edit = FileEdit(
                edit_id=str(uuid.uuid4()),
                file_path=self.path_resolver.normalize_path(item['path']),
                old_content=None,  # will be loaded on demand
                new_content=item.get('content', ''),
                edit_type=item.get('edit_type', 'update'),
                metadata={'explanation': item.get('explanation', ''), 'schema': schema_id},
                enabled=True,
            )
            edits.append(edit)
        
        batch = EditBatch(
            batch_id=str(uuid.uuid4()),
            edits=edits,
            summary=payload.get('summary'),
            timestamp=datetime.now(),
        )
        
        self.pending_edit_batches[batch.batch_id] = batch
        
        # Return link to batch
        files_affected = batch.total_files_affected()
        total_edits = len(batch.edits)
        return f'\n\n<b><a href="batch:{batch.batch_id}">Review {total_edits} Changes to {files_affected} Files</a></b>'
    
    # ... handle other schemas
```

### Phase 4: Testing & Validation

#### 4.1 Unit Tests

Create `tests/test_diff_engine.py`:

```python
def test_parse_update_blocks():
    """Test UPDATE block parsing."""
    response = """
    Here are the changes:
    :::UPDATE file1.md:::
    New content
    :::END:::
    """
    batch = DiffParser().parse_response(response)
    assert len(batch.edits) == 1
    assert batch.edits[0].file_path == "file1.md"

def test_parse_multiple_formats():
    """Test mixed format parsing."""
    response = """
    :::UPDATE file1.md:::
    Content 1
    :::END:::
    
    :::PATCH file2.py:::
    L10: old => new
    :::END:::
    """
    batch = DiffParser().parse_response(response)
    assert len(batch.edits) == 2

def test_path_normalization():
    """Test path resolution."""
    resolver = PathResolver("/project/root")
    assert resolver.normalize_path("./file.md") == "file.md"
    assert resolver.normalize_path("`file.md`") == "file.md"
    assert resolver.normalize_path('"path/file.md"') == "path/file.md"
```

#### 4.2 Integration Tests

Create `tests/test_diff_dialog.py`:

```python
def test_multi_edit_dialog(qtbot):
    """Test multi-edit dialog with batch."""
    batch = EditBatch(
        batch_id="test",
        edits=[
            FileEdit("1", "file1.md", "old", "new", "update", {}, True),
            FileEdit("2", "file2.md", "old", "new", "update", {}, False),
        ],
        summary="Test changes",
        timestamp=datetime.now(),
    )
    
    dialog = BatchDiffDialog(batch)
    qtbot.addWidget(dialog)
    
    # Only enabled edit should be applied
    dialog.accept()
    # ... assertions
```

#### 4.3 Manual Test Cases

Document test scenarios in `tests/manual/diff_handling_tests.md`:

1. **Single file edit**: LLM proposes one UPDATE block
2. **Multiple files**: LLM proposes 3+ files in one response
3. **Mixed formats**: UPDATE + PATCH in same response
4. **Structured output**: JSON schema with multiple edits
5. **Path variations**: basename only, quoted paths, relative paths
6. **Long lines**: File with 200+ char lines should scroll, not wrap
7. **Enable/disable**: Toggle individual files in batch
8. **Apply selected**: Only checked files should be modified

### Phase 5: Migration & Backwards Compatibility

#### 5.1 Gradual Rollout

**Step 1:** Introduce new classes alongside old code
- Add `core/diff_engine.py`, `core/diff_parser.py`, `core/path_resolver.py`
- Don't break existing functionality yet

**Step 2:** Update chat controller to use new parser
- Keep old parsing code as fallback
- Log when fallback is used
- Monitor for parse failures

**Step 3:** Deploy new dialog
- Add feature flag: `settings.value("use_batch_diff_dialog", False)`
- Allow users to opt-in for testing
- Gather feedback

**Step 4:** Deprecate old code
- Remove old parsing functions
- Remove single-file dialog
- Clean up `chat_controller.py`

#### 5.2 Settings Migration

Add to settings dialog:

```python
# Diff Display Settings
diff_section = QGroupBox("Diff Display")
layout = QFormLayout()

self.batch_mode_cb = QCheckBox("Use batch diff dialog (recommended)")
self.batch_mode_cb.setChecked(settings.value("use_batch_diff_dialog", True, type=bool))

self.diff_wrap_cb = QCheckBox("Wrap long lines in diff view")
self.diff_wrap_cb.setChecked(settings.value("diff_wrap_lines", False, type=bool))

self.char_diff_cb = QCheckBox("Highlight character-level changes")
self.char_diff_cb.setChecked(settings.value("diff_char_level", True, type=bool))

layout.addRow("Batch mode:", self.batch_mode_cb)
layout.addRow("Line wrapping:", self.diff_wrap_cb)
layout.addRow("Character diffs:", self.char_diff_cb)
diff_section.setLayout(layout)
```

## Implementation Checklist

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `core/diff_engine.py` with `FileEdit` and `EditBatch` dataclasses
- [ ] Create `core/path_resolver.py` with centralized path normalization
- [ ] Create `core/diff_parser.py` with unified parsing interface
- [ ] Migrate existing path normalization logic to `PathResolver`
- [ ] Migrate UPDATE block parsing to `DiffParser`
- [ ] Migrate PATCH block parsing to `DiffParser`
- [ ] Migrate unified diff parsing to `DiffParser`
- [ ] Write unit tests for path resolver
- [ ] Write unit tests for each parser method

### Phase 2: Dialog Redesign (Week 2)
- [ ] Create `gui/dialogs/batch_diff_dialog.py` skeleton
- [ ] Implement file list widget with checkboxes
- [ ] Implement diff view switcher (tabs or dropdown)
- [ ] Fix line wrapping: set `wrapcolumn=None` or use `overflow-x: auto`
- [ ] Add horizontal scrollbar support
- [ ] Implement enable/disable file functionality
- [ ] Implement "Apply Selected" vs "Apply All" logic
- [ ] Add cumulative stats display
- [ ] Style for dark mode compatibility

### Phase 3: Integration (Week 3)
- [ ] Update `ChatController` to use `DiffParser`
- [ ] Replace individual edit links with batch links
- [ ] Add `pending_edit_batches` storage
- [ ] Update `handle_chat_link` for batch URLs
- [ ] Create `_show_batch_diff_dialog` method
- [ ] Update structured response handler for `diff_patch` schema
- [ ] Add feature flag for batch mode
- [ ] Add settings UI for diff display options

### Phase 4: Structured Output (Week 4)
- [ ] Design and register `diff_patch_v2` schema
- [ ] Update system prompts to encourage structured output
- [ ] Add schema selection to settings
- [ ] Test with LM Studio Native provider
- [ ] Document schema in provider docs
- [ ] Add schema validation/fallback handling

### Phase 5: Testing & Polish (Week 5)
- [ ] Write integration tests for dialog
- [ ] Write integration tests for chat controller
- [ ] Document manual test cases
- [ ] Perform manual testing with various LLMs
- [ ] Test with long files (1000+ lines)
- [ ] Test with long lines (200+ chars)
- [ ] Test with multiple file types (md, py, json)
- [ ] Test path edge cases (spaces, special chars)
- [ ] Performance testing with large batches (10+ files)

### Phase 6: Cleanup (Week 6)
- [ ] Remove old parsing code from `chat_controller.py`
- [ ] Remove old `DiffDialog` (single file)
- [ ] Remove duplicate path normalization code
- [ ] Refactor `chat_controller.py` to extract more logic
- [ ] Update documentation
- [ ] Update copilot instructions
- [ ] Write migration guide for users

## Success Metrics

### User Experience
- [ ] Single click to review all proposed changes
- [ ] Clear visual indication of what's being changed
- [ ] No more confusing line wrapping in diffs
- [ ] Ability to selectively apply changes
- [ ] Faster workflow for multi-file edits

### Code Quality
- [ ] Reduced complexity in `chat_controller.py` (target: <1000 lines)
- [ ] 80%+ test coverage for diff engine
- [ ] No path normalization duplication
- [ ] Clear separation of concerns
- [ ] Documented APIs

### Reliability
- [ ] 95%+ successful parse rate for UPDATE blocks
- [ ] 90%+ successful parse rate for PATCH blocks
- [ ] 100% successful parse rate for structured JSON
- [ ] Zero crashes from malformed paths
- [ ] Clear error messages for failed edits

## Risks & Mitigations

### Risk: Breaking Existing Workflows
**Impact:** High  
**Likelihood:** Medium  
**Mitigation:**
- Feature flag for gradual rollout
- Keep old code as fallback during transition
- Extensive manual testing before removing old code

### Risk: Complex UI Overwhelming Users
**Impact:** Medium  
**Likelihood:** Low  
**Mitigation:**
- Start with simple design, iterate based on feedback
- Add tooltips and help text
- Consider "simple" vs "advanced" mode

### Risk: Performance with Large Batches
**Impact:** Medium  
**Likelihood:** Medium  
**Mitigation:**
- Lazy-load file contents (don't read until user selects)
- Limit batch size (e.g., max 20 files)
- Show progress indicator for large operations

### Risk: Structured Output Adoption
**Impact:** Low  
**Likelihood:** High (requires LLM support)  
**Mitigation:**
- Keep text-based formats as fallback
- Document schema clearly for fine-tuning
- Add schema validation with helpful errors

## Future Enhancements

### Post-V1
- [ ] Side-by-side preview of rendered Markdown (for .md files)
- [ ] Syntax highlighting in diff view based on file type
- [ ] "Smart merge" for conflicting edits
- [ ] Diff history (show previous proposals for same file)
- [ ] Export diff as patch file
- [ ] Integration with git for committing applied changes
- [ ] Keyboard shortcuts for accept/reject navigation
- [ ] "Explain this change" button to ask LLM about specific diffs
- [ ] Character-level inline diff highlighting
- [ ] Minimap for large files in diff view

### Future Research
- [ ] Investigate semantic diff libraries (AST-based for code)
- [ ] Explore diff-match-patch for better algorithm
- [ ] Consider monaco-editor integration for professional diff view
- [ ] Explore streaming diffs (show as LLM generates)

## References

### Existing Code Locations
- Current dialog: `gui/dialogs/diff_dialog.py`
- Parse logic: `gui/controllers/chat_controller.py:600-1700`
- Link handling: `gui/controllers/chat_controller.py:1220-1280`
- Structured schemas: `core/llm/schemas.py:90-120`

### External Libraries
- Python difflib: https://docs.python.org/3/library/difflib.html
- diff-match-patch: https://github.com/google/diff-match-patch
- diff2html: https://github.com/rtfpessoa/diff2html
- Monaco editor: https://microsoft.github.io/monaco-editor/

### Design Inspiration
- VS Code diff viewer
- GitHub PR diff view
- GitKraken merge tool
- IntelliJ IDEA diff tool

## Open Questions

1. **Batch size limit:** Should we cap the number of files in a single batch?
2. **Merge conflicts:** How to handle when multiple edits affect the same lines?
3. **Undo/redo:** Should batch apply support undo as a unit?
4. **Preview modes:** Should we show rendered preview for Markdown/HTML?
5. **Auto-apply:** Should there be an "auto-apply trusted changes" mode?
6. **Persistence:** Should pending batches survive app restart?

## Conclusion

This refactoring will significantly improve the user experience of reviewing and applying AI-generated edits in Inkwell AI. By consolidating scattered parsing logic, introducing a unified data model, and redesigning the dialog for batch operations, we'll address all identified pain points while setting up a solid foundation for future enhancements.

The phased approach with feature flags ensures a safe migration path, and comprehensive testing will ensure reliability. The structured output integration will improve consistency with LLMs that support JSON schemas.

**Estimated Total Effort:** 6 weeks  
**Priority:** High  
**Owner:** TBD
