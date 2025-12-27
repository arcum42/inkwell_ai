# Batch Mode Troubleshooting Guide

## The Problem
User reports seeing multiple individual links and the old DiffDialog when testing with structured responses enabled and diff_patch schema.

## Expected Behavior

### With Batch Mode (NEW)
- **Single link**: `📝 Review X Changes to Y Files`
- **Link format**: `batch:UUID`
- **Dialog**: BatchDiffDialog with file list sidebar and diff viewer

### With Legacy Mode (OLD)
- **Multiple links**: One per file like `Review Changes for filename.md`
- **Link format**: `edit:UUID`
- **Dialog**: Old DiffDialog

## Debug Flow

### 1. Project Initialization
**When**: Project is opened via File → Open Project
**Where**: `project_controller.py:open_project()` calls `chat_controller.reinit_diff_system()`
**What to check**:
```
DEBUG: Diff system initialized with project root: /path/to/project
```
**If missing**: Diff system not initialized, will fall back to legacy mode

### 2. Response Processing

#### Path A: Structured Output (diff_patch schema)
**When**: `structured_enabled=True` and `structured_schema_id=diff_patch`
**Where**: `on_chat_response()` → `_render_structured_payload()`
**What to check**:
```
DEBUG: Processing diff_patch schema, batch_mode=True, diff_parser=True
DEBUG: Attempting to parse structured diff_patch with batch system
DEBUG: Parsed structured JSON into batch with X edits
DEBUG: Created batch link for X edits
```
**If "Using legacy diff_patch handling"**: Either batch_mode=False OR diff_parser=None

#### Path B: Text-Based Edits (:::UPDATE:::)
**When**: Text response with `:::UPDATE path::: content :::END:::` blocks
**Where**: `on_chat_response()` → `_parse_and_display_response()` → `_parse_with_batch_system()`
**What to check**:
```
DEBUG: Batch mode enabled: True, diff_parser exists: True
DEBUG: _parse_with_batch_system called
DEBUG: Parsing response
DEBUG: Parsed batch with X edits
```
**If falls to legacy**: batch_mode=False OR diff_parser=None

### 3. Link Click
**When**: User clicks a link in the chat
**Where**: `handle_chat_link()`
**What to check**: Link URL starts with `batch:` or `edit:`

## Common Issues

### Issue 1: diff_parser is None
**Symptoms**:
- "diff_parser exists: False" in debug output
- Falls back to legacy mode

**Causes**:
- Diff system not initialized
- Project not loaded when chat controller created
- `reinit_diff_system()` not called

**Fix**: ✅ Already fixed by adding `reinit_diff_system()` call in `open_project()`

**Verify**: Check for "DEBUG: Diff system initialized" message after opening project

### Issue 2: Batch mode disabled
**Symptoms**:
- "Batch mode enabled: False" in debug output
- Falls back to legacy mode

**Causes**:
- QSettings value `use_batch_diff_dialog` is False

**Fix**: Check settings:
```python
from PySide6.QtCore import QSettings
settings = QSettings("InkwellAI", "InkwellAI")
print(settings.value("use_batch_diff_dialog", True, type=bool))
```

**Default**: True (batch mode enabled by default)

### Issue 3: Parsing fails
**Symptoms**:
- "ERROR: Failed to parse structured diff_patch" or similar
- Traceback in console

**Causes**:
- Malformed JSON from LLM
- Path resolution issues
- File doesn't exist

**Fix**: Check traceback for specific error

### Issue 4: No edits found
**Symptoms**:
- "DEBUG: No edits found" or "batch with 0 edits"
- No links appear

**Causes**:
- LLM didn't produce edits in expected format
- Parser didn't recognize format

**Fix**: Check raw AI response for edit blocks

## Testing Procedure

### Step 1: Open Project
```
1. Launch application
2. File → Open Project
3. Select test_project folder
4. Look for: "DEBUG: Diff system initialized with project root: /path/to/test_project"
```

### Step 2: Test Text-Based Edits
```
1. Send message: "Update outline.md with a better title"
2. Look for:
   - "DEBUG: Batch mode enabled: True, diff_parser exists: True"
   - "DEBUG: _parse_with_batch_system called"
   - "DEBUG: Parsed batch with X edits"
3. Check chat for single batch link
4. Click link, should open BatchDiffDialog
```

### Step 3: Test Structured Output
```
1. Enable Settings → Structured Responses
2. Set Settings → Structured Schema → diff_patch
3. Send message: "Update outline.md and Summary.md"
4. Look for:
   - "DEBUG: Processing diff_patch schema, batch_mode=True, diff_parser=True"
   - "DEBUG: Parsed structured JSON into batch with X edits"
   - "DEBUG: Created batch link for X edits"
5. Check chat for single batch link
6. Click link, should open BatchDiffDialog
```

## Expected Console Output (Success Case)

### For Structured Output:
```
DEBUG: Raw AI Response:
{structured JSON...}
DEBUG: Processing diff_patch schema, batch_mode=True, diff_parser=True
DEBUG: Attempting to parse structured diff_patch with batch system
DEBUG: Parsed structured JSON into batch with 2 edits
DEBUG: Created batch link for 2 edits
```

### For Text-Based Edits:
```
DEBUG: Raw AI Response:
Here are the changes:

:::UPDATE outline.md:::
...
:::END:::

DEBUG: Batch mode enabled: True, diff_parser exists: True
DEBUG: _parse_with_batch_system called
DEBUG: Parsing response (len=XXX) with active_file=...
DEBUG: Parsed batch with 1 edits
DEBUG: Created batch XXX with 1 edits affecting 1 files
```

## Failure Console Output (Legacy Mode)

### For Structured Output:
```
DEBUG: Processing diff_patch schema, batch_mode=False, diff_parser=False
DEBUG: Using legacy diff_patch handling
```
Result: Multiple `edit:` links, one per file

### For Text-Based Edits:
```
DEBUG: Batch mode enabled: False, diff_parser exists: False
```
Then falls back to `_parse_with_legacy_system()`, creates multiple `edit:` links

## Diagnostic Checklist

- [ ] Application launches without errors
- [ ] Project opens successfully
- [ ] Console shows "DEBUG: Diff system initialized"
- [ ] Console shows "batch_mode=True" when processing edits
- [ ] Console shows "diff_parser exists: True" when processing edits
- [ ] Chat shows **single** link with emoji 📝
- [ ] Link URL starts with `batch:` not `edit:`
- [ ] Clicking link opens BatchDiffDialog (not DiffDialog)
- [ ] Dialog has file list on left side
- [ ] Dialog has checkboxes to enable/disable edits
- [ ] Applying edits updates files correctly

## Next Steps

1. **Run application** with project loaded
2. **Send test message** requesting edits
3. **Check console output** for debug messages
4. **Report findings**: Which debug messages appear? Which don't?
5. **Test both paths**: Text-based (:::UPDATE:::) and structured (diff_patch schema)

## Files to Check

- `gui/controllers/chat_controller.py` - Main logic
- `gui/controllers/project_controller.py` - Project initialization
- `core/diff_parser.py` - Parsing logic
- `gui/dialogs/batch_diff_dialog.py` - New dialog UI
- `gui/dialogs/diff_dialog.py` - Old dialog (should not be used)
