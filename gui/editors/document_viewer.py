"""Markdown document editor with live preview."""

import os
import markdown
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QStackedWidget, QTextBrowser)
from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QUrl

from .code_editor import CodeEditor

class DocumentWidget(QWidget):
    """Widget for editing and previewing Markdown documents."""
    
    link_clicked = Signal(str)  # Emits path or URL when a link is clicked
    modification_changed = Signal(bool)  # Emits when modified state changes
    batch_edit_requested = Signal(str, str)  # Emits (path, content)

    def __init__(self, file_path, content, base_dir=None, spell_checker=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.base_dir = base_dir  # Project root for resolving relative paths
        self.spell_checker = spell_checker
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
        
        self.batch_btn = QPushButton("Batch Edit")
        self.batch_btn.setStatusTip("Process large file in chunks")
        self.batch_btn.clicked.connect(self.request_batch_edit)
        
        self.toolbar_layout.addWidget(self.edit_btn)
        self.toolbar_layout.addWidget(self.preview_btn)
        self.toolbar_layout.addWidget(self.batch_btn)
        self.toolbar_layout.addStretch()
        
        self.layout.addLayout(self.toolbar_layout)
        
        # Stack for Edit/Preview
        self.stack = QStackedWidget()
        
        # Editor with spell-checking
        self.editor = CodeEditor(spell_checker=spell_checker)
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)  # Reset initial state
        self.editor.document().modificationChanged.connect(self.on_modification_changed)
        
        self.stack.addWidget(self.editor)
        
        # Preview
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)  # Handle links manually
        self.preview.anchorClicked.connect(self.handle_link)
        
        # Set base directory for resolving relative paths in images
        if self.base_dir:
            self.preview.setSearchPaths([self.base_dir])
        
        self.stack.addWidget(self.preview)
        
        self.layout.addWidget(self.stack)

    def request_batch_edit(self):
        self.batch_edit_requested.emit(self.file_path, self.get_content())

    def on_modification_changed(self, changed):
        self.modification_changed.emit(changed)

    def is_modified(self):
        return self.editor.document().isModified()

    def set_modified(self, modified):
        self.editor.document().setModified(modified)

    def handle_link(self, url):
        # url is QUrl
        scheme = url.scheme()
        path = url.toString()
        
        # If it's a web URL, emit it (EditorWidget will handle opening in browser)
        if scheme in ['http', 'https']:
            self.link_clicked.emit(path)
            return
            
        # If it's a local file
        # Check if it's relative
        if not scheme or scheme == 'file':
            local_path = url.toLocalFile() if scheme == 'file' else path
            
            # If relative, resolve against current file's directory
            if not os.path.isabs(local_path):
                current_dir = os.path.dirname(self.file_path)
                local_path = os.path.normpath(os.path.join(current_dir, local_path))
                
            self.link_clicked.emit(local_path)

    def show_edit(self):
        self.edit_btn.setChecked(True)
        self.preview_btn.setChecked(False)
        self.stack.setCurrentIndex(0)

    def show_preview(self):
        self.edit_btn.setChecked(False)
        self.preview_btn.setChecked(True)
        
        # Render Markdown
        text = self.editor.toPlainText()
        html_content = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        
        # Add Styling
        style = """
        <style>
            html, body {
                font-family: sans-serif;
                color: #ffffff !important;
                background: #111;
            }
            p, li, ul, ol, table, td, th, blockquote { color: #ffffff !important; }
            a { color: #7cc7ff; }
            code {
                background-color: #1f1f24;
                color: #ffffff !important;
                padding: 2px 4px;
                border-radius: 4px;
            }
            pre {
                background-color: #1f1f24;
                color: #ffffff !important;
                padding: 10px;
                border-radius: 4px;
                border: 1px solid #2e2e32;
                overflow: auto;
            }
            pre code {
                background: transparent;
                color: #ffffff !important;
            }
            blockquote {
                border-left: 4px solid #555;
                margin: 0;
                padding-left: 10px;
                color: #e6e6e6;
            }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #2e2e32; padding: 8px; text-align: left; color: #ffffff; }
            th { background-color: #1a1a1f; color: #ffffff; }
        </style>
        """
        
        full_html = f"{style}\n{html_content}"
        self.preview.setHtml(full_html)
        
        self.stack.setCurrentIndex(1)

    def update_content(self, content):
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        if self.preview_btn.isChecked():
            self.show_preview()

    def replace_content_undoable(self, content):
        """Replaces content in an undoable way (select all -> paste)."""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.insertText(content)
        # This will trigger modificationChanged automatically via signal
        if self.preview_btn.isChecked():
            self.show_preview()

    def get_content(self):
        return self.editor.toPlainText()
