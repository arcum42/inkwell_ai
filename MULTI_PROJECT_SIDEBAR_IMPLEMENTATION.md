# Multi-Project Sidebar Implementation - Summary

## Overview
Implemented support for multiple collapsible project sections in the sidebar, allowing simultaneous display of a main project and a reusable assets folder. This enables better organization and workflow for writers managing shared resources across projects.

## Changes Made

### 1. **Sidebar Architecture Refactor** (`gui/sidebar.py`)
   - **New `ProjectSection` class**: Encapsulates a single project's file tree with all operations
     - Contains its own `QFileSystemModel` and `ProjectTreeView`
     - Handles file operations (create, rename, move, delete)
     - Emits signals for file changes that propagate up to parent Sidebar
   
   - **Refactored `Sidebar` class**: Now acts as a container for multiple `ProjectSection` widgets
     - Maintains a dictionary of project sections: `project_sections = {name -> ProjectSection}`
     - Methods to `add_project()`, `remove_project()`, and `get_project_section()`
     - Backward compatibility: Provides `tree` and `model` properties that delegate to "Project" section
     - Relays all file signals from child sections to parent window

### 2. **Settings Integration** (`gui/dialogs/settings_dialog.py`)
   - Added "Assets Folder" setting in General preferences tab
   - Includes folder browser button for easy selection
   - Saves relative path when possible (cleaner config, portable projects)
   - Defaults to `"assets"` folder
   - Added new method `browse_assets_folder()` to handle folder selection

### 3. **Project Controller Updates** (`gui/controllers/project_controller.py`)
   - Modified `open_project()` to:
     - Add main project to sidebar using `sidebar.add_project("Project", path)`
     - Automatically open assets folder via `_open_assets_folder()` helper
   - Added `_open_assets_folder()` method that:
     - Reads assets path from settings
     - Resolves relative paths (project-relative or app-relative)
     - Adds "Assets" section to sidebar if folder exists
   - Updated RAG engine indexing to specify project name: `set_rag_engine(engine, "Project")`
   - Modified `_shutdown_project_session()` to remove all projects from sidebar

### 4. **MainWindow Adjustments** (`gui/main_window.py`)
   - Updated sidebar signal connection: `file_double_clicked` now passes full file path instead of index
   - Simplified `on_file_double_clicked()` to work directly with file paths
   - Removed duplicate `_shutdown_project_session()` method (now uses ProjectController's version)
   - Added backward compatibility properties for existing code

### 5. **Backward Compatibility**
   - Sidebar still provides `tree` and `model` properties for code that expects them
   - Added delegation methods: `create_new_file()`, `create_new_folder()`, `rename_item()`, `move_item()`
   - All existing menu actions and keyboard shortcuts continue to work

## File Structure Changes

```
Left Pane (Sidebar):
├── Project (collapsible section)
│   ├── Chapters/
│   ├── Characters/
│   ├── README.md
│   └── ...
└── Assets (collapsible section)  [optional, if configured]
    ├── Templates/
    ├── Plots/
    └── ...
```

## User Workflow

1. **Open a project** → Main "Project" section appears in sidebar
2. **Configure assets folder** → Go to Preferences → General → Assets Folder → Browse
3. **Open project again** → Both "Project" and "Assets" sections appear in sidebar
4. **Browse files** → Can navigate project files and shared assets separately
5. **Copy files** → Can drag files from Assets to Project or vice versa

## Configuration

The assets folder setting is stored in `QSettings("InkwellAI", "InkwellAI")` under the key `"assets_folder"`.

Default: `"assets"` (relative to app directory)

Example configurations:
- `"assets"` → `{app_dir}/assets/`
- `"~/shared_templates"` → User's home directory
- `"/opt/inkwell_assets"` → Absolute path

## Testing

Comprehensive tests verify:
- ✓ Multiple project sections can be added and removed
- ✓ Backward compatibility properties work correctly
- ✓ Settings save and load properly
- ✓ Integration with ProjectController
- ✓ File signals propagate correctly
- ✓ Assets folder auto-loads when project opens

## Benefits

1. **Better Organization**: Separate project files from shared assets
2. **Reusability**: Share templates, plots, and reference materials across projects
3. **Flexibility**: Assets folder location is customizable
4. **Future-Proof**: Architecture supports adding more project sections later
5. **Non-Breaking**: Fully backward compatible with existing code

## Future Enhancements

- Add context menu to create new project section
- Allow user to drag-drop rename project sections
- Support for saving/loading multiple simultaneous projects
- Project-specific assets folders (assets per project)
- Collapsible section headers with expand/collapse icons
