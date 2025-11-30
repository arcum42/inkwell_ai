from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QPlainTextEdit, QMessageBox, QStackedWidget, QTextBrowser, QHBoxLayout, QPushButton, QToolBar
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtCore import Qt, Signal
import markdown

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12pt;")

class DocumentWidget(QWidget):
    def __init__(self, file_path, content, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar for switching modes
        self.toolbar_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setChecked(True)
        self.edit_btn.clicked.connect(self.show_edit)
        
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setCheckable(True)
        self.preview_btn.clicked.connect(self.show_preview)
        
        self.toolbar_layout.addWidget(self.edit_btn)
        self.toolbar_layout.addWidget(self.preview_btn)
        self.toolbar_layout.addStretch()
        
        self.layout.addLayout(self.toolbar_layout)
        
        # Stack for Edit/Preview
        self.stack = QStackedWidget()
        
        # Editor
        self.editor = CodeEditor()
        self.editor.setPlainText(content)
        self.stack.addWidget(self.editor)
        
        # Preview
        self.preview = QTextBrowser()
        self.stack.addWidget(self.preview)
        
        self.layout.addWidget(self.stack)

    def show_edit(self):
        self.edit_btn.setChecked(True)
        self.preview_btn.setChecked(False)
        self.stack.setCurrentIndex(0)

    def show_preview(self):
        self.edit_btn.setChecked(False)
        self.preview_btn.setChecked(True)
        
        # Render Markdown
        text = self.editor.toPlainText()
        html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        self.preview.setHtml(html)
        
        self.stack.setCurrentIndex(1)

    def update_content(self, content):
        self.editor.setPlainText(content)
        if self.preview_btn.isChecked():
            self.show_preview()

    def get_content(self):
        return self.editor.toPlainText()

class EditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.layout.addWidget(self.tabs)
        
        self.open_files = {} # path -> DocumentWidget

    def open_file(self, path, content):
        if path in self.open_files:
            self.tabs.setCurrentWidget(self.open_files[path])
            return
        
        doc_widget = DocumentWidget(path, content)
        doc_widget.setProperty("file_path", path)
        
        # Add to tabs
        index = self.tabs.addTab(doc_widget, path.split("/")[-1])
        self.tabs.setCurrentIndex(index)
        self.open_files[path] = doc_widget

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        path = widget.property("file_path")
        if path in self.open_files:
            del self.open_files[path]
        self.tabs.removeTab(index)

    def get_current_document(self):
        return self.tabs.currentWidget()

    def undo(self):
        doc = self.get_current_document()
        if doc: doc.editor.undo()

    def redo(self):
        doc = self.get_current_document()
        if doc: doc.editor.redo()

    def cut(self):
        doc = self.get_current_document()
        if doc: doc.editor.cut()

    def copy(self):
        doc = self.get_current_document()
        if doc: doc.editor.copy()

    def paste(self):
        doc = self.get_current_document()
        if doc: doc.editor.paste()

    def get_current_file(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            return current_widget.property("file_path"), current_widget.get_content()
        return None, None
