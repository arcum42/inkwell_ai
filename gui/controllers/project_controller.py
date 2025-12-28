"""Controller for project lifecycle and RAG operations."""

import os
import hashlib
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressBar
from PySide6.QtCore import QSettings

from core.rag_engine import RAGEngine
from core.tools import register_default_tools
from core.tools.registry import register_by_names
from gui.workers import IndexWorker
from gui.editor import DocumentWidget, ImageViewerWidget


class ProjectController:
    """Handles project open/close/save and RAG indexing."""
    
    def __init__(self, main_window):
        """Initialize project controller.
        
        Args:
            main_window: The MainWindow instance
        """
        self.window = main_window
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.index_worker = None
        self.index_progress_state = None  # (current, total, file) for dashboard
        
    def open_project_dialog(self):
        """Open file dialog to select project folder."""
        folder_path = QFileDialog.getExistingDirectory(self.window, "Select Project Folder")
        if folder_path:
            self.open_project(folder_path)

    def open_project(self, folder_path):
        """Open a project folder.
        
        Args:
            folder_path: Path to project folder
        """
        if self.window.project_manager.open_project(folder_path):
            # Configure tool registry based on project settings
            try:
                enabled = self.window.project_manager.get_enabled_tools()
                if enabled is None:
                    register_default_tools()
                else:
                    register_by_names(enabled)
            except Exception:
                pass
                
            # Add main project to sidebar
            self.window.sidebar.add_project("Project", folder_path)
            
            self.window.setWindowTitle(f"Inkwell AI - {folder_path}")
            self.window.stack.setCurrentWidget(self.window.main_interface)
            
            # Update Image Gen
            self.window.image_gen.set_project_path(folder_path)
            
            # Update Editor
            self.window.editor.set_project_path(folder_path)
            
            # Update Spell Checker with project root
            self.window.spell_checker = self.window.spell_checker.__class__(folder_path)
            spell_check_enabled = self.settings.value("spell_check_enabled", True, type=bool)
            self.window.spell_checker.set_enabled(spell_check_enabled)
            # Update editor's spell-checker reference
            self.window.editor.spell_checker = self.window.spell_checker
            
            # Save to settings
            self.settings.setValue("last_project", folder_path)
            
            # Update Recent Projects
            recent = self.settings.value("recent_projects", [])
            if not isinstance(recent, list):
                recent = []
            
            if folder_path in recent:
                recent.remove(folder_path)
            recent.insert(0, folder_path)
            recent = recent[:5]  # Keep top 5
            self.settings.setValue("recent_projects", recent)
            
            # Initialize RAG
            self.window.rag_engine = RAGEngine(folder_path)
            
            # Clean any previously-indexed files from excluded directories (e.g., .debug)
            self.window.rag_engine.clean_excluded_files()
            
            # Connect RAG engine to sidebar for status indicators
            if hasattr(self.window, 'sidebar'):
                self.window.sidebar.set_rag_engine(self.window.rag_engine, "Project")
            
            # Start indexer worker with cancel support
            self.index_worker = IndexWorker(self.window.rag_engine)
            self.index_worker.progress.connect(self.on_index_progress)
            self.index_worker.finished.connect(self.on_index_finished)
            self.index_worker.start()
            self.index_progress_state = (0, 0, "")
            self.window._update_token_dashboard()
            
            # Reinitialize diff system with new project root
            self.window.chat_controller.reinit_diff_system()
            
            # Show progress bar
            self.window.indexing_progress = QProgressBar()
            self.window.indexing_progress.setTextVisible(True)
            self.window.indexing_progress.setFormat("Indexing: %p% (%v/%m)")
            self.window.statusBar().addWidget(self.window.indexing_progress)
            
            # Update personas in chat widget
            personas = self.window.project_manager.get_all_personas()
            active_name, _ = self.window.project_manager.get_active_persona()
            self.window.chat.update_personas(personas, active_name)
            
            # Try to open assets folder if configured
            self._open_assets_folder()
            
            # Restore Tabs
            self.restore_project_state(folder_path)

    def save_project_state(self):
        """Save current project state (open tabs, etc.)."""
        if not self.window.project_manager.root_path:
            return
            
        project_path = self.window.project_manager.root_path
        
        # Use hash of path for key to avoid issues with special chars
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Get open files
        open_files = []
        for i in range(self.window.editor.tabs.count()):
            widget = self.window.editor.tabs.widget(i)
            if isinstance(widget, (DocumentWidget, ImageViewerWidget)):
                path = widget.property("file_path")
                if path and os.path.exists(path) and not os.path.isdir(path):
                    open_files.append(path)
        
        # Check Image Studio
        image_studio_open = False
        for i in range(self.window.editor.tabs.count()):
            if self.window.editor.tabs.widget(i) == self.window.image_gen:
                image_studio_open = True
                break
        
        self.settings.setValue(f"state/{key}/open_files", open_files)
        self.settings.setValue(f"state/{key}/image_studio_open", image_studio_open)
        self.settings.sync()  # Force write to disk

    def restore_project_state(self, project_path):
        """Restore project state from settings.
        
        Args:
            project_path: Path to project folder
        """
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Restore files
        open_files = self.settings.value(f"state/{key}/open_files", [])
        
        # Ensure it's a list (QSettings might return a string if only one item)
        if open_files and not isinstance(open_files, list):
            open_files = [open_files]
            
        if open_files:
            for path in open_files:
                if os.path.exists(path) and not os.path.isdir(path):
                    # Check extension to decide how to open
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self.window.editor.open_file(path, None)
                    else:
                        content = self.window.project_manager.read_file(path)
                        if content is not None:
                            self.window.editor.open_file(path, content)
        
        # Restore Image Studio
        image_studio_open = self.settings.value(f"state/{key}/image_studio_open", False, type=bool)
        if image_studio_open:
            self.window.open_image_studio()

        # After restoring tabs, populate Context Files list
        try:
            self.window.chat.show_context_spinner()
            self.window.chat_controller.refresh_context_sources_view()
        except Exception:
            pass
    
    def _open_assets_folder(self):
        """Open the configured assets folder in sidebar if it exists."""
        assets_path = self.settings.value("assets_folder", "assets")  # Default to "assets" folder
        
        # If relative path, resolve it
        if assets_path and not os.path.isabs(assets_path):
            # Try relative to project root first
            if self.window.project_manager.root_path:
                proj_assets = os.path.join(self.window.project_manager.root_path, assets_path)
                if os.path.isdir(proj_assets):
                    assets_path = proj_assets
                else:
                    # Try relative to app root (parent of gui/ directory)
                    # Project controller is at: inkwell_ai/gui/controllers/project_controller.py
                    app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    assets_path = os.path.join(app_root, assets_path)
        
        # Only add assets folder if it exists and is different from project root
        if assets_path and os.path.isdir(assets_path):
            if assets_path != self.window.project_manager.root_path:
                print(f"DEBUG: Opening assets folder from {assets_path}")
                self.window.sidebar.add_project("Assets", assets_path)
    
    def on_index_progress(self, current, total, file_path):
        """Update progress bar during indexing.
        
        Args:
            current: Current file count
            total: Total file count
            file_path: Current file being indexed
        """
        if hasattr(self.window, 'indexing_progress'):
            self.window.indexing_progress.setMaximum(total)
            self.window.indexing_progress.setValue(current)
            # Update sidebar to show indexed file status
            if self.window.rag_engine and hasattr(self.window, 'sidebar'):
                self.window.sidebar.update_file_status("Project")
        self.index_progress_state = (current, total, file_path)
        self.window._update_token_dashboard()
    
    def on_index_finished(self):
        """Clean up after indexing completes."""
        if hasattr(self.window, 'indexing_progress'):
            self.window.statusBar().removeWidget(self.window.indexing_progress)
            self.window.indexing_progress.deleteLater()
            del self.window.indexing_progress
        # Final update of file statuses
        if hasattr(self.window, 'sidebar'):
            self.window.sidebar.update_file_status("Project")
        self.index_progress_state = None
        self.window._update_token_dashboard()
        print("Indexing complete")

    def close_project(self):
        """Close current project and return to welcome screen."""
        # Save state, cleanup, and clear last_project setting
        self._shutdown_project_session(clear_last_project=True)
        
        # Switch to Welcome
        self.window.stack.setCurrentWidget(self.window.welcome_widget)

    def _shutdown_project_session(self, clear_last_project=False):
        """Common logic for closing a project session.
        
        Args:
            clear_last_project: Whether to clear last_project setting
        """
        # Save state before closing
        self.save_project_state()
        
        # Clear state
        self.window.project_manager.root_path = None
        
        # Clear all projects from sidebar
        for project_name in list(self.window.sidebar.project_sections.keys()):
            self.window.sidebar.remove_project(project_name)
        
        self.window.setWindowTitle("Inkwell AI")
        
        # Close all tabs
        self.window.editor.tabs.clear()
        self.window.editor.open_files.clear()
        
        # Clear chat
        self.window.chat_controller.save_current_chat_session()  # Save before clearing
        self.window.chat.clear_chat()
        self.window.chat_controller.chat_history = []
        self.window._raw_ai_responses = []  # Clear raw responses tracking
        
        # Cancel RAG indexing worker immediately
        try:
            if self.index_worker is not None:
                self.index_worker.cancel()
                self.index_worker = None
        except Exception:
            pass
        self.window.rag_engine = None
        
        # Clear last project setting if requested (e.g. user explicitly closed project)
        if clear_last_project:
            self.settings.setValue("last_project", "")
        
        # Update Welcome Screen
        self.window.update_welcome_screen()
        self.window._update_token_dashboard(0)
        
    def update_welcome_screen(self):
        """Update welcome screen with recent projects."""
        recent = self.settings.value("recent_projects", [])
        if not isinstance(recent, list):
            recent = []
        # Filter out non-existent paths
        recent = [p for p in recent if os.path.exists(p)]
        self.settings.setValue("recent_projects", recent)
        
        self.window.welcome_widget.set_recent_projects(recent)
        
    def shutdown_on_close(self):
        """Handle cleanup when window closes."""
        # Save current chat session before shutdown
        try:
            self.window.chat_controller.save_current_chat_session()
        except Exception as e:
            print(f"Error saving chat on shutdown: {e}")
        
        # Immediately cancel and terminate indexing worker
        if self.index_worker is not None:
            try:
                self.index_worker.cancel()
                # Force terminate to avoid destructor issues
                if self.index_worker.isRunning():
                    self.index_worker.terminate()
            except Exception:
                pass
