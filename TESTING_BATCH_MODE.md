# Testing Batch Mode

## Debug Checklist

When testing the batch diff system, check for these debug messages:

### 1. Project Initialization
When opening a project, you should see:
```
DEBUG: Diff system initialized with project root: /path/to/project
```

If you see:
```
DEBUG: Cannot initialize diff system - no project root
```
Then the diff system wasn't initialized properly.

### 2. Batch Mode Check
When processing a response with edits, you should see:
```
DEBUG: Batch mode enabled: True, diff_parser exists: True
```

If `diff_parser exists: False`, the system will fall back to legacy mode.

### 3. Response Parsing

#### For Text-Based Edits (:::UPDATE:::)
You should see:
```
DEBUG: _parse_with_batch_system called
DEBUG: Parsing response with diff parser
DEBUG: Parsed batch with X edits
```

If you see:
```
DEBUG: No edits found, falling back to legacy
```
Then the parser didn't find any UPDATE/PATCH blocks.

#### For Structured JSON (diff_patch schema)
You should see:
```
DEBUG: Processing diff_patch schema, batch_mode=True, diff_parser=True
DEBUG: Attempting to parse structured diff_patch with batch system
DEBUG: Parsed structured JSON into batch with X edits
DEBUG: Created batch link for X edits
```

If you see:
```
DEBUG: Using legacy diff_patch handling
```
Then either batch mode is disabled or diff_parser is None, or parsing failed.

### 4. Expected Output

#### Batch Mode (NEW)
- Single link in chat: `📝 Review X Changes to Y Files`
- Link starts with `batch:`
- Opens BatchDiffDialog with file list sidebar

#### Legacy Mode (OLD)
- Multiple links in chat, one per file
- Links like: `Review Changes for filename.md`
- Link starts with `edit:`
- Opens old DiffDialog

## Testing Steps

1. **Open a project**
   - File → Open Project
   - Select `test_project` folder
   - Check console for: `DEBUG: Diff system initialized`

2. **Send a test message**
   
   **Option A: Text-based edits**
   ```
   Can you update outline.md with a better title?
   ```
   
   **Option B: Structured output**
   - Enable Settings → Structured Responses
   - Enable Settings → Diff Patch Schema
   - Send same message
   
3. **Check debug output**
   - Look for "DEBUG: Batch mode enabled"
   - Look for "DEBUG: Parsed batch with X edits"
   - Count links in chat response

4. **Click the link**
   - Should open BatchDiffDialog (new)
   - Should have file list on left
   - Should have diff view on right
   - Should have checkboxes to enable/disable edits

## Common Issues

### Issue: Multiple links appear
**Cause**: Legacy mode is active
**Check**: Did you see "DEBUG: Batch mode enabled: True, diff_parser exists: True"?
**Fix**: If diff_parser exists is False, the system wasn't initialized.

### Issue: Old DiffDialog opens
**Cause**: Clicking an `edit:` link instead of `batch:` link
**Check**: What does the link text say?
**Fix**: Make sure you're seeing the batch link format.

### Issue: No diff parser initialized
**Cause**: Project not loaded before chat controller initialized
**Fix**: Already fixed - `reinit_diff_system()` is called in `open_project()`

### Issue: Structured output uses legacy path
**Cause**: Either batch mode disabled or diff_parser is None
**Check**: See "DEBUG: Processing diff_patch schema" message
**Fix**: Verify project is open and diff system initialized

## Settings Check

Batch mode is controlled by QSettings:
```python
use_batch_diff_dialog = True  # Default
```

To verify in code:
```python
from PySide6.QtCore import QSettings
settings = QSettings("InkwellAI", "InkwellAI")
print(settings.value("use_batch_diff_dialog", True, type=bool))
```

## Test Scenarios

### Scenario 1: Single File Edit
Message: "Update outline.md with a new introduction"
Expected:
- 1 batch link
- BatchDiffDialog with 1 file
- 1 diff view

### Scenario 2: Multiple File Edits
Message: "Update outline.md and Summary.md with consistent formatting"
Expected:
- 1 batch link
- BatchDiffDialog with 2 files in sidebar
- Can select each file to see its diff

### Scenario 3: Structured Output
Enable structured responses + diff_patch schema
Message: Any edit request
Expected:
- 1 batch link
- Summary from structured output
- All edits in batch

## Current Status

✅ Core infrastructure complete (diff_engine, path_resolver, diff_parser)
✅ UI complete (BatchDiffDialog)
✅ Integration complete (ChatController)
✅ Debug output added
⚠️ Testing in progress - need to verify batch mode activates correctly
