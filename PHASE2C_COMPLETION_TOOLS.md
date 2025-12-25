# Phase 2C: Tools Refactor Completion

This completes the tools refactor by wiring project settings to the tool registry.

What changed:
- Tools split into `core/tools/` modules with `util.py` and `registry.py`.
- Settings dialog now lists all known tools (even if not registered) and persists per-project:
  - Enabled tools list
  - Per-tool configurable settings
- On project open and after saving settings, the tool registry is refreshed:
  - If all available tools are enabled, all defaults are registered.
  - Otherwise, only the selected tools are registered via `register_by_names()`.
- Chat uses the enabled tools set to inject tool instructions and validate tool execution.

Usage:
- Open Preferences → Project Tools to toggle tools and adjust their settings.
- Changes apply immediately after saving the dialog.

Notes:
- Backward compatibility is preserved via `core/tools.py` wrapper.
- Tests and runtime checks continue to pass for tool registration and selective enablement.
