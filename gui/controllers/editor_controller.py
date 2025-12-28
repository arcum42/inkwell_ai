"""Controller for editor and file operations."""

import os
import shutil
from PySide6.QtWidgets import QMessageBox


class EditorController:
    """Handles file operations (rename, move, undo/redo)."""
    
    def __init__(self, main_window):
        """Initialize editor controller.
        
        Args:
            main_window: The MainWindow instance
        """
        self.window = main_window
        self.file_ops_history = []  # list of {"type": "rename"|"move", "old": str, "new": str}
        self.file_ops_redo = []     # stack for redo
        
    def on_file_renamed(self, old_path, new_path):
        """Handle file rename from sidebar.
        
        Args:
            old_path: Original file path
            new_path: New file path
        """
        # Update editor tabs
        if self.window.editor.update_open_file_path(old_path, new_path):
            print(f"Updated editor tabs: {old_path} → {new_path}")
        
        # Record for undo
        self.file_ops_history.append({"type": "rename", "old": old_path, "new": new_path})
        self.file_ops_redo.clear()  # Clear redo stack on new action
        
        # Update RAG index for renamed files
        try:
            if self.window.rag_engine and new_path.endswith((".md", ".txt")):
                # Remove old chunks
                self.window.rag_engine.remove_file(old_path)
                # Index with new path
                try:
                    with open(new_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.window.rag_engine.index_file(new_path, content)
                    # Update sidebar status
                    if hasattr(self.window, 'sidebar'):
                        self.window.sidebar.update_file_status("Project")
                        # Also update Assets if it's a section
                        if "Assets" in self.window.sidebar.project_sections:
                            self.window.sidebar.update_file_status("Assets")
                except Exception as e:
                    print(f"DEBUG: Failed to reindex renamed file {new_path}: {e}")
        except Exception as e:
            print(f"DEBUG: RAG update on rename failed: {e}")
        
        # Update project state
        self.window.save_project_state()
        
    def on_file_moved(self, old_path, new_path):
        """Handle file/folder move from sidebar.
        
        Args:
            old_path: Original path
            new_path: New path
        """
        # Update editor tabs
        if self.window.editor.update_open_file_path(old_path, new_path):
            print(f"Updated editor tabs: {old_path} → {new_path}")
        
        # Record for undo
        self.file_ops_history.append({"type": "move", "old": old_path, "new": new_path})
        self.file_ops_redo.clear()
        
        # Update RAG index for moved files/folders
        try:
            if self.window.rag_engine:
                # Handle both single file and folder moves
                if os.path.isfile(new_path) and new_path.endswith((".md", ".txt")):
                    # Single file move
                    self.window.rag_engine.remove_file(old_path)
                    try:
                        with open(new_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.window.rag_engine.index_file(new_path, content)
                    except Exception as e:
                        print(f"DEBUG: Failed to reindex moved file {new_path}: {e}")
                elif os.path.isdir(new_path):
                    # Folder move - reindex all md/txt files inside
                    for root, dirs, files in os.walk(new_path):
                        for file in files:
                            if file.endswith((".md", ".txt")):
                                file_new_path = os.path.join(root, file)
                                # Compute old path
                                rel_path = os.path.relpath(file_new_path, new_path)
                                file_old_path = os.path.join(old_path, rel_path)
                                self.window.rag_engine.remove_file(file_old_path)
                                try:
                                    with open(file_new_path, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    self.window.rag_engine.index_file(file_new_path, content)
                                except Exception as e:
                                    print(f"DEBUG: Failed to reindex {file_new_path}: {e}")
                # Update sidebar status
                if hasattr(self.window, 'sidebar'):
                    self.window.sidebar.update_file_status("Project")
                    if "Assets" in self.window.sidebar.project_sections:
                        self.window.sidebar.update_file_status("Assets")
        except Exception as e:
            print(f"DEBUG: RAG update on move failed: {e}")
        
        # Update project state
        self.window.save_project_state()
        
    def _perform_move(self, src, dst):
        """Perform actual file/folder move on disk.
        
        Args:
            src: Source path
            dst: Destination path
        """
        if not os.path.exists(src):
            raise FileNotFoundError(f"Source path not found: {src}")
        if os.path.exists(dst):
            raise FileExistsError(f"Destination already exists: {dst}")
        
        # Ensure destination directory exists
        dst_dir = os.path.dirname(dst)
        os.makedirs(dst_dir, exist_ok=True)
        
        # Perform move
        shutil.move(src, dst)
        
    def undo_file_change(self):
        """Undo last file rename or move."""
        if not self.file_ops_history:
            QMessageBox.information(self.window, "Undo", "No file operations to undo.")
            return
        
        op = self.file_ops_history.pop()
        old_path = op["old"]
        new_path = op["new"]
        
        # Reverse the operation on disk
        try:
            if op["type"] in ("rename", "move"):
                self._perform_move(new_path, old_path)
                # Update editor tabs
                self.window.editor.update_open_file_path(new_path, old_path)
                # Reload sidebar
                self.window.sidebar.reload_tree()
                # Push to redo stack
                self.file_ops_redo.append(op)
                self.window.statusBar().showMessage(f"Undone: {os.path.basename(new_path)} → {os.path.basename(old_path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self.window, "Undo Failed", f"Could not undo operation: {e}")
            # Re-add to history if failed
            self.file_ops_history.append(op)
            
    def redo_file_change(self):
        """Redo last undone file operation."""
        if not self.file_ops_redo:
            QMessageBox.information(self.window, "Redo", "No file operations to redo.")
            return
        
        op = self.file_ops_redo.pop()
        old_path = op["old"]
        new_path = op["new"]
        
        # Re-apply the operation
        try:
            if op["type"] in ("rename", "move"):
                self._perform_move(old_path, new_path)
                # Update editor tabs
                self.window.editor.update_open_file_path(old_path, new_path)
                # Reload sidebar
                self.window.sidebar.reload_tree()
                # Push back to history
                self.file_ops_history.append(op)
                self.window.statusBar().showMessage(f"Redone: {os.path.basename(old_path)} → {os.path.basename(new_path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self.window, "Redo Failed", f"Could not redo operation: {e}")
            # Re-add to redo stack if failed
            self.file_ops_redo.append(op)
            
    def update_save_button_state(self, modified):
        """Enable/disable save button based on modification state.
        
        Args:
            modified: Whether the current document is modified
        """
        self.window.save_act.setEnabled(modified)
        
    def save_current_file(self):
        """Save the currently open file."""
        path, content = self.window.editor.get_current_file()
        if not path or content is None:
            return
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.window.editor.mark_current_saved()
            self.window.statusBar().showMessage(f"Saved: {os.path.basename(path)}", 3000)
            # Trigger RAG reindex for saved markdown/text files
            try:
                if self.window.rag_engine and path.endswith((".md", ".txt")):
                    self.window.rag_engine.index_file(path, content)
                    # Update sidebar status indicators
                    if hasattr(self.window, 'sidebar'):
                        self.window.sidebar.update_file_status("Project")
            except Exception as e:
                # Non-fatal; log and continue
                print(f"DEBUG: RAG reindex on save failed for {path}: {e}")
        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Could not save file: {e}")
            
    def on_file_double_clicked(self, index):
        """Handle file double-click in sidebar.
        
        Args:
            index: QModelIndex of clicked item
        """
        path = self.window.sidebar.model.filePath(index)
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.window.editor.open_file(path, content)
            except Exception as e:
                QMessageBox.warning(self.window, "Error", f"Could not open file: {e}")
