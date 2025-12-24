from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFileDialog, QMenuBar, QMenu, QStackedWidget, QMessageBox, QStyle, QInputDialog, QProgressDialog
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

from gui.workers import ChatWorker, BatchWorker, ToolWorker, IndexWorker
from gui.dialogs.image_dialog import ImageSelectionDialog
import shutil


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
        self.content_splitter.addWidget(self.chat)

        # Initialize model header with current settings
        try:
            provider = self.get_llm_provider()
            model = self.settings.value("ollama_model", "llama3")
            is_vision = provider.is_vision_model(model)
            self.chat.update_model_info(model, is_vision)
        except Exception:
            # Fail silently; header will update on first message or settings change
            pass
        
        # Set initial sizes
        self.main_splitter.setSizes([240, 960])
        self.content_splitter.setSizes([700, 260])
        
        self.stack.addWidget(self.main_interface)
        
        # Start at Welcome
        self.stack.setCurrentWidget(self.welcome_widget)
        
        self.chat_history = [] # List of {"role": "user/assistant", "content": "..."}
        # File operations history for undo/redo
        self.file_ops_history = []  # list of {"type": "rename"|"move", "old": str, "new": str}
        self.file_ops_redo = []     # stack for redo
        
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

        # Update chat header to reflect current model and capability
        try:
            self.chat.update_model_info(model, provider.is_vision_model(model))
        except Exception:
            pass
        
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
        
        self.chat.show_thinking()
        
        system_prompt = self.settings.value("system_prompt", "You are a helpful coding assistant.")
        
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
            
        # Add active file context
        if active_path:
             system_prompt += f"\n\nActive File: {active_path}\nContent:\n{active_content}"
             
        self.worker = ChatWorker(provider, self.chat_history, model, context, system_prompt, images=attached_images)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

    def on_chat_response(self, response):
        # Remove thinking indicator
        self.chat.remove_thinking()
        
        print(f"DEBUG: Raw AI Response:\n{response}")
        
        # Parse for :::TOOL:...::: blocks
        tool_pattern = r":::TOOL:(.*?):(.*?):::"
        tool_match = re.search(tool_pattern, response)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            query = tool_match.group(2).strip()
            self.chat.append_message("System", f"<i>Running tool: {tool_name}...</i>")
            self.chat.show_thinking() # thinking again for tool
            
            self.tool_worker = ToolWorker(tool_name, query)
            self.tool_worker.finished.connect(self.on_tool_finished)
            self.tool_worker.start()
            return # Stop processing other things if tool runs (it effectively continues the conversation)

        # Parse for :::UPDATE...::: blocks
        # Improved regex to handle whitespace/newlines more flexibly
        # Accepts :::END:::, :::END, or just ::: as the closer
        pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        matches = re.findall(pattern, response, re.DOTALL)
        
        print(f"DEBUG: Found {len(matches)} edit blocks")
        
        display_response = response
        
        if matches:
            import uuid
            # Define non-text file extensions that shouldn't be edited
            non_text_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
                                  '.mp4', '.avi', '.mov', '.mp3', '.wav', 
                                  '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}
            
            for path, content in matches:
                path = path.strip()
                content = content.strip().replace('\\n', '\n')
                
                # Check if this is a non-text file
                file_ext = os.path.splitext(path)[1].lower()
                if file_ext in non_text_extensions:
                    # Convert to .txt file instead
                    original_path = path
                    path = os.path.splitext(path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text file edit from {original_path} to {path}")
                
                print(f"DEBUG: Parsed edit for {path}")
                
                edit_id = str(uuid.uuid4())
                self.pending_edits[edit_id] = (path, content)
                
            def replace_match(match):
                m_path = match.group(1).strip()
                m_content = match.group(2).strip().replace('\\n', '\n')
                
                # Check if this is a non-text file and convert to .txt
                file_ext = os.path.splitext(m_path)[1].lower()
                if file_ext in non_text_extensions:
                    original_path = m_path
                    m_path = os.path.splitext(m_path)[0] + '.txt'
                    print(f"DEBUG: Converting non-text file edit from {original_path} to {m_path} (in display)")
                
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
                    # Apply to buffer (Undoable)
                    # 1. Ensure file is open in editor
                    if path not in self.editor.open_files:
                        self.editor.open_file(path, old_content if old_content else "")
                    
                    # 2. Apply changes via undoable action
                    doc_widget = self.editor.open_files[path]
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
            # Start indexer worker with cancel support
            self.index_worker = IndexWorker(self.rag_engine)
            self.index_worker.start()
            
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
        self.chat.history.clear()
        self.chat_history = []
        
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

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # After settings are saved, refresh chat header
            try:
                provider = self.get_llm_provider()
                model = self.settings.value("ollama_model", "llama3")
                is_vision = provider.is_vision_model(model)
                self.chat.update_model_info(model, is_vision)
            except Exception:
                pass

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
        system_prompt = self.settings.value("system_prompt", "You are a helpful coding assistant.")
        
        # Inject Project Structure
        if self.project_manager.root_path:
            structure = self.project_manager.get_project_structure()
            # We truncate if it's too huge, but assuming it fits for now
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            
        # Add active file context again? ChatWorker does it.
        
        self.worker = ChatWorker(provider, self.chat_history, model, context, system_prompt)
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


