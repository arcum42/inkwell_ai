from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFileDialog, QMenuBar, QMenu, QStackedWidget, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QThread, Signal
from gui.sidebar import Sidebar
from core.project import ProjectManager
from core.llm_provider import OllamaProvider, LMStudioProvider
from PySide6.QtCore import QSettings

from gui.dialogs.settings_dialog import SettingsDialog
from gui.editor import EditorWidget
from gui.chat import ChatWidget
from gui.welcome import WelcomeWidget

from core.rag_engine import RAGEngine

from gui.dialogs.diff_dialog import DiffDialog
import re

class ChatWorker(QThread):
    response_received = Signal(str)
    
    def __init__(self, provider, messages, model, context=None, system_prompt=None):
        super().__init__()
        self.provider = provider
        self.messages = messages
        self.model = model
        self.context = context
        self.system_prompt = system_prompt

    def run(self):
        msgs_to_send = list(self.messages)
        
        # Inject System Prompt if present
        if self.system_prompt:
            # Check if system prompt already exists
            if msgs_to_send and msgs_to_send[0]['role'] == 'system':
                msgs_to_send[0]['content'] = self.system_prompt + "\n\n" + msgs_to_send[0]['content']
            else:
                msgs_to_send.insert(0, {"role": "system", "content": self.system_prompt})

        # Inject RAG Context
        if self.context:
            context_str = "\n\n".join(self.context)
            # Find the last user message
            for i in range(len(msgs_to_send)-1, -1, -1):
                if msgs_to_send[i]['role'] == 'user':
                    msgs_to_send[i]['content'] = f"Context from project files:\n{context_str}\n\nUser Question:\n{msgs_to_send[i]['content']}"
                    break
        
        response = self.provider.chat(msgs_to_send, model=self.model)
        self.response_received.emit(response)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inkwell AI")
        self.resize(1200, 800)
        
        self.project_manager = ProjectManager()
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.rag_engine = None
        self.pending_edits = {} # id -> (path, content)
        
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
        
        # Central Stack (Welcome vs Main Interface)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # 1. Welcome Screen
        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.open_clicked.connect(self.open_project_dialog)
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
        self.content_splitter.addWidget(self.editor)
        
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

    def open_project_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder_path:
            if self.project_manager.open_project(folder_path):
                self.sidebar.set_root_path(folder_path)
                self.setWindowTitle(f"Inkwell AI - {folder_path}")
                self.stack.setCurrentWidget(self.main_interface)
                
                # Initialize RAG
                self.rag_engine = RAGEngine(folder_path)
                # Run indexing in background (simple thread for now or just main thread if fast enough, 
                # but better to do it async. For MVP, main thread is risky if large project.
                # Let's do it in a thread.)
                self.index_thread = QThread()
                self.index_thread.run = self.rag_engine.index_project
                self.index_thread.start()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def on_file_double_clicked(self, index):
        file_path = self.sidebar.model.filePath(index)
        if not self.sidebar.model.isDir(index):
            # Check if already open to avoid overwriting unsaved changes
            if file_path in self.editor.open_files:
                self.editor.open_file(file_path, None) # Content ignored if open
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


