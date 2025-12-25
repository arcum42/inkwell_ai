from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFileDialog, QMenuBar, QMenu, QStackedWidget, QMessageBox, QStyle, QInputDialog, QProgressDialog, QProgressBar
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtCore import Qt, QThread, Signal, QCoreApplication
from gui.sidebar import Sidebar
from core.project import ProjectManager
from core.llm_provider import OllamaProvider, LMStudioProvider
from PySide6.QtCore import QSettings

from gui.dialogs.settings_dialog import SettingsDialog
from gui.editor import EditorWidget, DocumentWidget, ImageViewerWidget
from gui.chat import ChatWidget
from gui.welcome import WelcomeWidget
from gui.image_gen import ImageGenWidget

from core.rag_engine import RAGEngine

from gui.dialogs.diff_dialog import DiffDialog
import re
import os
import hashlib
import difflib

from gui.workers import ChatWorker, BatchWorker, ToolWorker, IndexWorker
from gui.dialogs.image_dialog import ImageSelectionDialog
import shutil
from core.tools import register_default_tools
from core.tools.registry import register_by_names


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic.
    Approximates: ~1 token per 4 characters on average.
    This is a rough estimate that works for most models."""
    if not text:
        return 0
    # More sophisticated: count words and adjust for punctuation
    words = len(text.split())
    chars = len(text)
    # Average of 4 chars per token
    return max(words // 2, chars // 4)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inkwell AI")
        self.resize(1200, 800)
        
        self.project_manager = ProjectManager()
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.rag_engine = None
        self.pending_edits = {} # id -> (path, content)
        self.index_worker = None
        self.index_progress_state = None  # (current, total, file) for dashboard
        self._last_token_usage = None
        self._raw_ai_responses = []  # Track raw AI responses before parsing
        
        # ... (Menu Bar setup) ...
        # We need to initialize editor before connecting signals, but editor is in stack?
        # Wait, editor is created in main_interface usually.
        # Let's check where editor is created. It's usually part of main_interface.
        # Ah, I need to see where self.editor is defined. It's likely in init_ui or similar.
        # Looking at previous code, self.editor is used in lambdas.
        # Let's assume it's initialized before toolbar.
        
        # Actually, looking at the file, I need to find where `self.editor` is assigned.
        # It seems I missed where `self.editor` is created in `MainWindow`. 
        # It's likely inside `init_ui` or `setup_ui` which might be called in `__init__`.
        # Wait, `MainWindow` usually has `self.editor = EditorWidget()` somewhere.
        # Let's look at the file content again.
        
        # I'll just add the connection after I find where editor is created.
        # For now, let's add the method `update_save_button_state`.
        
        # Menu Bar
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("File")
        
        open_action = QAction("Open Project Folder", self)
        open_action.triggered.connect(self.open_project_dialog)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_file)
        file_menu.addAction(save_action)
        
        close_project_action = QAction("Close Project", self)
        close_project_action.triggered.connect(self.close_project)
        file_menu.addAction(close_project_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = self.menu_bar.addMenu("Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.editor.undo())
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.editor.redo())
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.editor.cut())
        edit_menu.addAction(cut_action)
        
        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.editor.copy())
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.editor.paste())
        edit_menu.addAction(paste_action)
        
        # Settings Menu
        settings_menu = self.menu_bar.addMenu("Settings")
        settings_action = QAction("Preferences...", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(settings_action)
        
        # Debug Menu
        debug_menu = self.menu_bar.addMenu("Debug")
        export_debug_action = QAction("Export Debug Log & Chat", self)
        export_debug_action.triggered.connect(self.export_debug_log)
        debug_menu.addAction(export_debug_action)
        
        # View Menu
        view_menu = self.menu_bar.addMenu("View")
        image_studio_action = QAction("Image Studio", self)
        image_studio_action.triggered.connect(self.open_image_studio)
        view_menu.addAction(image_studio_action)
        
        chat_history_action = QAction("Chat History...", self)
        chat_history_action.triggered.connect(self.open_chat_history)
        view_menu.addAction(chat_history_action)
        
        # Toolbar
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        
        # Standard Icons
        style = self.style()
        
        # Save File
        self.save_act = QAction(style.standardIcon(QStyle.SP_DriveFDIcon), "Save", self)
        self.save_act.setStatusTip("Save current file")
        self.save_act.triggered.connect(self.save_current_file)
        self.save_act.setEnabled(False) # Disabled by default
        self.toolbar.addAction(self.save_act)
        
        self.toolbar.addSeparator()

        # New File
        new_file_act = QAction(style.standardIcon(QStyle.SP_FileIcon), "New File", self)
        new_file_act.setStatusTip("Create a new file")
        new_file_act.triggered.connect(lambda: self.sidebar.create_new_file(self.sidebar.tree.currentIndex()))
        self.toolbar.addAction(new_file_act)
        
        # New Folder
        new_folder_act = QAction(style.standardIcon(QStyle.SP_DirIcon), "New Folder", self)
        new_folder_act.setStatusTip("Create a new folder")
        new_folder_act.triggered.connect(lambda: self.sidebar.create_new_folder(self.sidebar.tree.currentIndex()))
        self.toolbar.addAction(new_folder_act)

        # Rename
        rename_act = QAction(QIcon.fromTheme("edit-rename"), "Rename", self)
        if rename_act.icon().isNull():
            rename_act.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        rename_act.setStatusTip("Rename selected file/folder")
        rename_act.triggered.connect(lambda: self.sidebar.rename_item(self.sidebar.tree.currentIndex()))
        self.toolbar.addAction(rename_act)

        # Move To
        move_act = QAction(QIcon.fromTheme("transform-move"), "Move To…", self)
        if move_act.icon().isNull():
            move_act.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        move_act.setStatusTip("Move selected file/folder")
        move_act.triggered.connect(lambda: self.sidebar.move_item(self.sidebar.tree.currentIndex()))
        self.toolbar.addAction(move_act)

        # Undo File Change
        file_undo_act = QAction(QIcon.fromTheme("edit-undo"), "Undo File Change", self)
        if file_undo_act.icon().isNull():
            file_undo_act.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        file_undo_act.setStatusTip("Undo last file rename/move")
        file_undo_act.setShortcut(QKeySequence("Ctrl+Alt+Z"))
        file_undo_act.triggered.connect(self.undo_file_change)
        self.toolbar.addAction(file_undo_act)

        # Redo File Change
        file_redo_act = QAction(QIcon.fromTheme("edit-redo"), "Redo File Change", self)
        if file_redo_act.icon().isNull():
            file_redo_act.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        file_redo_act.setStatusTip("Redo last undone file rename/move")
        file_redo_act.setShortcut(QKeySequence("Ctrl+Alt+Y"))
        file_redo_act.triggered.connect(self.redo_file_change)
        self.toolbar.addAction(file_redo_act)
        
        # Open Project
        open_act = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "Open Project", self)
        open_act.setStatusTip("Open a project folder")
        open_act.triggered.connect(self.open_project_dialog)
        self.toolbar.addAction(open_act)
        
        # Close Project
        close_act = QAction(style.standardIcon(QStyle.SP_DialogCloseButton), "Close Project", self)
        close_act.setStatusTip("Close current project")
        close_act.triggered.connect(self.close_project)
        self.toolbar.addAction(close_act)
        
        self.toolbar.addSeparator()
        
        # Cut
        cut_act = QAction(QIcon.fromTheme("edit-cut"), "Cut", self)
        cut_act.triggered.connect(lambda: self.editor.cut())
        self.toolbar.addAction(cut_act)
        
        # Copy
        copy_act = QAction(QIcon.fromTheme("edit-copy"), "Copy", self)
        copy_act.triggered.connect(lambda: self.editor.copy())
        self.toolbar.addAction(copy_act)
        
        # Paste
        paste_act = QAction(QIcon.fromTheme("edit-paste"), "Paste", self)
        paste_act.triggered.connect(lambda: self.editor.paste())
        self.toolbar.addAction(paste_act)
        
        self.toolbar.addSeparator()
        
        # Undo
        undo_act = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Undo", self)
        undo_act.triggered.connect(lambda: self.editor.undo())
        self.toolbar.addAction(undo_act)
        
        # Redo
        redo_act = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Redo", self)
        redo_act.triggered.connect(lambda: self.editor.redo())
        self.toolbar.addAction(redo_act)
        
        self.toolbar.addSeparator()
        
        # Image Studio
        img_act = QAction(style.standardIcon(QStyle.SP_DesktopIcon), "Image Studio", self)
        img_act.setStatusTip("Open Image Studio")
        img_act.triggered.connect(self.open_image_studio)
        self.toolbar.addAction(img_act)
        
        # Settings
        settings_act = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "Settings", self)
        settings_act.triggered.connect(self.open_settings_dialog)
        self.toolbar.addAction(settings_act)
        
        # Formatting Toolbar
        self.addToolBarBreak() # Start new row
        self.format_toolbar = self.addToolBar("Formatting")
        self.format_toolbar.setMovable(False)
        
        # Bold
        bold_act = QAction(QIcon.fromTheme("format-text-bold"), "Bold", self)
        bold_act.triggered.connect(lambda: self.editor.format_bold())
        self.format_toolbar.addAction(bold_act)
        
        # Italic
        italic_act = QAction(QIcon.fromTheme("format-text-italic"), "Italic", self)
        italic_act.triggered.connect(lambda: self.editor.format_italic())
        self.format_toolbar.addAction(italic_act)
        
        # Code Block
        code_act = QAction(QIcon.fromTheme("format-text-code"), "Code Block", self) 
        if code_act.icon().isNull(): code_act.setText("Code Block")
        code_act.triggered.connect(lambda: self.editor.format_code_block())
        self.format_toolbar.addAction(code_act)
        
        # Quote
        quote_act = QAction(QIcon.fromTheme("format-text-blockquote"), "Quote", self) # Try standard name
        if quote_act.icon().isNull(): quote_act.setText("Quote")
        quote_act.triggered.connect(lambda: self.editor.format_quote())
        self.format_toolbar.addAction(quote_act)
        
        self.format_toolbar.addSeparator()
        
        # Headers
        h1_act = QAction("H1", self)
        h1_act.triggered.connect(lambda: self.editor.format_h1())
        self.format_toolbar.addAction(h1_act)
        
        h2_act = QAction("H2", self)
        h2_act.triggered.connect(lambda: self.editor.format_h2())
        self.format_toolbar.addAction(h2_act)
        
        h3_act = QAction("H3", self)
        h3_act.triggered.connect(lambda: self.editor.format_h3())
        self.format_toolbar.addAction(h3_act)
        
        self.format_toolbar.addSeparator()
        
        # Link
        link_act = QAction(QIcon.fromTheme("insert-link"), "Link", self)
        link_act.triggered.connect(lambda: self.editor.insert_link())
        self.format_toolbar.addAction(link_act)
        
        # Image
        image_act = QAction(QIcon.fromTheme("insert-image"), "Image", self)
        image_act.triggered.connect(lambda: self.editor.insert_image())
        self.format_toolbar.addAction(image_act)
        
        # Central Stack (Welcome vs Main Interface)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # 1. Welcome Screen
        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.open_clicked.connect(self.open_project_dialog)
        self.welcome_widget.recent_clicked.connect(self.open_project)
        self.stack.addWidget(self.welcome_widget)
        
        # 2. Main Interface
        self.main_interface = QWidget()
        main_layout = QHBoxLayout(self.main_interface)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for Sidebar vs Main Content
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.tree.doubleClicked.connect(self.on_file_double_clicked)
        # Keep editor tabs in sync when files are renamed or moved from sidebar
        self.sidebar.file_renamed.connect(self.on_file_renamed)
        self.sidebar.file_moved.connect(self.on_file_moved)
        self.main_splitter.addWidget(self.sidebar)
        
        # Content Splitter (Editor vs Chat)
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.content_splitter)
        
        # Editor Area
        self.editor = EditorWidget()
        self.editor.modification_changed.connect(self.update_save_button_state) # Connect signal
        self.editor.batch_edit_requested.connect(self.handle_batch_edit)
        self.editor.tab_closed.connect(self.save_project_state) # Save state when tabs are closed
        self.content_splitter.addWidget(self.editor)
        
        # Image Studio
        self.image_gen = ImageGenWidget(self.settings)
        # self.editor.add_tab(self.image_gen, "Image Studio") # Don't open by default, let persistence handle it
        
        # Chat Interface
        self.chat = ChatWidget()
        self.chat.message_sent.connect(self.handle_chat_message)
        self.chat.link_clicked.connect(self.handle_chat_link)
        self.chat.save_chat_requested.connect(self.handle_save_chat)
        self.chat.copy_to_file_requested.connect(self.handle_copy_chat_to_file)
        self.chat.message_deleted.connect(self.handle_message_deleted)
        self.chat.message_edited.connect(self.handle_message_edited)
        self.chat.regenerate_requested.connect(self.handle_regenerate)
        self.chat.continue_requested.connect(self.handle_continue)
        self.chat.new_chat_requested.connect(self.handle_new_chat)
        self.chat.provider_changed.connect(self.on_provider_changed)
        self.chat.model_changed.connect(self.on_model_changed)
        self.chat.refresh_models_requested.connect(self.on_refresh_models)
        self.chat.context_level_changed.connect(self.on_context_level_changed)
        # Status message when copying messages/chat
        self.chat.message_copied.connect(self.on_message_copied)
        self.content_splitter.addWidget(self.chat)

        # Initialize model controls
        self.update_model_controls()
        
        # Set initial sizes
        self.main_splitter.setSizes([240, 960])
        self.content_splitter.setSizes([700, 260])
        
        self.stack.addWidget(self.main_interface)
        
        # Start at Welcome
        self.stack.setCurrentWidget(self.welcome_widget)
        
        self.chat_history = [] # List of {"role": "user/assistant", "content": "..."}
        self.context_level = "visible"  # Default context level
        # File operations history for undo/redo
        self.file_ops_history = []  # list of {"type": "rename"|"move", "old": str, "new": str}
        self.file_ops_redo = []     # stack for redo
        
        # Load Recent Projects for Welcome Screen
        self.update_welcome_screen()

        # Token dashboard in status bar
        self.token_status = QLabel("Tokens: --/-- | Cache: -- | Index: idle")
        self.statusBar().addPermanentWidget(self.token_status)
        
        # Auto-open last project
        last_project = self.settings.value("last_project")
        if last_project and os.path.exists(last_project):
            self.open_project(last_project)

    def update_welcome_screen(self):
        recent_projects = self.settings.value("recent_projects", [])
        # Ensure it's a list (QSettings might return something else if empty)
        if not isinstance(recent_projects, list):
            recent_projects = []
        self.welcome_widget.set_recent_projects(recent_projects)

    def update_model_controls(self):
        """Update model controls with current settings and available models."""
        try:
            provider_name = self.settings.value("llm_provider", "Ollama")
            provider = self.get_llm_provider()
            
            # Get available models
            models = provider.list_models()
            
            # Determine which models support vision
            vision_models = [m for m in models if provider.is_vision_model(m)]
            
            # Get current model based on provider
            if provider_name == "Ollama":
                current_model = self.settings.value("ollama_model", "llama3")
            else:
                current_model = self.settings.value("lm_studio_model", "default")
            
            # Update UI with vision model indicators
            self.chat.update_model_info(provider_name, current_model, models, vision_models)
        except Exception as e:
            print(f"DEBUG: Failed to update model controls: {e}")
            # Set defaults
            self.chat.update_model_info("Ollama", "llama3", ["llama3"], [])
    
    def on_provider_changed(self, provider_name):
        """Handle provider selection change."""
        self.settings.setValue("llm_provider", provider_name)
        self.update_model_controls()
    
    def on_model_changed(self, model_name):
        """Handle model selection change."""
        # Get the raw model name (strip vision indicator if present)
        raw_model = self.chat.model_combo.currentData()
        if raw_model is None:
            # Fallback: strip indicator from display text
            raw_model = self.chat.model_combo.currentText().replace("👁️", "").strip()
        
        if not raw_model:
            return
        
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            self.settings.setValue("ollama_model", raw_model)
        else:
            self.settings.setValue("lm_studio_model", raw_model)
    
    def on_refresh_models(self):
        """Refresh available models from provider."""
        self.update_model_controls()
    
    def on_context_level_changed(self, level):
        """Handle context level change."""
        self.context_level = level

    def get_llm_provider(self):
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            url = self.settings.value("ollama_url", "http://localhost:11434")
            return OllamaProvider(base_url=url)
        else:
            url = self.settings.value("lm_studio_url", "http://localhost:1234")
            return LMStudioProvider(base_url=url)

    def handle_chat_message(self, message):
        print(f"DEBUG: Context level for this message: {self.context_level}")
        self.chat_history.append({"role": "user", "content": message})
        
        provider = self.get_llm_provider()
        # Read model from correct settings key based on provider
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            model = self.settings.value("ollama_model", "llama3")
        else:
            model = self.settings.value("lm_studio_model", "llama3")
        token_usage = estimate_tokens(message)
        token_breakdown = {"User message": token_usage}

        # Update chat header to reflect current model
        try:
            provider_name = self.settings.value("llm_provider", "Ollama")
            models = provider.list_models()
            vision_models = [m for m in models if provider.is_vision_model(m)]
            self.chat.update_model_info(provider_name, model, models, vision_models)
        except Exception:
            pass
        
        # Retrieve context if RAG is active and context level allows
        context = []
        mentioned_files = set()
        
        if self.context_level != "none" and self.rag_engine:
            print(f"DEBUG: Querying RAG for: {message}")
            context = self.rag_engine.query(message, n_results=5, include_metadata=True)
            print(f"DEBUG: Retrieved {len(context)} chunks")
            
            # Extract mentioned file paths and estimate tokens
            rag_file_info = []
            for chunk in context:
                meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                source = meta.get("source")
                if source:
                    mentioned_files.add(source)
            
            if mentioned_files:
                for source in sorted(mentioned_files):
                    try:
                        content = self.project_manager.read_file(source)
                        if content:
                            tokens = estimate_tokens(content)
                            rag_file_info.append(f"{source} ({tokens} tokens)")
                            token_usage += tokens
                            token_breakdown[f"RAG: {source}"] = token_breakdown.get(f"RAG: {source}", 0) + tokens
                    except Exception:
                        pass
                
                if rag_file_info:
                    print(f"DEBUG: Files from RAG context: {', '.join(rag_file_info)}")
            
        # Get base system prompt and enhance it with edit format instructions FIRST
        self.chat.show_thinking()
        
        base_system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )
        
        # Check if image generation is enabled
        enabled_tools = self.project_manager.get_enabled_tools()
        image_gen_enabled = enabled_tools is None or "GENERATE_IMAGE" in enabled_tools
        
        # Add comprehensive edit format instructions
        edit_instructions = (
            "\n\n## Edit Formats\n"
            "Use PATCH for line-level edits or range replacements:\n"
            ":::PATCH path/to/file.md\n"
            "L42: old text => new text\n"
            "L20-L23:\n"
            "New content for lines 20-23...\n"
            "Multiple lines here...\n"
            ":::END:::\n"
            "\n"
            "Use UPDATE when replacing entire file or large sections:\n"
            ":::UPDATE path/to/file.md\n"
            "Complete new file content...\n"
            ":::END:::\n"
        )
        
        if image_gen_enabled:
            edit_instructions += (
                "\n"
                "Image generation:\n"
                ":::GENERATE_IMAGE:::\n"
                "Prompt: Description...\n"
                ":::END:::\n"
            )
        
        edit_instructions += (
            "\n"
            "CRITICAL RULES:\n"
            "- ALWAYS use :::PATCH::: or :::UPDATE::: directives for file edits\n"
            "- Output ONLY the directive blocks (:::PATCH...:::END:::)\n"
            "- Do NOT wrap directives in code fences (no ```text or ```patch)\n"
            "- Do NOT output edit: links or HTML anchors\n"
            "- Do NOT include reminders or instructions in your response\n"
            "- Explanations can come AFTER the directive block\n"
            "- When editing selections repeatedly, continue using :::PATCH::: format for each edit\n"
        )
        
        system_prompt = base_system_prompt + edit_instructions
            
        # Add Active File Context based on context level
        active_path, active_content = self.editor.get_current_file()
        
        # Include active file if not in "none" mode
        if active_path and active_content and self.context_level != "none":
            tokens = estimate_tokens(active_content)
            print(f"DEBUG: Including active file in context: {active_path} ({tokens} tokens)")
            system_prompt += f"\nCurrently Open File ({active_path}):\n{active_content}\n"
            token_usage += tokens
            token_breakdown[f"Active: {active_path}"] = tokens
        
        # Add other open tabs if context level is "all_open" or "full"
        if self.context_level in ("all_open", "full"):
            open_files = []
            for i in range(self.editor.tabs.count()):
                tab_widget = self.editor.tabs.widget(i)
                tab_path = tab_widget.property("file_path") if hasattr(tab_widget, 'property') else None
                
                if tab_path and tab_path != active_path:
                    try:
                        content = self.project_manager.read_file(tab_path)
                        if content:
                            tokens = estimate_tokens(content)
                            open_files.append(f"{tab_path} ({tokens} tokens)")
                            system_prompt += f"\nOpen File ({tab_path}):\n{content}\n"
                            token_usage += tokens
                            token_breakdown[f"Open tab: {tab_path}"] = tokens
                    except Exception:
                        pass
            
            if open_files:
                print(f"DEBUG: Including open tabs in context: {', '.join(open_files)}")
        
        # Check Vision Capability
        is_vision = provider.is_vision_model(model)
        attached_images = []
        attached_image_names = []
        
        if is_vision:
            system_prompt += "\n\n[System] Current model is VISION CAPABLE. You can see images provided in the context."
            
            # Collect all open images from tabs
            for i in range(self.editor.tabs.count()):
                widget = self.editor.tabs.widget(i)
                if isinstance(widget, ImageViewerWidget):
                    path = widget.property("file_path")
                    if path and os.path.exists(path):
                        try:
                            b64 = self.project_manager.get_image_base64(path)
                            if b64:
                                attached_images.append(b64)
                                attached_image_names.append(os.path.basename(path))
                        except Exception as e:
                            print(f"DEBUG: Error reading open image {path}: {e}")
            
            # Also auto-detect images referenced in the message
            found_paths = self.project_manager.find_images_in_text(message)
            if found_paths:
                print(f"DEBUG: Found referenced images in message: {found_paths}")
                for p in found_paths:
                    # Skip if already added from open tabs
                    if any(b64 == self.project_manager.get_image_base64(p) for b64 in attached_images):
                        continue
                    b64 = self.project_manager.get_image_base64(p)
                    if b64:
                        attached_images.append(b64)
                        attached_image_names.append(os.path.basename(p))
            
            if attached_image_names:
                self.chat.append_message("System", f"<i>Attached images: {', '.join(attached_image_names)}</i>")

        else:
            system_prompt += "\n\n[System] Current model is TEXT ONLY."

        # Inject Project Structure
        if self.project_manager.root_path:
            structure = self.project_manager.get_project_structure()
            # We truncate if it's too huge
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            token_usage += estimate_tokens(structure)
            token_breakdown["Project structure"] = estimate_tokens(structure)
            
        # Add active file context
        if active_path:
            system_prompt += f"\n\nActive File: {active_path}\nContent:\n{active_content}"
            token_usage += estimate_tokens(active_content)
            token_breakdown[f"Active content: {active_path}"] = estimate_tokens(active_content)

            # Include selection info if present
            try:
                current_editor = self.editor.get_current_editor()
                if current_editor:
                    cursor = current_editor.textCursor()
                    if cursor and cursor.hasSelection():
                        doc = current_editor.document()
                        start_pos = cursor.selectionStart()
                        end_pos = cursor.selectionEnd()
                        start_block = doc.findBlock(start_pos)
                        end_block = doc.findBlock(end_pos)
                        sel_start_line = start_block.blockNumber() + 1
                        sel_end_line = end_block.blockNumber() + 1
                        sel_text = cursor.selectedText().replace('\u2029', '\n')
                        # Append selection context to the last user message for precise targeting
                        self.chat_history[-1]['content'] += (
                            f"\n\nSelected Range in {active_path}: L{sel_start_line}-L{sel_end_line}\n"
                            f"Selected Text:\n```text\n{sel_text}\n```\n"
                            f"Prefer PATCH targeting the selected lines when possible."
                        )
                        # Store selection info for apply-time restriction
                        self._last_selection_info = {
                            'path': active_path,
                            'start_line': sel_start_line,
                            'end_line': sel_end_line,
                        }
                        # Show a small note in chat
                        self.chat.append_message("System", f"<i>Selection sent for {active_path}: L{sel_start_line}-L{sel_end_line}</i>")
                        token_usage += estimate_tokens(sel_text)
                        token_breakdown[f"Selection: {active_path} L{sel_start_line}-L{sel_end_line}"] = estimate_tokens(sel_text)
            except Exception as e:
                print(f"DEBUG: Failed to include selection info: {e}")
             
        enabled_tools = self.project_manager.get_enabled_tools()
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=attached_images,
            enabled_tools=enabled_tools,
        )
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

        # Update dashboard with latest token estimate
        if context:
            for chunk in context:
                if isinstance(chunk, dict):
                    ctokens = estimate_tokens(chunk.get("text", ""))
                    token_usage += ctokens
                    source = chunk.get("metadata", {}).get("source", "context")
                    token_breakdown[f"RAG chunk: {source}"] = token_breakdown.get(f"RAG chunk: {source}", 0) + ctokens
                else:
                    ctokens = estimate_tokens(str(chunk))
                    token_usage += ctokens
                    token_breakdown["RAG chunk"] = token_breakdown.get("RAG chunk", 0) + ctokens
        self._update_token_dashboard(token_usage, token_breakdown)

    def is_response_complete(self, response: str) -> bool:
        """Check if the response appears complete.
        Returns False if response is likely incomplete (missing closing blocks, etc.)"""
        # Check for incomplete UPDATE blocks
        update_opens = response.count(":::UPDATE")
        update_closes = response.count(":::END:::") + response.count(":::END") + response.count(":::")
        # Note: this is a heuristic; could have false positives but better safe than sorry
        
        # If there are unclosed UPDATE blocks, response is incomplete
        if update_opens > 0 and update_closes < update_opens:
            return False
        
        # Check for incomplete GENERATE_IMAGE blocks
        gen_opens = response.count(":::GENERATE_IMAGE")
        if gen_opens > 0 and update_closes < gen_opens:
            return False
        
        # If response ends abruptly with specific tokens, it's likely incomplete
        incomplete_endings = [
            "- ",
            "* ",
            "1. ",
            ": ",
            "and ",
            "or ",
            "in ",
            "the ",
        ]
        
        # Only flag if it's a very short ending
        if len(response) > 50:
            for ending in incomplete_endings:
                if response.rstrip().endswith(ending):
                    return False
        
        return True

    def on_chat_response(self, response):
        # Remove thinking indicator
        self.chat.remove_thinking()
        
        # Store raw response for debug export before any parsing
        self._raw_ai_responses.append(response)
        
        print(f"DEBUG: Raw AI Response:\n{response}")

        import uuid

        # Capture any edit:XYZ ids already present in the response so we can reuse them
        provided_edit_ids = re.findall(r"edit:([0-9a-fA-F-]{6,})", response)
        # Preserve order but de-duplicate
        seen_ids = set()
        provided_edit_ids = [eid for eid in provided_edit_ids if not (eid in seen_ids or seen_ids.add(eid))]

        def next_edit_id() -> str:
            if provided_edit_ids:
                return provided_edit_ids.pop(0)
            return str(uuid.uuid4())
        
        # Parse for :::TOOL:...::: blocks
        tool_pattern = r":::TOOL:(.*?):(.*?):::"
        tool_match = re.search(tool_pattern, response)
        print(f"DEBUG: Checking for tools in response... Match found: {tool_match is not None}")
        if tool_match:
            tool_name = tool_match.group(1).strip()
            query = tool_match.group(2).strip()
            print(f"DEBUG: Executing tool '{tool_name}' with query '{query}'")
            self.chat.append_message("System", f"<i>Running tool: {tool_name}...</i>")
            self.chat.show_thinking() # thinking again for tool
            
            self.tool_worker = ToolWorker(tool_name, query, enabled_tools=self.project_manager.get_enabled_tools(), project_manager=self.project_manager)
            self.tool_worker.finished.connect(self.on_tool_finished)
            self.tool_worker.start()
            return # Stop processing other things if tool runs (it effectively continues the conversation)

        # Strip common prefixes that models might add (reminder text, etc.)
        processing_response = response
        reminder_pattern = r"^[^\n]*REMINDER[^\n]*:.*?\n+"
        processing_response = re.sub(reminder_pattern, "", processing_response, flags=re.IGNORECASE)

        # Parse for :::UPDATE...::: blocks
        # Improved regex to handle whitespace/newlines, quoted paths
        # Accepts :::END:::, :::END, or just ::: as the closer
        pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        matches = re.findall(pattern, processing_response, re.DOTALL)
        # Fallback parsing: allow quoted paths or path on next line
        if not matches:
            alt_pattern = r":::UPDATE\s*(?:\"([^\"]+)\"|'([^']+)'|([^:]+))\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
            alt = re.findall(alt_pattern, processing_response, re.DOTALL)
            # alt is list of tuples with possibly empty groups; pick first non-empty path group
            normalized = []
            for g1, g2, g3, content in alt:
                path = g1 or g2 or g3 or ""
                normalized.append((path, content))
            matches = normalized

        # Parse for :::PATCH...::: blocks (line-level replacements)
        # IMPORTANT: Handle fenced PATCH blocks first to avoid capturing garbage
        # Pattern: ``` (optional lang) \n :::PATCH path [::: optional] \n body \n :::END::: \n ```
        fenced_patch_pattern = r"```[a-z]*\s*\n\s*:::PATCH\s+([^\n:]+)\s*(?:::\s*)?\n((?:(?!:::END:::)[\s\S])*?)\s*:::END:::\s*\n```"
        fenced_patch_matches = re.findall(fenced_patch_pattern, processing_response, re.DOTALL | re.IGNORECASE)
        
        # Remove fenced PATCH blocks from processing_response to avoid double-parsing
        processing_response_no_fenced = re.sub(fenced_patch_pattern, '', processing_response, flags=re.DOTALL | re.IGNORECASE)
        
        # Now parse bare PATCH blocks from the cleaned response
        patch_pattern = r":::PATCH\s*(.*?)\s*:::\s*\n(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        patch_alt = r":::PATCH\s*(?:\"([^\"]+)\"|'([^']+)'|([^:]+))\s*:::\s*\n(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        malformed_patch = r":::PATCH\s+([^\n:]+?)\s*\n+(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        # Handle malformed "path:::" format: :::PATCH path:::/some/file
        path_triple_colon = r":::PATCH\s+path:::([^\n]+?)\s*\n(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        # Handle malformed comma/semicolon format: :::PATCH /path,line;;line:::
        comma_semicolon_patch = r":::PATCH\s+([^,\n]+)[,;]+.*?:::\s*\n(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        inline_patch_pattern = r":::PATCH\s+(\S+)\s+(?!\n)(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        inline_patch_alt = r":::PATCH\s+(?:\"([^\"]+)\"|'([^']+)')\s+(?!\n)(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        
        patch_matches = list(fenced_patch_matches)  # Start with fenced matches
        bare_matches = re.findall(patch_pattern, processing_response_no_fenced, re.DOTALL)
        patch_matches.extend(bare_matches)
        
        # Check for path::: malformed format
        path_triple_matches = re.findall(path_triple_colon, processing_response_no_fenced, re.DOTALL)
        if path_triple_matches:
            print(f"DEBUG: Found {len(path_triple_matches)} PATCH blocks with 'path:::' format")
            patch_matches.extend(path_triple_matches)
        
        # Check for comma/semicolon malformed format
        comma_semicolon_matches = re.findall(comma_semicolon_patch, processing_response_no_fenced, re.DOTALL)
        if comma_semicolon_matches:
            print(f"DEBUG: Found {len(comma_semicolon_matches)} PATCH blocks with comma/semicolon format, extracting path only")
            patch_matches.extend(comma_semicolon_matches)
        
        if not patch_matches:
            alt = re.findall(patch_alt, processing_response_no_fenced, re.DOTALL)
            normalized = []
            for g1, g2, g3, body in alt:
                path = g1 or g2 or g3 or ""
                normalized.append((path, body))
            patch_matches = normalized
        
        # Fallback: handle malformed PATCH without closing ::: after path
        if not patch_matches:
            alt2 = re.findall(malformed_patch, processing_response_no_fenced, re.DOTALL)
            if alt2:
                print(f"DEBUG: Found {len(alt2)} malformed PATCH blocks (missing ::: after path)")
                patch_matches = alt2

        # Inline PATCH format on the SAME line (no newline after path)
        inline_patch_matches = re.findall(inline_patch_pattern, processing_response_no_fenced, re.DOTALL)
        inline_alt = re.findall(inline_patch_alt, processing_response_no_fenced, re.DOTALL)
        for m in inline_patch_matches:
            patch_matches.append(m)
        for g1, g2, body in inline_alt:
            path = g1 or g2 or ""
            patch_matches.append((path, body))

        # Dedupe patch matches (some formats may double-match)
        if patch_matches:
            unique = []
            seen = set()
            for p, b in patch_matches:
                key = (p.strip(), b.strip())
                if key in seen:
                    continue
                seen.add(key)
                unique.append((p, b))
            patch_matches = unique
        
        print(f"DEBUG: Found {len(matches)} edit blocks and {len(patch_matches)} patch blocks")
        
        display_response = response
        
        # Determine active file for path normalization during edit parsing
        try:
            active_path = self.editor.get_current_file()[0]
        except Exception:
            active_path = None
        
        non_text_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                               '.mp4', '.avi', '.mov', '.mp3', '.wav',
                               '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}

        if matches:

            def replace_match(match):
                m_path = self._normalize_edit_path(match.group(1).strip(), active_path)
                m_content = match.group(2).strip().replace('\\n', '\n')

                # Check if this is a non-text file and convert to .txt
                file_ext = os.path.splitext(m_path)[1].lower()
                if file_ext in non_text_extensions:
                    original_path = m_path
                    m_path = os.path.splitext(m_path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text file edit from {original_path} to {m_path} (in display)")

                m_id = next_edit_id()
                self.pending_edits[m_id] = (m_path, m_content)
                print(f"DEBUG: Parsed UPDATE for {m_path}")
                return f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>'

            display_response = re.sub(pattern, replace_match, display_response, flags=re.DOTALL)

        if patch_matches:

            def _clean_patch_body(body: str) -> str:
                cleaned = body.strip()
                # Strip embedded links that model incorrectly placed inside PATCH body
                link_pattern = r'<br><b><a href="edit:[^"]+">.*?</a></b><br>'
                if re.search(link_pattern, cleaned):
                    cleaned = re.sub(link_pattern, '', cleaned).strip()
                    print("DEBUG: Stripped embedded link from PATCH body")
                # Truncate anything after :::END::: if model included extras
                if ':::END:::' in cleaned:
                    cleaned = cleaned.split(':::END:::')[0]
                # Strip nested fences like ```text ... ```
                nested_fence = re.match(r"^(L\d+(?:\s*-\s*L\d+)?:)?\s*```[a-z]*\s*\n(.*?)\n```\s*$", cleaned, re.DOTALL)
                if nested_fence:
                    prefix = nested_fence.group(1) or ''
                    inner = nested_fence.group(2)
                    cleaned = (prefix + "\n" + inner).strip()
                    print("DEBUG: Stripped nested code fence from PATCH body")
                return cleaned

            def replace_patch(match):
                m_path_raw = match.group(1)
                if not m_path_raw:
                    print("DEBUG: PATCH block has no path, skipping")
                    return match.group(0)
                m_path = self._normalize_edit_path(m_path_raw.strip(), active_path)
                patch_body = _clean_patch_body(match.group(2))
                
                success, m_new_content = self._apply_patch_block(m_path, patch_body)
                if not success or m_new_content is None:
                    print(f"DEBUG: Failed to apply patch for {m_path} in display substitution")
                    return match.group(0)

                file_ext = os.path.splitext(m_path)[1].lower()
                if file_ext in non_text_extensions:
                    original_path = m_path
                    m_path = os.path.splitext(m_path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text patch from {original_path} to {m_path} (in display)")

                m_id = next_edit_id()
                self.pending_edits[m_id] = (m_path, m_new_content)
                print(f"DEBUG: Parsed patch for {m_path}")
                return f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>'

            # Substitute all PATCH pattern variants
            display_response = re.sub(fenced_patch_pattern, replace_patch, display_response, flags=re.DOTALL | re.IGNORECASE)
            display_response = re.sub(patch_pattern, replace_patch, display_response, flags=re.DOTALL)
            display_response = re.sub(patch_alt, replace_patch, display_response, flags=re.DOTALL)
            display_response = re.sub(malformed_patch, replace_patch, display_response, flags=re.DOTALL)
            display_response = re.sub(inline_patch_pattern, replace_patch, display_response, flags=re.DOTALL)
            display_response = re.sub(inline_patch_alt, replace_patch, display_response, flags=re.DOTALL)

        # Parse for fenced PATCH blocks (code fence style)
        fenced_patch_pattern_alt = r"```patch\s*\n(.*?)```"
        fenced_patch_blocks = re.findall(fenced_patch_pattern_alt, processing_response, re.DOTALL | re.IGNORECASE)
        if fenced_patch_blocks:
            def replace_fenced_patch(match):
                inner = match.group(1)
                # First non-empty line is path; rest is patch body
                lines = inner.splitlines()
                path = ""
                body_lines = []
                for idx, ln in enumerate(lines):
                    if ln.strip():
                        path = ln.strip()
                        body_lines = lines[idx + 1:]
                        break
                # Remove optional :::END::: terminator
                if body_lines and body_lines[-1].strip().startswith(":::END"):
                    body_lines = body_lines[:-1]
                body = "\n".join(body_lines).strip()

                # Fallback to active file if path missing
                m_path = self._normalize_edit_path((path or (active_path or "")).strip(), active_path)
                success, m_new_content = self._apply_patch_block(m_path, body)
                if not success or m_new_content is None:
                    print(f"DEBUG: Failed to apply fenced PATCH for {m_path}")
                    return match.group(0)

                file_ext = os.path.splitext(m_path)[1].lower()
                if file_ext in non_text_extensions:
                    original_path = m_path
                    m_path = os.path.splitext(m_path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text fenced PATCH from {original_path} to {m_path}")

                m_id = next_edit_id()
                self.pending_edits[m_id] = (m_path, m_new_content)
                return f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>'

            display_response = re.sub(fenced_patch_pattern, replace_fenced_patch, display_response, flags=re.DOTALL | re.IGNORECASE)

        # Parse for fenced unified diff blocks and apply them
        diff_pattern = r"```diff\s*\n(.*?)```"
        diff_blocks = re.findall(diff_pattern, processing_response, re.DOTALL)
        if diff_blocks:
            def _extract_diff_target_path(diff_text: str) -> str | None:
                # Try to read from +++ header first; fallback to --- header
                for line in diff_text.splitlines():
                    if line.startswith('+++ '):
                        p = line[4:].strip()
                        if p.startswith('b/') or p.startswith('a/'):
                            p = p[2:]
                        return p
                for line in diff_text.splitlines():
                    if line.startswith('--- '):
                        p = line[4:].strip()
                        if p.startswith('b/') or p.startswith('a/'):
                            p = p[2:]
                        return p
                return None

            def replace_diff_block(match):
                diff_text = match.group(1)
                # Support multi-file diffs inside the fenced block
                file_blocks = self._find_unfenced_unified_diff_blocks(diff_text)
                links_html = []
                if file_blocks:
                    for sub_diff, target_path in file_blocks:
                        norm_path = self._normalize_edit_path(target_path.strip(), active_path)
                        success, m_new = self._apply_unified_diff(norm_path, sub_diff)
                        if not success or m_new is None:
                            print(f"DEBUG: Failed to apply fenced multi-file diff for {norm_path}")
                            continue
                        file_ext = os.path.splitext(norm_path)[1].lower()
                        if file_ext in non_text_extensions:
                            norm_path = os.path.splitext(norm_path)[0] + '.txt'
                        m_id = next_edit_id()
                        self.pending_edits[m_id] = (norm_path, m_new)
                        print(f"DEBUG: Parsed diff for {norm_path}")
                        links_html.append(f'<br><b><a href="edit:{m_id}">Review Changes for {norm_path}</a></b><br>')
                    if links_html:
                        return ''.join(links_html)
                    # Fallback to returning original block if nothing applied
                    return match.group(0)
                else:
                    # Single-file fallback using headers inside the block
                    target_path = _extract_diff_target_path(diff_text) or ''
                    norm_path = self._normalize_edit_path(target_path.strip(), active_path)
                    success, m_new = self._apply_unified_diff(norm_path, diff_text)
                    if not success or m_new is None:
                        return match.group(0)
                    file_ext = os.path.splitext(norm_path)[1].lower()
                    if file_ext in non_text_extensions:
                        norm_path = os.path.splitext(norm_path)[0] + '.txt'
                    m_id = next_edit_id()
                    self.pending_edits[m_id] = (norm_path, m_new)
                    return f'<br><b><a href="edit:{m_id}">Review Changes for {norm_path}</a></b><br>'

            display_response = re.sub(diff_pattern, replace_diff_block, display_response, flags=re.DOTALL)

        # Parse for unfenced unified diff blocks (supports multiple files)
        unfenced_blocks = self._find_unfenced_unified_diff_blocks(processing_response)
        if unfenced_blocks:
            import uuid
            for diff_text, target_path in unfenced_blocks:
                norm_path = self._normalize_edit_path(target_path.strip(), active_path)
                success, new_content = self._apply_unified_diff(norm_path, diff_text)
                if not success or new_content is None:
                    print(f"DEBUG: Failed to apply unfenced unified diff for {norm_path}")
                    continue

                file_ext = os.path.splitext(norm_path)[1].lower()
                if file_ext in non_text_extensions:
                    original_path = norm_path
                    norm_path = os.path.splitext(norm_path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text unfenced unified diff from {original_path} to {norm_path}")

                edit_id = next_edit_id()
                self.pending_edits[edit_id] = (norm_path, new_content)

                # Replace the block in the display with a review link
                link_html = f'<br><b><a href="edit:{edit_id}">Review Changes for {norm_path}</a></b><br>'
                display_response = display_response.replace(diff_text, link_html)

        # Fallback: parse generic code-fenced full content blocks (markdown/md/text)
        # Treat these as full-file UPDATEs targeting the active file when available
        code_block_pattern = r"```(?:markdown|md|text)?\s*\n(.*?)```"
        code_blocks = re.findall(code_block_pattern, processing_response, re.DOTALL)
        # Avoid treating fenced blocks as full updates when explicit edit blocks exist
        has_explicit_edits = bool(matches or patch_matches or diff_blocks or unfenced_blocks)

        # Filter out link-only or directive-only blocks for heuristics
        filtered_blocks = []
        for b in code_blocks:
            stripped_b = b.strip()
            # Skip blocks that contain embedded links (even if not at start)
            if '<br><b><a href="edit:' in stripped_b:
                continue
            # Skip directive blocks
            if re.match(r'^\s*:::(PATCH|UPDATE|GENERATE_IMAGE)', stripped_b):
                continue
            # Skip blocks with malformed tags like </code>
            if re.match(r'^\s*</code>', stripped_b):
                continue
            filtered_blocks.append(b)

        # Fallback: if no explicit edits were parsed but we have exactly one meaningful code block,
        # and selection info exists, treat it as a selection replacement to avoid full-file overwrite
        if (not has_explicit_edits and filtered_blocks and len(filtered_blocks) == 1
                and active_path and hasattr(self, '_last_selection_info') and self._last_selection_info):
            sel = self._last_selection_info
            if sel.get('path') == active_path:
                full_text = filtered_blocks[0]
                selection_lines = sel['end_line'] - sel['start_line'] + 1
                new_content_lines = len(full_text.strip().splitlines())
                if new_content_lines <= selection_lines * 2 and new_content_lines > 0:
                    target_path = self._normalize_edit_path(active_path.strip(), active_path)
                    patch_body = f"L{sel['start_line']}-L{sel['end_line']}:\n{full_text.strip()}"
                    success, new_content = self._apply_patch_block(target_path, patch_body)
                    if success and new_content:
                        edit_id = next_edit_id()
                        self.pending_edits[edit_id] = (target_path, new_content)
                        link_html = f'<br><b><a href="edit:{edit_id}">Review Changes for {target_path}</a></b><br>'
                        replaced = False

                        def replace_first(match: re.Match) -> str:
                            nonlocal replaced
                            block_body = match.group(1)
                            if replaced:
                                return match.group(0)
                            if block_body in filtered_blocks:
                                replaced = True
                                return link_html
                            return match.group(0)

                        display_response = re.sub(code_block_pattern, replace_first, display_response, flags=re.DOTALL)
                        has_explicit_edits = True  # prevent further full-file replacement
                        print(f"DEBUG: Synthesized PATCH from single code block for selection L{sel['start_line']}-L{sel['end_line']} ({new_content_lines} lines vs {selection_lines})")
        
        # ALWAYS strip code blocks that only contain edit: links or directives (models sometimes do this)
        def strip_link_only_blocks(m):
            full_text = m.group(1)
            stripped = full_text.strip()
            # Remove blocks with just edit links
            if re.match(r'^\s*<br><b><a href="edit:', stripped):
                return ''  # Remove the entire fence
            # Remove blocks with just directive blocks (already parsed above)
            if re.match(r'^\s*:::(PATCH|UPDATE|GENERATE_IMAGE)', stripped):
                return ''  # Remove the entire fence
            return m.group(0)  # Keep as-is
        
        display_response = re.sub(code_block_pattern, strip_link_only_blocks, display_response, flags=re.DOTALL)
        
        if code_blocks and active_path and not has_explicit_edits:
            import uuid
            def replace_code_block(m):
                full_text = m.group(1)
                # Skip blocks that only contain edit: links (already stripped above)
                if re.match(r'^\s*<br><b><a href="edit:', full_text.strip()):
                    return m.group(0)  # Keep original fence
                target_path = self._normalize_edit_path(active_path.strip(), active_path)
                
                # Try to determine if this is a selection replacement or full-file replacement
                # by comparing sizes and using selection context
                selection_start_line = None
                selection_end_line = None
                if (hasattr(self, '_last_selection_info') and 
                    self._last_selection_info and
                    self._last_selection_info['path'] == target_path):
                    selection_start_line = self._last_selection_info['start_line']
                    selection_end_line = self._last_selection_info['end_line']
                    selection_lines = selection_end_line - selection_start_line + 1
                    
                    # Size heuristic: if new text is roughly the size of the selection
                    # (within 200% to allow for reformatting), treat as selection replacement
                    new_content_lines = len(full_text.strip().splitlines())
                    if new_content_lines <= selection_lines * 2 and new_content_lines > 0:
                        print(f"DEBUG: replace_code_block selection heuristic: new_lines={new_content_lines}, sel_lines={selection_lines}")
                        print(f"DEBUG: Inferring selection replacement: {new_content_lines} lines vs {selection_lines} selected")
                        # Apply as PATCH to just those lines
                        patch_body = f"L{selection_start_line}-L{selection_end_line}:\n{full_text.strip()}"
                        success, new_content = self._apply_patch_block(target_path, patch_body)
                        if success and new_content:
                            edit_id = next_edit_id()
                            self.pending_edits[edit_id] = (target_path, new_content)
                            print(f"DEBUG: Inferred PATCH for selection L{selection_start_line}-L{selection_end_line} in {target_path}")
                            return f'<br><b><a href="edit:{edit_id}">Review Changes for {target_path}</a></b><br>'
                
                # Otherwise, treat as full-file replacement
                edit_id = next_edit_id()
                self.pending_edits[edit_id] = (target_path, full_text.strip())
                return f'<br><b><a href="edit:{edit_id}">Review Changes for {target_path}</a></b><br>'
            display_response = re.sub(code_block_pattern, replace_code_block, display_response, flags=re.DOTALL)
        elif code_blocks and not active_path and not has_explicit_edits:
            print("DEBUG: Received code-fenced full content but no active file to apply it to")

        # Parse for :::GENERATE_IMAGE::: blocks
        gen_pattern = r":::GENERATE_IMAGE:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        gen_matches = re.findall(gen_pattern, response, re.DOTALL)
        
        if gen_matches:
            for content in gen_matches:
                # Parse Prompt and Workflow from content
                prompt = ""
                workflow = None
                
                for line in content.split('\n'):
                    if line.lower().startswith("prompt:"):
                        prompt = line[7:].strip()
                    elif line.lower().startswith("workflow:"):
                        workflow = line[9:].strip()
                
                # If prompt wasn't found with prefix, assume whole content is prompt (fallback)
                if not prompt and content:
                     prompt = content.strip()

                if prompt:
                    print(f"DEBUG: Agent requested image generation. Prompt: {prompt}, Workflow: {workflow}")
                    self.open_image_studio()
                    self.image_gen.generate_from_agent(prompt, workflow)
                    
                    # Add a visual indicator to chat
                    display_response += f'<br><i>Generating image for: "{prompt}"...</i><br>'

        # Drop any edit: links that aren't associated with pending edits
        display_response = self._strip_unknown_edit_links(display_response)

        self.chat.append_message("AI", display_response)
        self.chat_history.append({"role": "assistant", "content": response})
        
        # Check if response appears incomplete and auto-continue if needed
        if not self.is_response_complete(response):
            print(f"DEBUG: Response appears incomplete, auto-continuing...")
            self.chat.show_thinking()
            self._continue_response()
        else:
            # Auto-save chat session after each exchange (only if complete)
            self.save_current_chat_session()
    
    def _continue_response(self):
        """Automatically continue the previous response."""
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )

        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            [],
            system_prompt,
            images=None,
            enabled_tools=self.project_manager.get_enabled_tools(),
        )
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()
        self._update_token_dashboard()

    def handle_continue(self):
        """Manually continue the conversation if the model stopped early."""
        if not self.chat_history:
            self.statusBar().showMessage("No conversation to continue", 2000)
            return

        self.chat.show_thinking()
        self._continue_response()
    
    def handle_new_chat(self):
        """Start a new chat, saving the current one to history first."""
        if self.chat_history:
            self.save_current_chat_session()
        
        # Clear chat history and UI
        self.chat_history = []
        self.chat.clear_messages()
        self.pending_edits = {}
        
        # Clear selection info
        if hasattr(self, '_last_selection_info'):
            self._last_selection_info = None
        
        self.statusBar().showMessage("Started new chat (previous chat saved to history)", 3000)
        rag_cap = None

        # Prefer provider-reported context window if available
        provider_window = None
        try:
            provider = self.get_llm_provider()
            model = self.settings.value("ollama_model", "llama3")
            if hasattr(provider, "get_model_context_length"):
                provider_window = provider.get_model_context_length(model)
        except Exception:
            provider_window = None

        if provider_window:
            context_window = provider_window
        elif self.rag_engine and getattr(self.rag_engine, "context_optimizer", None):
            optimizer = self.rag_engine.context_optimizer
            context_window = getattr(optimizer, "context_window", None)
            rag_cap = getattr(optimizer, "max_rag_tokens", None)

        tokens_text = f"{used_tokens}"
        if context_window:
            tokens_text = f"{used_tokens}/{context_window}"
        if rag_cap:
            tokens_text += f" (RAG cap {rag_cap})"

        cache_text = "--"
        if self.rag_engine and hasattr(self.rag_engine, "query_cache"):
            stats = self.rag_engine.query_cache.get_stats()
            hits = stats.get("hits", 0)
            misses = stats.get("misses", 0)
            total = hits + misses
            if total > 0:
                hit_rate = (hits / total) * 100
                cache_text = f"{hit_rate:.0f}% ({hits}/{total})"
            else:
                cache_text = "0% (0/0)"

        index_text = "idle"
        if self.index_progress_state:
            current, total, file_path = self.index_progress_state
            if total:
                index_text = f"{current}/{total}"
            else:
                index_text = "starting"
            if file_path:
                index_text += f" {os.path.basename(file_path)}"
        elif hasattr(self, 'index_worker') and self.index_worker is not None and self.index_worker.isRunning():
            index_text = "running"

        if hasattr(self, 'token_status'):
            self.token_status.setText(f"Tokens: {tokens_text} | Cache: {cache_text} | Index: {index_text}")
            # Build tooltip with breakdown if provided
            tooltip_lines = [f"Tokens: {tokens_text}", f"Cache: {cache_text}", f"Index: {index_text}"]
            if breakdown:
                tooltip_lines.append("Breakdown:")
                for label, value in breakdown.items():
                    tooltip_lines.append(f"  • {label}: {value}")
            self.token_status.setToolTip("\n".join(tooltip_lines))

    def _normalize_edit_path(self, raw_path: str, active_path: str | None) -> str:
        """Make path extraction more forgiving.
        - Strip quotes/backticks/angle brackets
        - Collapse redundant slashes
        - If path seems to be just a basename, try to resolve in project
        - Fallback to active file when path is empty
        """
        path = raw_path.strip()
        # Remove enclosing quotes/backticks/angle brackets
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        if (path.startswith('<') and path.endswith('>')) or (path.startswith('`') and path.endswith('`')):
            path = path[1:-1]
        # Normalize slashes but DO NOT strip leading '/'
        path = path.replace('\\', '/')
        # Remove a single leading './' if present
        if path.startswith('./'):
            path = path[2:]
        # Drop any accidental line markers or closers appended to the path
        if '\n' in path:
            path = path.splitlines()[0].strip()
        # If a line marker like " L12:" got attached, cut it off
        import re as _re
        path = _re.split(r"\s+L\d+:", path)[0].strip()
        # Remove stray block terminators if present
        for marker in (":::END:::", ":::END", ":::"):
            if marker in path:
                path = path.split(marker)[0].strip()
        # Collapse duplicate slashes (preserving a single leading '/')
        while '//' in path:
            path = path.replace('//', '/')
        path = path.strip()
        # If empty, fallback to active file if available
        if not path and active_path:
            return active_path
        # If it's an absolute path within project, convert to relative
        if self.project_manager.root_path and os.path.isabs(path):
            try:
                rel = os.path.relpath(path, self.project_manager.root_path)
                if not rel.startswith('..'):
                    path = rel
            except Exception:
                pass
        # If no directories (basename only), try to resolve in project
        if '/' not in path and self.project_manager.root_path:
            candidates = []
            for root, dirs, files in os.walk(self.project_manager.root_path):
                for f in files:
                    if f == path:
                        candidates.append(os.path.relpath(os.path.join(root, f), self.project_manager.root_path))
            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1 and active_path:
                # Prefer same directory as active file when possible
                active_dir = os.path.dirname(active_path)
                for c in candidates:
                    if os.path.dirname(c) == active_dir:
                        return c
                # Fallback to closest match by dir length
                candidates.sort(key=lambda p: len(os.path.dirname(p)))
                return candidates[0]
        # Fuzzy correction: if path not found, try close matches against project files
        if self.project_manager.root_path:
            target = path.split('/')[-1]
            index = []
            for root, dirs, files in os.walk(self.project_manager.root_path):
                for f in files:
                    index.append(os.path.relpath(os.path.join(root, f), self.project_manager.root_path))
            basenames = [os.path.basename(p) for p in index]
            matches = difflib.get_close_matches(target, basenames, n=1, cutoff=0.8)
            if matches:
                m = matches[0]
                # Pick the path whose basename equals the match
                for p in index:
                    if os.path.basename(p) == m:
                        return p
        return path

    def _apply_patch_block(self, file_path: str, patch_body: str) -> tuple[bool, str | None]:
        """Apply a PATCH block to a file's current content and return new content.

        PATCH lines format: L42: old => new
        Only single-line replacements are supported. If the old text is not found on the line,
        the entire line is replaced with the new text.
        Also supports range replacements: L10-L15: followed by either inline text or a fenced
        block (```...```) containing the replacement lines.
        """
        print(f"DEBUG: _apply_patch_block called for {file_path}, body length: {len(patch_body)}, first 100 chars: {patch_body[:100]!r}")
        
        try:
            current = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for patch {file_path}: {e}")
            return False, None

        if current is None:
            print(f"DEBUG: No content to patch for {file_path}")
            return False, None

        lines = current.split("\n")
        original_had_trailing_newline = current.endswith("\n")
        applied_any = False

        # Prefer range replacements over inline segments if any range marker exists
        has_range_marker = re.search(r"L\d+\s*-\s*L\d+:", patch_body) is not None
        # Support inline bodies without newlines: split using L\d+: markers
        inline_segments = [] if has_range_marker else list(
            re.finditer(r"L(\d+):\s*(.*?)(?=\s+L\d+:|\s+L\d+\s*-\s*L\d+:|$)", patch_body, flags=re.DOTALL)
        )
        if inline_segments:
            for seg in inline_segments:
                line_no = int(seg.group(1))
                new_text = seg.group(2).strip()
                if line_no < 1 or line_no > len(lines):
                    print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                    continue
                lines[line_no - 1] = new_text
                applied_any = True
        else:
            raw_lines = patch_body.splitlines()
            i = 0
            while i < len(raw_lines):
                raw = raw_lines[i]
                line = raw.strip()
                i += 1
                if not line:
                    continue
                # Range replacement: Lx-Ly:
                m_range = re.match(r"L(\d+)\s*-\s*L(\d+):\s*(.*)", line)
                if m_range:
                    start_no = int(m_range.group(1))
                    end_no = int(m_range.group(2))
                    trailing = m_range.group(3).strip()
                    repl_lines: list[str] = []
                    # If inline text present after ':', use it as the first replacement line,
                    # then continue capturing subsequent lines until a directive or end.
                    if trailing:
                        repl_lines.append(trailing)
                    # If next line starts a fenced block, capture until closing fence
                    if i < len(raw_lines) and raw_lines[i].strip().startswith("```"):
                        i += 1
                        while i < len(raw_lines) and not raw_lines[i].strip().startswith("```"):
                            repl_lines.append(raw_lines[i])
                            i += 1
                        # Skip closing fence if present
                        if i < len(raw_lines) and raw_lines[i].strip().startswith("```"):
                            i += 1
                    else:
                        # Otherwise, capture until next directive or end
                        while i < len(raw_lines):
                            peek = raw_lines[i]
                            if re.match(r"\s*L\d+:", peek) or re.match(r"\s*L\d+\s*-\s*L\d+:", peek):
                                break
                            repl_lines.append(peek)
                            i += 1
                    # Safety: strip any stray leading/trailing fences inside captured lines
                    if repl_lines:
                        if repl_lines[0].strip().startswith("```"):
                            repl_lines = repl_lines[1:]
                        if repl_lines and repl_lines[-1].strip().startswith("```"):
                            repl_lines = repl_lines[:-1]
                    # Apply replacement to target range
                    s_idx = max(1, start_no)
                    e_idx = min(len(lines), end_no)
                    if s_idx > e_idx:
                        print(f"DEBUG: Invalid range L{start_no}-L{end_no} for {file_path}")
                        continue
                    print(f"DEBUG: Applying PATCH range L{start_no}-L{end_no}: replacing {e_idx - s_idx + 1} lines with {len(repl_lines)} lines")
                    # Replace slice with repl_lines
                    before = lines[:s_idx - 1]
                    after = lines[e_idx:]
                    lines = before + repl_lines + after
                    applied_any = True
                    continue
                # With old=>new or old->new
                m = re.match(r"L(\d+):\s*(.+?)\s*(?:=>|->)\s*(.+)", line)
                if m:
                    line_no = int(m.group(1))
                    old_text = m.group(2)
                    new_text = m.group(3)
                    if line_no < 1 or line_no > len(lines):
                        print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                        continue
                    current_line = lines[line_no - 1]
                    if old_text in current_line:
                        lines[line_no - 1] = current_line.replace(old_text, new_text, 1)
                    else:
                        lines[line_no - 1] = new_text
                    applied_any = True
                    continue
                # Without old text: set entire line
                m2 = re.match(r"L(\d+):\s*(.+)", line)
                if m2:
                    line_no = int(m2.group(1))
                    new_text = m2.group(2).strip()
                    if line_no < 1 or line_no > len(lines):
                        print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                        continue
                    lines[line_no - 1] = new_text
                    applied_any = True
                else:
                    print(f"DEBUG: Skipping unrecognized patch line: {line}")

        if not applied_any:
            return False, None

        new_content = "\n".join(lines)
        if original_had_trailing_newline and not new_content.endswith("\n"):
            new_content += "\n"
        # Debug snippet around the patched range to verify correctness
        try:
            sample_start = max(0, s_idx - 5)
            sample_end = min(len(new_content.split("\n")), e_idx + 5)
            snippet = "\n".join(new_content.split("\n")[sample_start:sample_end])
            print(f"DEBUG: Patched snippet around L{s_idx}-L{e_idx}:\n{snippet}")
        except Exception:
            pass
        return True, new_content

    def _apply_unified_diff(self, file_path: str, diff_text: str) -> tuple[bool, str | None]:
        """Apply a unified diff (fenced ```diff block) to a file's content.

        Supports multiple hunks with lines starting by ' ', '+', '-'.
        Reconstructs new content based on original file and diff hunks.
        """
        try:
            original = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for unified diff {file_path}: {e}")
            return False, None

        if original is None:
            print(f"DEBUG: No content to patch for unified diff {file_path}")
            return False, None

        orig_lines = original.split("\n")
        new_lines: list[str] = []
        orig_idx = 0  # pointer into original lines

        lines = diff_text.splitlines()

        # Skip headers (---, +++)
        i = 0
        while i < len(lines) and (lines[i].startswith('--- ') or lines[i].startswith('+++ ')):
            i += 1

        hunk_header_re = re.compile(r"@@\s*-([0-9]+)(?:,([0-9]+))?\s*\+([0-9]+)(?:,([0-9]+))?\s*@@")
        any_applied = False

        while i < len(lines):
            if not lines[i].startswith('@@'):
                # Not a hunk header, skip
                i += 1
                continue

            m = hunk_header_re.match(lines[i])
            i += 1
            if not m:
                continue
            # Parse original and new ranges (we mainly use original start for copying unaffected parts)
            orig_start = int(m.group(1))
            # Copy unchanged chunk before this hunk
            target_orig_pos = max(0, orig_start - 1)
            if target_orig_pos > orig_idx:
                new_lines.extend(orig_lines[orig_idx:target_orig_pos])
                orig_idx = target_orig_pos

            # Process hunk body until next hunk header or end
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- ') and not lines[i].startswith('+++ '):
                line = lines[i]
                i += 1
                if not line:
                    # Preserve blank lines when context or addition
                    # Treat as context if no prefix
                    new_lines.append('')
                    continue
                prefix = line[0]
                content = line[1:] if len(line) > 1 else ''
                if prefix == ' ':
                    # Context line: copy from original when available, fallback to provided content
                    if orig_idx < len(orig_lines):
                        new_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                    else:
                        new_lines.append(content)
                elif prefix == '-':
                    # Removal: advance original pointer (skip)
                    if orig_idx < len(orig_lines):
                        orig_idx += 1
                elif prefix == '+':
                    # Addition: add content
                    new_lines.append(content)
                else:
                    # Unknown marker; default to context behavior
                    if orig_idx < len(orig_lines):
                        new_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                    else:
                        new_lines.append(line)
            any_applied = True

        # Append remaining original content after last hunk
        if orig_idx < len(orig_lines):
            new_lines.extend(orig_lines[orig_idx:])

        if not any_applied:
            return False, None

        new_content = "\n".join(new_lines)
        # Preserve trailing newline behavior
        if original.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
        return True, new_content

    def _merge_apply_within_range(self, old_text: str, new_text: str, start_line: int, end_line: int) -> str:
        """Merge changes by applying only the selected line range from new_text.

        Lines are 1-based. If range exceeds bounds, it is clamped.
        """
        old_lines = old_text.split("\n")
        new_lines = new_text.split("\n")
        n = max(len(old_lines), len(new_lines))
        # Clamp
        s = max(1, start_line)
        e = min(n, end_line)
        if s > e:
            return new_text  # nothing sensible, fallback to new_text
        # Build merged
        pre = old_lines[:s-1]
        mid = new_lines[s-1:e]
        post = old_lines[e:]
        merged = "\n".join(pre + mid + post)
        # Preserve trailing newline if old had one
        if old_text.endswith("\n") and not merged.endswith("\n"):
            merged += "\n"
        return merged

    def _find_unfenced_unified_diff_blocks(self, text: str) -> list[tuple[str, str]]:
        """Extract unfenced unified diff blocks and their target paths.

        Returns a list of tuples (diff_text, target_path).
        A block starts with '--- ' followed by '+++ ' and continues while lines
        start with '@@', '+', '-', ' ', or are blank, until the next '--- ' header
        or a non-diff line.
        """
        blocks: list[tuple[str, str]] = []
        lines = text.splitlines(keepends=True)
        i = 0

        def header_path(line: str) -> str:
            p = line[4:].strip() if len(line) > 4 else ''
            if p.startswith('a/') or p.startswith('b/'):
                p = p[2:]
            return p

        while i < len(lines):
            if not lines[i].startswith('--- '):
                i += 1
                continue
            start = i
            i += 1
            if i >= len(lines) or not lines[i].startswith('+++ '):
                # Not a valid diff header pair
                continue
            plus_header = lines[i]
            i += 1

            # Consume hunk bodies
            while i < len(lines):
                l = lines[i]
                if l.startswith('--- '):
                    # Next diff block header encountered
                    break
                if l.startswith('@@') or (l and l[0] in ('+', '-', ' ')) or l.strip() == '':
                    i += 1
                    continue
                # Non-diff line marks end of block
                break

            end = i
            diff_text = ''.join(lines[start:end])
            target_path = header_path(plus_header)
            blocks.append((diff_text, target_path))
        return blocks

    def _strip_unknown_edit_links(self, html: str) -> str:
        """Remove or unwrap any edit: links that are not backed by pending edits."""
        def _replace(match):
            edit_id = match.group(1)
            link_text = match.group(2) or ""
            if edit_id in self.pending_edits:
                return match.group(0)
            print(f"DEBUG: Dropping stale edit link: {edit_id}")
            return link_text

        pattern = r"<a\s+[^>]*href=[\"']edit:([^\"']+)[\"'][^>]*>(.*?)</a>"
        return re.sub(pattern, _replace, html, flags=re.IGNORECASE | re.DOTALL)

    def handle_chat_link(self, url):
        from PySide6.QtWidgets import QMessageBox
        
        if url.startswith("edit:"):
            edit_id = url.split(":")[1]
            if edit_id in self.pending_edits:
                path, new_content = self.pending_edits[edit_id]

                # Defensive fix: if new_content is just an edit link HTML, resolve the nested target
                if new_content and 'href="edit:' in new_content:
                    nested = re.search(r'href=["\']edit:([^"\']+)', new_content)
                    if nested:
                        nested_id = nested.group(1)
                        if nested_id in self.pending_edits:
                            print(f"DEBUG: Resolving nested edit link {nested_id} for {edit_id}")
                            path, new_content = self.pending_edits[nested_id]
                        else:
                            # Unwrap the link text to avoid showing raw HTML
                            text_only = re.sub(r"<[^>]+>", "", new_content)
                            new_content = text_only or new_content

                # Reject snippet-only content that shouldn't replace the whole file
                # If selection was sent and new_content is suspiciously short/incomplete, warn user
                old_content = self.project_manager.read_file(path)
                if old_content and hasattr(self, '_last_selection_info'):
                    sel_info = self._last_selection_info
                    if sel_info and sel_info.get('path') == path:
                        # Selection-based edit: check if new_content looks like a snippet
                        old_lines = old_content.count('\n') + 1
                        new_lines = new_content.count('\n') + 1
                        if new_lines < old_lines * 0.3:  # Less than 30% of original
                            reply = QMessageBox.warning(
                                self,
                                "Suspicious Edit",
                                f"This edit would replace {old_lines} lines with only {new_lines} lines.\n"
                                f"This may be a snippet instead of a full file.\n\n"
                                f"Continue anyway?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No
                            )
                            if reply != QMessageBox.Yes:
                                return
                
                # old_content already fetched above
                # Selection info for this file
                sel_range = None
                try:
                    if hasattr(self, '_last_selection_info') and self._last_selection_info:
                        info = self._last_selection_info
                        if info.get('path') == path:
                            sel_range = (info.get('start_line'), info.get('end_line'))
                except Exception:
                    sel_range = None

                # Default selection behavior from project settings
                default_apply_only = False
                try:
                    edit_settings = self.project_manager.get_editing_settings()
                    default_apply_only = bool(edit_settings.get('apply_only_selection_default', False))
                except Exception:
                    default_apply_only = False

                dialog = DiffDialog(
                    path,
                    old_content,
                    new_content,
                    self,
                    selection_range=sel_range,
                    default_apply_only_selection=default_apply_only,
                )
                if dialog.exec():
                    # Apply to buffer (Undoable)
                    # 1. Ensure file is open in editor
                    if path not in self.editor.open_files:
                        self.editor.open_file(path, old_content if old_content else "")
                    
                    # 2. Apply changes via undoable action
                    doc_widget = self.editor.open_files[path]
                    if sel_range and dialog.apply_only_selection():
                        s_line, e_line = sel_range
                        merged = self._merge_apply_within_range(old_content or "", new_content, s_line, e_line)
                        doc_widget.replace_content_undoable(merged)
                    else:
                        doc_widget.replace_content_undoable(new_content)
                    
                    self.statusBar().showMessage(f"Applied changes to buffer: {path}", 3000)
                    QMessageBox.information(self, "Success", f"Changes applied to {path}\n(Not saved to disk yet)")
                    
                    # RAG update skipped for now until saved? 
                    # Or should we update RAG with buffer content? 
                    # Probably better to wait for save, as RAG usually reads from disk or memory structure.
                    # If we really want to be correct, we should update RAG with memory content but that might start indexing unsaved stuff.
                    # Let's clean up RAG index on save.


    def update_save_button_state(self, modified):
        self.save_act.setEnabled(modified)

    def save_current_file(self):
        path, content = self.editor.get_current_file()
        if path and content is not None:
            try:
                if self.project_manager.save_file(path, content):
                    self.statusBar().showMessage(f"Saved {path}", 2000)
                    self.editor.mark_current_saved() # Reset modified state
                    # Update RAG index for this file
                    if self.rag_engine:
                        self.rag_engine.index_file(path, content)
                        self._update_token_dashboard()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to save {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file: {e}")
        else:
            # Maybe Save As?
            pass

    def open_project_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder_path:
            self.open_project(folder_path)

    def open_project(self, folder_path):
        if self.project_manager.open_project(folder_path):
            # Configure tool registry based on project settings
            try:
                enabled = self.project_manager.get_enabled_tools()
                if enabled is None:
                    register_default_tools()
                else:
                    register_by_names(enabled)
            except Exception:
                pass
            self.sidebar.set_root_path(folder_path)
            self.setWindowTitle(f"Inkwell AI - {folder_path}")
            self.stack.setCurrentWidget(self.main_interface)
            
            # Update Image Gen
            self.image_gen.set_project_path(folder_path)
            
            # Update Editor
            self.editor.set_project_path(folder_path)
            
            # Save to settings
            self.settings.setValue("last_project", folder_path)
            
            # Update Recent Projects
            recent = self.settings.value("recent_projects", [])
            if not isinstance(recent, list): recent = []
            
            if folder_path in recent:
                recent.remove(folder_path)
            recent.insert(0, folder_path)
            recent = recent[:5] # Keep top 5
            self.settings.setValue("recent_projects", recent)
            
            # Initialize RAG
            self.rag_engine = RAGEngine(folder_path)
            
            # Connect RAG engine to sidebar for status indicators
            if hasattr(self, 'sidebar'):
                self.sidebar.set_rag_engine(self.rag_engine)
            
            # Start indexer worker with cancel support
            self.index_worker = IndexWorker(self.rag_engine)
            self.index_worker.progress.connect(self.on_index_progress)
            self.index_worker.finished.connect(self.on_index_finished)
            self.index_worker.start()
            self.index_progress_state = (0, 0, "")
            self._update_token_dashboard()
            
            # Show progress bar
            self.indexing_progress = QProgressBar()
            self.indexing_progress.setTextVisible(True)
            self.indexing_progress.setFormat("Indexing: %p% (%v/%m)")
            self.statusBar().addWidget(self.indexing_progress)
            
            # Restore Tabs
            self.restore_project_state(folder_path)

    def save_project_state(self):
        if not self.project_manager.root_path:
            return
            
        project_path = self.project_manager.root_path
        
        # Use hash of path for key to avoid issues with special chars
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Get open files
        open_files = []
        for i in range(self.editor.tabs.count()):
            widget = self.editor.tabs.widget(i)
            if isinstance(widget, DocumentWidget) or isinstance(widget, ImageViewerWidget):
                path = widget.property("file_path")
                if path and os.path.exists(path) and not os.path.isdir(path):
                    open_files.append(path)
        
        # Check Image Studio
        # We need to check if any of the tabs is the image_gen widget
        image_studio_open = False
        for i in range(self.editor.tabs.count()):
            if self.editor.tabs.widget(i) == self.image_gen:
                image_studio_open = True
                break
        
        self.settings.setValue(f"state/{key}/open_files", open_files)
        self.settings.setValue(f"state/{key}/image_studio_open", image_studio_open)
        self.settings.sync() # Force write to disk

    def restore_project_state(self, project_path):
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
                        self.editor.open_file(path, None)
                    else:
                        content = self.project_manager.read_file(path)
                        if content is not None:
                            self.editor.open_file(path, content)
        
        # Restore Image Studio
        image_studio_open = self.settings.value(f"state/{key}/image_studio_open", False, type=bool)
        if image_studio_open:
            self.open_image_studio()
    
    def on_index_progress(self, current, total, file_path):
        """Update progress bar during indexing."""
        if hasattr(self, 'indexing_progress'):
            self.indexing_progress.setMaximum(total)
            self.indexing_progress.setValue(current)
            # Update sidebar to show indexed file status
            if self.rag_engine and hasattr(self, 'sidebar'):
                self.sidebar.update_file_status()
        self.index_progress_state = (current, total, file_path)
        self._update_token_dashboard()
    
    def on_index_finished(self):
        """Clean up after indexing completes."""
        if hasattr(self, 'indexing_progress'):
            self.statusBar().removeWidget(self.indexing_progress)
            self.indexing_progress.deleteLater()
            del self.indexing_progress
        # Final update of file statuses
        if hasattr(self, 'sidebar'):
            self.sidebar.update_file_status()
        self.index_progress_state = None
        self._update_token_dashboard()
        print("Indexing complete")

    def closeEvent(self, event):
        # Immediately cancel and terminate indexing worker
        if hasattr(self, 'index_worker') and self.index_worker is not None:
            try:
                self.index_worker.cancel()
                # Force terminate to avoid destructor issues
                if self.index_worker.isRunning():
                    self.index_worker.terminate()
            except Exception:
                pass
        # Force hard exit immediately bypassing all cleanup
        import os
        os._exit(0)

    def close_project(self):
        # Save state, cleanup, and clear last_project setting
        self._shutdown_project_session(clear_last_project=True)
        
        # Switch to Welcome
        self.stack.setCurrentWidget(self.welcome_widget)

    def _shutdown_project_session(self, clear_last_project=False):
        """Common logic for closing a project session."""
        # Save state before closing
        self.save_project_state()
        
        # Clear state
        self.project_manager.root_path = None
        self.sidebar.model.setRootPath("")
        self.setWindowTitle("Inkwell AI")
        
        # Close all tabs
        self.editor.tabs.clear()
        self.editor.open_files.clear()
        
        # Clear chat
        self.save_current_chat_session()  # Save before clearing
        self.chat.clear_chat()
        self.chat_history = []
        self._raw_ai_responses = []  # Clear raw responses tracking
        
        # Cancel RAG indexing worker immediately
        try:
            if hasattr(self, 'index_worker') and self.index_worker is not None:
                self.index_worker.cancel()
                self.index_worker = None
        except Exception:
            pass
        self.rag_engine = None
        
        # Clear last project setting if requested (e.g. user explicitly closed project)
        if clear_last_project:
            self.settings.setValue("last_project", "")
        
        # Update Welcome Screen
        self.update_welcome_screen()
        self._update_token_dashboard(0)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Re-register tools based on updated project settings
            try:
                enabled = self.project_manager.get_enabled_tools()
                if enabled is None:
                    register_default_tools()
                else:
                    register_by_names(enabled)
            except Exception:
                pass
            # After settings are saved, refresh model controls
            self.update_model_controls()

    def open_image_studio(self):
        # Check if already open
        index = self.editor.tabs.indexOf(self.image_gen)
        if index >= 0:
            self.editor.tabs.setCurrentIndex(index)
        else:
            self.editor.add_tab(self.image_gen, "Image Studio")

    def on_file_double_clicked(self, index):
        file_path = self.sidebar.model.filePath(index)
        if not self.sidebar.model.isDir(index):
            # Check if already open to avoid overwriting unsaved changes
            if file_path in self.editor.open_files:
                self.editor.open_file(file_path, None) # Content ignored if open
            else:
                # Check extension
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    self.editor.open_file(file_path, None)
                else:
                    content = self.project_manager.read_file(file_path)
                    if content is not None:
                        self.editor.open_file(file_path, content)

    def handle_batch_edit(self, path, content):
        instruction, ok = QInputDialog.getText(self, "Batch Edit", "Enter instruction for processing (e.g. 'Fix typos'):")
        if ok and instruction:
            # Create progress dialog
            self.progress = QProgressDialog("Processing chunks...", "Cancel", 0, 100, self)
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            provider = self.get_llm_provider()
            model = self.settings.value("ollama_model", "llama3")
            
            self.batch_worker = BatchWorker(provider, model, content, instruction)
            self.batch_worker.progress_updated.connect(self.on_batch_progress)
            self.batch_worker.finished.connect(lambda result: self.on_batch_finished(path, result))
            self.batch_worker.error_occurred.connect(self.on_batch_error)
            
            self.progress.canceled.connect(self.batch_worker.cancel)
            self.batch_worker.start()

    def on_batch_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.progress.setLabelText(f"Processing chunk {current} of {total}...")

    def on_batch_finished(self, path, result):
        self.progress.close()
        if result:
            # check files open
            if path in self.editor.open_files:
                doc_widget = self.editor.open_files[path]
                doc_widget.replace_content_undoable(result)
                QMessageBox.information(self, "Batch Complete", "Batch processing finished. Changes applied to buffer.")
            else:
                 QMessageBox.warning(self, "Error", "File closed during processing.")
    
    def on_batch_error(self, error):
        self.progress.close()
        QMessageBox.critical(self, "Batch Error", f"An error occurred: {error}")

    def on_tool_finished(self, result_text, extra_data):
        self.chat.remove_thinking()
        
        if extra_data: # Image Results
            # Fix AttributeError: use self.project_manager.root_path instead of self.project_path
            dialog = ImageSelectionDialog(extra_data, self.project_manager.root_path, self)
            if dialog.exec():
                saved_paths = dialog.get_saved_paths()
                if saved_paths:
                    msg_lines = []
                    for p in saved_paths:
                        name = os.path.basename(p)
                        self.chat.append_message("System", f"Image saved to: {name}")
                        msg_lines.append(f"User selected and saved image to {name}")
                    
                    # Notify agent but DO NOT continue chat loop automatically
                    # This prevents the AI from asking "Do you want another?" -> Tool -> Dialog loop
                    result_msg = "\n".join(msg_lines)
                    self.chat_history.append({"role": "user", "content": f"Tool Output: {result_msg}"})
                    self.chat.append_message("System", "Task completed.")
            else:
                 self.chat.append_message("System", "Image selection cancelled.")
                 self.chat_history.append({"role": "user", "content": "Tool Output: User cancelled image selection."})
        else:
            # Text result
            # We append it to chat as a system/tool message but don't show it to user necessarily? 
            # Or show it? Usually showing "Tool Output" is good.
            # self.chat.append_message("Tool", result_text[:500] + "..." if len(result_text) > 500 else result_text)
            
            # Feed back to LLM
            self.continue_chat_with_tool_result(result_text)

    def continue_chat_with_tool_result(self, result):
        # We need to send this result back to the LLM as if it were a system observation
        # or just context, to continue the generation.
        # Simple approach: append to history and trigger chat again.
        
        # We don't necessarily want this in the visible user chat history if it's long data.
        # But for simplicity, we treat it as a "System" message in the context.
        # self.chat_history is a list of dicts.
        
        # Context to LLM:
        prompt = f"Tool Output: {result}\n\nContinue responding to the user."
        
        # Trigger chat
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        
        # We need to construct context including this new info
        # We can append it to the last message contextually
        context = [] # We rely on history mostly
        
        # Add to history structure but maybe NOT UI if we want to keep it clean?
        # Let's add to UI for transparency
        if len(result) < 200:
            self.chat.append_message("Tool", result)
        else:
            self.chat.append_message("Tool", f"Result data ({len(result)} chars)...")

        # Manually append to self.chat_history so worker picks it up?
        # ChatWorker uses self.chat_history.
        # But ChatWorker expects {"role":, "content":}
        # Using "user" role often works better for forcing the model to pay attention to the new "data provided"
        self.chat_history.append({"role": "user", "content": f"Tool Output: {result}"})
        
        self.chat.show_thinking()
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )
        
        # Inject Project Structure
        if self.project_manager.root_path:
            structure = self.project_manager.get_project_structure()
            # We truncate if it's too huge, but assuming it fits for now
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            
        # Add active file context again? ChatWorker does it.
        
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            enabled_tools=self.project_manager.get_enabled_tools(),
        )
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

    def handle_save_chat(self, chat_content):
        """Save chat contents as a new file in the project."""
        if not self.project_manager.get_root_path():
            QMessageBox.warning(self, "No Project", "Please open a project first to save chat.")
            return
        
        root_path = self.project_manager.get_root_path()
        
        # Open folder selection dialog
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save chat",
            root_path,
            QFileDialog.ShowDirsOnly
        )
        
        if not folder:
            return
        
        # Verify folder is within project
        if not os.path.commonpath([folder, root_path]) == root_path:
            QMessageBox.warning(self, "Invalid Folder", "Please select a folder within the project.")
            return
        
        # Ask user for filename
        filename, ok = QInputDialog.getText(
            self, "Save Chat", "Enter filename (without extension):",
            text="chat_export"
        )
        
        if ok and filename:
            # Ensure it doesn't have extension already
            if '.' in filename:
                filename = filename.split('.')[0]
            
            # Use relative path from root for save_file
            relative_folder = os.path.relpath(folder, root_path)
            if relative_folder == '.':
                relative_path = f"{filename}.md"
            else:
                relative_path = os.path.join(relative_folder, f"{filename}.md")
            
            full_path = os.path.join(root_path, relative_path)
            
            # Check if file exists
            if os.path.exists(full_path):
                reply = QMessageBox.question(
                    self, "File Exists",
                    f"{filename}.md already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            try:
                self.project_manager.save_file(relative_path, chat_content)
                QMessageBox.information(self, "Success", f"Chat saved to {relative_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save chat: {e}")

    def handle_copy_chat_to_file(self, chat_content):
        """Copy chat contents to the currently open file."""
        if not self.editor.open_files:
            QMessageBox.warning(self, "No File Open", "Please open a file first to copy chat contents.")
            return
        
        current_path, current_content = self.editor.get_current_file()
        
        if not current_path:
            QMessageBox.warning(self, "No File Open", "Please open a file first to copy chat contents.")
            return
        
        # Ask user how to append
        reply = QMessageBox.question(
            self, "Append Chat",
            f"Append chat to {current_path}?\n\nYes = Append to end\nNo = Replace contents",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return
        
        if reply == QMessageBox.Yes:
            # Append to end
            new_content = (current_content if current_content else "") + "\n\n" + chat_content
        else:
            # Replace contents
            new_content = chat_content
        
        # Apply to buffer (Undoable)
        doc_widget = self.editor.open_files[current_path]
        doc_widget.replace_content_undoable(new_content)
        self.statusBar().showMessage(f"Chat copied to {current_path} (not saved yet)", 3000)
    
    def handle_message_deleted(self, msg_index):
        """Handle deletion of a chat message."""
        if msg_index < len(self.chat_history):
            # Remove from history
            del self.chat_history[msg_index]
            
            # Remove from chat display
            del self.chat.messages[msg_index]
            self.chat.rebuild_chat_display()
            
            self.statusBar().showMessage("Message deleted", 2000)
    
    def handle_message_edited(self, msg_index, new_content):
        """Handle editing of a chat message."""
        if msg_index < len(self.chat_history):
            # Update history with new content
            self.chat_history[msg_index]['content'] = new_content
            
            self.statusBar().showMessage("Message edited", 2000)
    
    def handle_regenerate(self):
        """Regenerate the last AI response."""
        if not self.chat_history:
            return
        
        # Find the last assistant message and last user message before it
        last_assistant_idx = None
        last_user_idx = None
        
        for i in range(len(self.chat_history) - 1, -1, -1):
            if self.chat_history[i]['role'] == 'assistant' and last_assistant_idx is None:
                last_assistant_idx = i
            elif self.chat_history[i]['role'] == 'user' and last_assistant_idx is not None and last_user_idx is None:
                last_user_idx = i
                break
        
        if last_assistant_idx is None:
            QMessageBox.information(self, "Nothing to Regenerate", "No AI response found to regenerate.")
            return
        
        # Remove the last assistant message
        del self.chat_history[last_assistant_idx]
        del self.chat.messages[last_assistant_idx]
        self.chat.rebuild_chat_display()
        
        # Show thinking indicator
        self.chat.show_thinking()
        
        # Resend the request
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        
        # Get RAG context if available
        context = None
        if self.rag_engine and last_user_idx is not None:
            query = self.chat_history[last_user_idx]['content']
            print(f"DEBUG: Querying RAG for: {query}")
            context = self.rag_engine.query(query)
            print(f"DEBUG: Retrieved {len(context) if context else 0} chunks")
        
        # Build system prompt
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are a helpful AI assistant.")
        )
        
        # Include project structure if enabled
        if self.project_manager.root_path and self.settings.value("include_project_structure", True, type=bool):
            structure = self.project_manager.get_project_structure()
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
        
        enabled_tools = self.project_manager.get_enabled_tools()
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=None,
            enabled_tools=enabled_tools,
        )
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()
    
    def save_current_chat_session(self):
        """Save the current chat session to history."""
        if not self.chat_history:
            self.statusBar().showMessage("No chat to save", 2000)
            return
        
        # Get title from first user message
        title = "Untitled Chat"
        for msg in self.chat_history:
            if msg['role'] == 'user':
                title = msg['content'][:50]  # First 50 chars
                if len(msg['content']) > 50:
                    title += "..."
                break
        
        # Create session object
        from datetime import datetime
        session = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'title': title,
            'messages': list(self.chat_history)  # Copy the list
        }
        
        # Add to history
        chat_sessions = self.settings.value("chat_history", [])
        if not isinstance(chat_sessions, list):
            chat_sessions = []
        
        chat_sessions.append(session)
        
        # Keep only last 50 sessions to avoid bloat
        if len(chat_sessions) > 50:
            chat_sessions = chat_sessions[-50:]
        
        self.settings.setValue("chat_history", chat_sessions)
        self.statusBar().showMessage("Chat saved to history", 2000)
    
    def open_chat_history(self):
        """Open the chat history dialog."""
        from gui.dialogs.chat_history_dialog import ChatHistoryDialog
        
        dialog = ChatHistoryDialog(self.settings, self)
        dialog.message_copy_requested.connect(self.copy_message_to_current_chat)
        dialog.exec()
    
    def copy_message_to_current_chat(self, message_content):
        """Copy a message from history to current chat and send it."""
        # Add to input field but don't send automatically
        self.chat.input_field.setPlainText(message_content)
        self.chat.input_field.setFocus()

    def export_debug_log(self):
        """Export current chat session and debug info to a timestamped file."""
        from datetime import datetime
        
        if not self.project_manager.root_path:
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return
        
        # Create .debug folder if needed
        debug_dir = os.path.join(self.project_manager.root_path, '.debug')
        os.makedirs(debug_dir, exist_ok=True)
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.join(debug_dir, f"session_{timestamp}.md")
        
        # Gather session info
        provider_name = self.settings.value("llm_provider", "Ollama")
        model_name = self.settings.value("ollama_model", "llama3")
        context_level = self.context_level
        
        # Build debug content
        content = f"""# Debug Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Session Info
- **Project:** {self.project_manager.root_path}
- **Provider:** {provider_name}
- **Model:** {model_name}
- **Context Level:** {context_level}
- **Token Usage:** {self._last_token_usage or '---'}

## Chat History (Rendered with Parsed Links)

"""
        
        # Add chat messages (rendered/processed version with links)
        for sender, text in self.chat.messages:
            content += f"\n### {sender}\n\n{text}\n\n---\n"
        
        # Add raw AI responses section (before parsing, shows original PATCH/UPDATE/diff blocks)
        if self._raw_ai_responses:
            content += "\n\n## Raw AI Responses (Before Parsing)\n\n"
            for idx, raw_resp in enumerate(self._raw_ai_responses, 1):
                content += f"\n### AI Response #{idx}\n\n```\n{raw_resp}\n```\n\n---\n"
        
        # Add pending edits info
        if self.pending_edits:
            content += "\n## Pending Edits\n\n"
            for edit_id, (path, new_content) in self.pending_edits.items():
                content += f"### {path} (ID: {edit_id})\n\n```\n{new_content[:500]}...\n```\n\n"
        
        # Write to file
        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.statusBar().showMessage(f"Debug log exported to {os.path.relpath(debug_file, self.project_manager.root_path)}", 3000)
            QMessageBox.information(self, "Export Complete", f"Debug log saved to:\n{os.path.relpath(debug_file, self.project_manager.root_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export debug log: {e}")

    def on_message_copied(self, kind: str):
        msg = "Copied to clipboard"
        if kind == "message":
            msg = "Message copied to clipboard"
        elif kind == "chat":
            msg = "Chat copied to clipboard"
        try:
            self.statusBar().showMessage(msg, 2000)
        except Exception:
            pass

    def on_file_renamed(self, old_path, new_path):
        """Update open editor tabs when a file is renamed from the sidebar."""
        try:
            self.editor.update_open_file_path(old_path, new_path)
            # Record operation and clear redo stack
            self.file_ops_history.append({"type": "rename", "old": old_path, "new": new_path})
            self.file_ops_redo.clear()
            self.statusBar().showMessage(f"Renamed: {os.path.basename(old_path)} → {os.path.basename(new_path)}", 3000)
        except Exception as e:
            # Non-critical; just log
            print(f"WARN: Failed to update editor after rename: {e}")

    def on_file_moved(self, old_path, new_path):
        """Update open editor tabs when a file is moved from the sidebar."""
        try:
            self.editor.update_open_file_path(old_path, new_path)
            # Record operation and clear redo stack
            self.file_ops_history.append({"type": "move", "old": old_path, "new": new_path})
            self.file_ops_redo.clear()
            self.statusBar().showMessage(f"Moved: {os.path.basename(old_path)} → {os.path.basename(new_path)}", 3000)
        except Exception as e:
            print(f"WARN: Failed to update editor after move: {e}")

    def _perform_move(self, src, dst):
        """Move/rename path with basic validation and conflict checking."""
        if not os.path.exists(src):
            QMessageBox.warning(self, "Not Found", f"Source does not exist: {src}")
            return False
        if os.path.exists(dst):
            reply = QMessageBox.question(
                self, "File Exists",
                f"{os.path.basename(dst)} exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return False
            # If overwriting a file with a folder or vice versa could be unsafe; rely on shutil semantics
        try:
            shutil.move(src, dst)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to move: {e}")
            return False

    def undo_file_change(self):
        """Undo the last file rename/move."""
        if not self.file_ops_history:
            self.statusBar().showMessage("No file changes to undo", 2000)
            return
        op = self.file_ops_history.pop()
        src = op["new"]
        dst = op["old"]
        if self._perform_move(src, dst):
            # Update editor tabs
            try:
                self.editor.update_open_file_path(src, dst)
            except Exception:
                pass
            # Push to redo stack
            self.file_ops_redo.append(op)
            self.statusBar().showMessage(f"Undid {op['type']}: {os.path.basename(src)} → {os.path.basename(dst)}", 3000)

    def redo_file_change(self):
        """Redo the last undone file rename/move."""
        if not self.file_ops_redo:
            self.statusBar().showMessage("No file changes to redo", 2000)
            return
        op = self.file_ops_redo.pop()
        src = op["old"]
        dst = op["new"]
        if self._perform_move(src, dst):
            # Update editor tabs
            try:
                self.editor.update_open_file_path(src, dst)
            except Exception:
                pass
            # Push back to history
            self.file_ops_history.append(op)
            self.statusBar().showMessage(f"Redid {op['type']}: {os.path.basename(src)} → {os.path.basename(dst)}", 3000)

    def _update_token_dashboard(self, token_usage=None, token_breakdown=None):
        """Stub for token usage tracking (to be implemented)."""
        # Store for potential future use
        if token_usage is not None:
            self._last_token_usage = token_usage
        # TODO: Display token usage in UI (statusbar, dedicated widget, etc.)
        pass


