# Quick Test Plan for Batch Diff Mode

## Status
- ✅ All code is implemented
- ✅ Debug output is added
- ✅ Unit tests pass (45/45)
- ✅ Components work in isolation
- ✅ Settings are configured correctly
- ⚠️ Need to test in running application

## Test Now

### Step 1: Run the application
```bash
cd /home/arcum42/Projects/personal/inkwell_ai
source venv/bin/activate
python main.py
```

### Step 2: Watch the console
When the application starts, you should see:
```
DEBUG: Cannot initialize diff system - no project root
```
This is normal - no project is loaded yet.

Then when the last project auto-opens, you should see:
```
DEBUG: Diff system initialized with project root: /path/to/project
```

**If you don't see this**, the diff system is not initialized!

### Step 3: Send a test message

**Option A**: Text-based (simpler to start with)
```
Disable structured responses in settings
Send message: "Update outline.md with a new section about characters"
```

Watch for:
```
DEBUG: Raw AI Response:
...
DEBUG: Batch mode enabled: True, diff_parser exists: True
DEBUG: _parse_with_batch_system called
DEBUG: Parsing response (len=XXX) with active_file=...
DEBUG: Parsed batch with X edits
DEBUG: Created batch XXX with X edits affecting X files
```

**Option B**: Structured output
```
Enable structured responses
Set schema to diff_patch
Send message: "Update outline.md and Summary.md"
```

Watch for:
```
DEBUG: Raw AI Response:
{...json...}
DEBUG: Processing diff_patch schema, batch_mode=True, diff_parser=True
DEBUG: Attempting to parse structured diff_patch with batch system
DEBUG: Parsed structured JSON into batch with X edits
DEBUG: Created batch link for X edits
```

### Step 4: Check the chat
**SUCCESS**: You see ONE link that says:
```
📝 Review X Changes to Y Files
```

**FAILURE**: You see multiple links like:
```
Review Changes for file1.md
Review Changes for file2.md
```

### Step 5: Click the link
**SUCCESS**: Opens BatchDiffDialog with:
- File list on the left
- Checkboxes to enable/disable
- Diff viewer on the right

**FAILURE**: Opens old DiffDialog with single diff view

## Debug Scenarios

### Scenario 1: diff_parser is None
**Symptoms**:
```
DEBUG: Batch mode enabled: True, diff_parser exists: False
```

**Cause**: Diff system didn't initialize
**Check**: Did you see "DEBUG: Diff system initialized"?
**Fix**: Make sure project is loaded

### Scenario 2: Batch mode disabled
**Symptoms**:
```
DEBUG: Batch mode enabled: False, diff_parser exists: True
```

**Cause**: Settings flag is False
**Fix**: Run `python check_settings.py` - should show True

### Scenario 3: Parse fails
**Symptoms**:
```
ERROR: Failed to parse...
<traceback>
```

**Cause**: Bug in parser
**Action**: Report full traceback

### Scenario 4: No edits found
**Symptoms**:
```
DEBUG: Parsed batch with 0 edits
DEBUG: No edits found in response
```

**Cause**: LLM didn't produce edit blocks
**Check**: Look at raw AI response - does it have `:::UPDATE` blocks?

## What to Report

After running the test, please share:

1. **Console output**: Copy ALL debug messages
2. **Link text**: What does the link in chat say?
3. **Link count**: One link or multiple?
4. **Dialog**: Which dialog opens when you click?
5. **Settings**: Output of `python check_settings.py`

## Expected Full Console Log (Success)

```
DEBUG: Cannot initialize diff system - no project root
DEBUG: Diff system initialized with project root: /path/to/project
...
[user sends message]
...
DEBUG: Raw AI Response:
:::UPDATE outline.md:::
# New Content
...
:::END:::

DEBUG: Batch mode enabled: True, diff_parser exists: True
DEBUG: _parse_with_batch_system called, diff_parser=True
DEBUG: Parsing response (len=123) with active_file=None
DEBUG: Parsed batch with 1 edits
DEBUG: Created batch abc-123 with 1 edits affecting 1 files
```

Then in chat you see:
```
📝 Review 1 Changes to 1 Files
```

## Files Modified (Summary)

All implementation is complete:
- `core/diff_engine.py` - Data models
- `core/path_resolver.py` - Path handling
- `core/diff_parser.py` - Parsing logic
- `gui/dialogs/batch_diff_dialog.py` - New UI
- `gui/controllers/chat_controller.py` - Integration
- `gui/controllers/project_controller.py` - Initialization hook

## Next Actions

1. Run `python main.py`
2. Open or wait for project to auto-open
3. Check console for "DEBUG: Diff system initialized"
4. Send test message
5. Watch debug output
6. Report findings

The debug output will tell us exactly what's happening!
