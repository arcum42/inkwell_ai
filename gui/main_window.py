from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFileDialog, QMenuBar, QMenu, QStackedWidget, QMessageBox, QStyle
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt, QThread, Signal
from gui.sidebar import Sidebar
from core.project import ProjectManager
from core.llm_provider import OllamaProvider, LMStudioProvider
from PySide6.QtCore import QSettings

from gui.dialogs.settings_dialog import SettingsDialog
from gui.editor import EditorWidget
from gui.chat import ChatWidget
from gui.welcome import WelcomeWidget
from gui.image_gen import ImageGenWidget

from core.rag_engine import RAGEngine

from gui.dialogs.diff_dialog import DiffDialog
import re
import os

# ... (ChatWorker class remains unchanged) ...

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inkwell AI")
        self.resize(1200, 800)
        
        self.project_manager = ProjectManager()
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.rag_engine = None
        self.pending_edits = {} # id -> (path, content)
        
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
        
        # View Menu
        view_menu = self.menu_bar.addMenu("View")
        image_studio_action = QAction("Image Studio", self)
        image_studio_action.triggered.connect(self.open_image_studio)
        view_menu.addAction(image_studio_action)
        
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
        self.main_splitter.addWidget(self.sidebar)
        
        # Content Splitter (Editor vs Chat)
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.content_splitter)
        
        # Editor Area
        self.editor = EditorWidget()
        self.editor.modification_changed.connect(self.update_save_button_state) # Connect signal
        self.content_splitter.addWidget(self.editor)
        
        # Image Studio
        self.image_gen = ImageGenWidget(self.settings)
        self.editor.add_tab(self.image_gen, "Image Studio")
        
        # Chat Interface
        self.chat = ChatWidget()
        self.chat.message_sent.connect(self.handle_chat_message)
        self.chat.link_clicked.connect(self.handle_chat_link)
        self.content_splitter.addWidget(self.chat)
        
        # Set initial sizes
        self.main_splitter.setSizes([240, 960])
        self.content_splitter.setSizes([700, 260])
        
        self.stack.addWidget(self.main_interface)
        
        # Start at Welcome
        self.stack.setCurrentWidget(self.welcome_widget)
        
        self.chat_history = [] # List of {"role": "user/assistant", "content": "..."}
        
        # Load Recent Projects for Welcome Screen
        self.update_welcome_screen()
        
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

    def get_llm_provider(self):
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            url = self.settings.value("ollama_url", "http://localhost:11434")
            return OllamaProvider(base_url=url)
        else:
            url = self.settings.value("lm_studio_url", "http://localhost:1234")
            return LMStudioProvider(base_url=url)

    def handle_chat_message(self, message):
        self.chat_history.append({"role": "user", "content": message})
        
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        
        # Retrieve context if RAG is active
        context = []
        if self.rag_engine:
            print(f"DEBUG: Querying RAG for: {message}")
            context = self.rag_engine.query(message)
            print(f"DEBUG: Retrieved {len(context)} chunks")
            
        # Add Active File Context
        active_path, active_content = self.editor.get_current_file()
        system_prompt = (
            "You are Inkwell AI, a creative writing assistant.\n"
            "You can read project files and propose edits.\n"
            "To propose an edit or create a file, output the content in this format:\n"
            ":::UPDATE path/to/file.md:::\n"
            "New Content Here...\n"
            ":::END:::\n"
            "To generate an image, use this format:\n"
            ":::GENERATE_IMAGE:::\n"
            "Prompt: A description of the image...\n"
            "Workflow: image_z_image_turbo (Optional, defaults to current)\n"
            ":::END:::\n"
            "IMPORTANT: You must close the block with :::END:::.\n"
            "If the file does not exist, it will be created.\n"
            "Example:\n"
            ":::UPDATE Characters/Pip.md:::\n"
            "# Pip\n"
            "Role: Healer\n"
            ":::END:::\n"
        )
        
        if active_path and active_content:
            system_prompt += f"\nCurrently Open File ({active_path}):\n{active_content}\n"
        
        # We need to pass the model to the worker/provider
        self.worker = ChatWorker(provider, self.chat_history, model, context, system_prompt)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

    def on_chat_response(self, response):
        print(f"DEBUG: Raw AI Response:\n{response}")
        
        # Parse for :::UPDATE...::: blocks
        # Improved regex to handle whitespace/newlines more flexibly
        # Accepts :::END:::, :::END, or just ::: as the closer
        pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        matches = re.findall(pattern, response, re.DOTALL)
        
        print(f"DEBUG: Found {len(matches)} edit blocks")
        
        display_response = response
        
        if matches:
            import uuid
            for path, content in matches:
                path = path.strip()
                content = content.strip()
                print(f"DEBUG: Parsed edit for {path}")
                
                edit_id = str(uuid.uuid4())
                self.pending_edits[edit_id] = (path, content)
                
            def replace_match(match):
                m_path = match.group(1).strip()
                m_content = match.group(2).strip()
                m_id = str(uuid.uuid4())
                self.pending_edits[m_id] = (m_path, m_content)
                return f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>'
            
            display_response = re.sub(pattern, replace_match, response, flags=re.DOTALL)

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

        self.chat.append_message("AI", display_response)
        self.chat_history.append({"role": "assistant", "content": response})

    def handle_chat_link(self, url):
        if url.startswith("edit:"):
            edit_id = url.split(":")[1]
            if edit_id in self.pending_edits:
                path, new_content = self.pending_edits[edit_id]
                
                # Get old content
                old_content = self.project_manager.read_file(path)
                
                dialog = DiffDialog(path, old_content, new_content, self)
                if dialog.exec():
                    # Apply
                    if self.project_manager.save_file(path, new_content):
                        self.statusBar().showMessage(f"Applied changes to {path}", 3000)
                        QMessageBox.information(self, "Success", f"Changes applied to {path}")
                        
                        # Refresh editor if open, or open it if new
                        if path in self.editor.open_files:
                            doc_widget = self.editor.open_files[path]
                            doc_widget.update_content(new_content)
                        else:
                            self.editor.open_file(path, new_content)
                            
                        # Update RAG
                        if self.rag_engine:
                            self.rag_engine.index_file(path, new_content)
                    else:
                        QMessageBox.warning(self, "Error", f"Failed to save {path}")

    def update_save_button_state(self, modified):
        self.save_act.setEnabled(modified)

    def save_current_file(self):
        path, content = self.editor.get_current_file()
        if path and content is not None:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.statusBar().showMessage(f"Saved {path}", 2000)
                self.editor.mark_current_saved() # Reset modified state
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
            self.index_thread = QThread()
            self.index_thread.run = self.rag_engine.index_project
            self.index_thread.start()

    def close_project(self):
        # Clear state
        self.project_manager.current_project_path = None
        self.sidebar.model.setRootPath("")
        self.setWindowTitle("Inkwell AI")
        
        # Close all tabs
        self.editor.tabs.clear()
        self.editor.open_files.clear()
        
        # Clear chat
        self.chat.history.clear()
        self.chat_history = []
        
        # Stop RAG
        self.rag_engine = None
        
        # Clear last project setting so it doesn't auto-open next time if user explicitly closed it
        self.settings.setValue("last_project", "")
        
        # Update Welcome Screen
        self.update_welcome_screen()
        
        # Switch to Welcome
        self.stack.setCurrentWidget(self.welcome_widget)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

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

    def save_current_file(self):
        path, content = self.editor.get_current_file()
        if path and content is not None:
            if self.project_manager.save_file(path, content):
                self.statusBar().showMessage(f"Saved {path}", 3000)
                # Update RAG index for this file
                if self.rag_engine:
                    self.rag_engine.index_file(path, content)
            else:
                QMessageBox.warning(self, "Error", f"Failed to save {path}")


