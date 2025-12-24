from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QPlainTextEdit, QMessageBox, QStackedWidget, QTextBrowser, QHBoxLayout, QPushButton, QToolBar, QScrollArea, QLabel, QDialog, QLineEdit, QDialogButtonBox
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPixmap, QTextCursor, QDesktopServices
from PySide6.QtCore import Qt, Signal
import markdown
import os

class LinkDialog(QDialog):
    def __init__(self, parent=None, text="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Insert Link")
        self.layout = QVBoxLayout(self)
        
        self.text_input = QLineEdit(text)
        self.text_input.setPlaceholderText("Link Text")
        self.layout.addWidget(QLabel("Text:"))
        self.layout.addWidget(self.text_input)
        
        self.url_input = QLineEdit(url)
        self.url_input.setPlaceholderText("URL")
        self.layout.addWidget(QLabel("URL:"))
        self.layout.addWidget(self.url_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
    def get_data(self):
        return self.text_input.text(), self.url_input.text()

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12pt;")

    # ... (toggle_formatting methods remain the same) ...

    def insert_link(self):
        cursor = self.textCursor()
        selected_text = ""
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            
        dialog = LinkDialog(self, text=selected_text)
        if dialog.exec():
            text, url = dialog.get_data()
            if text and url:
                cursor.insertText(f"[{text}]({url})")

    def toggle_formatting(self, symbol, placeholder="text"):
        cursor = self.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            text = cursor.selectedText()
            
            # Check if already formatted (naive check)
            if text.startswith(symbol) and text.endswith(symbol):
                cursor.insertText(text[len(symbol):-len(symbol)])
                return

            # Adjust for whitespace
            # We need to find how much whitespace is at start and end
            # Note: selectedText() uses U+2029 for paragraph separators, need to be careful
            
            # Calculate leading whitespace
            leading_ws = 0
            for char in text:
                if char.isspace():
                    leading_ws += 1
                else:
                    break
            
            # Calculate trailing whitespace
            trailing_ws = 0
            for char in reversed(text):
                if char.isspace():
                    trailing_ws += 1
                else:
                    break
            
            # If all whitespace, just wrap it? Or do nothing? 
            # User said "place start after any whitespace and end before".
            # If "   ", start after 3, end before 3 -> empty range.
            if leading_ws + trailing_ws >= len(text) and len(text) > 0:
                # All whitespace, maybe just insert around it? Or skip?
                # Let's just wrap the whole thing if it's all whitespace to avoid errors, 
                # or maybe just don't trim.
                # But usually we want to format the word inside.
                # Let's assume we format nothing if it's all whitespace.
                pass 
            else:
                # Adjust cursor to exclude whitespace
                cursor.setPosition(start + leading_ws)
                cursor.setPosition(end - trailing_ws, QTextCursor.KeepAnchor)
                
                trimmed_text = cursor.selectedText()
                cursor.insertText(f"{symbol}{trimmed_text}{symbol}")
                
                # Restore selection (optional, but nice)
                # cursor.setPosition(start + leading_ws)
                # cursor.setPosition(start + leading_ws + len(trimmed_text) + 2*len(symbol), QTextCursor.KeepAnchor)
                # self.setTextCursor(cursor)
        else:
            # Insert placeholder
            cursor.insertText(f"{symbol}{placeholder}{symbol}")
            # Select the placeholder
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(placeholder) + len(symbol))
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(placeholder))
            self.setTextCursor(cursor)

    def toggle_block_formatting(self, symbol):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        text = cursor.selectedText()
        
        if text.startswith(symbol):
            cursor.insertText(text[len(symbol):])
        else:
            cursor.insertText(symbol + text)

    def format_code_block(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"```\n{text}\n```")
        else:
            cursor.insertText("```\ncode\n```")
            # Move cursor inside
            cursor.movePosition(QTextCursor.Up)
            self.setTextCursor(cursor)

    def format_quote(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            self.toggle_block_formatting("> ")
            return

        # Multi-line quote
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfBlock)
        start_pos = cursor.position()
        
        cursor.setPosition(end)
        # If we are at the start of a block and not at the very beginning (meaning we selected a full line including newline),
        # we probably don't want to quote the *next* empty line.
        if cursor.atBlockStart() and cursor.position() > start:
            cursor.movePosition(QTextCursor.PreviousBlock)
            cursor.movePosition(QTextCursor.EndOfBlock)
        end_pos = cursor.position()
        
        # Select all involved blocks
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        text = cursor.selectedText()
        
        # Naive implementation: split by paragraph separator and prepend >
        # Note: Qt uses unicode paragraph separator \u2029 for selectedText() of multiple blocks sometimes?
        # Or just \n if we use toPlainText()? selectedText returns \u2029.
        
        lines = text.split('\u2029')
        # Check if all lines are already quoted
        all_quoted = all(line.startswith("> ") for line in lines)
        
        new_lines = []
        for line in lines:
            if all_quoted:
                new_lines.append(line[2:])
            else:
                new_lines.append(f"> {line}")
        
        new_text = "\u2029".join(new_lines)
        cursor.insertText(new_text)

    def format_bold(self):
        self.toggle_formatting("**", "bold text")

    def format_italic(self):
        self.toggle_formatting("*", "italic text")

    def format_code(self):
        # Kept for API compatibility, but maybe unused by toolbar now
        self.toggle_formatting("`", "code")

    def format_h1(self):
        self.toggle_block_formatting("# ")

    def format_h2(self):
        self.toggle_block_formatting("## ")

    def format_h3(self):
        self.toggle_block_formatting("### ")
        
    def insert_link(self):
        cursor = self.textCursor()
        selected_text = ""
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            
        dialog = LinkDialog(self, text=selected_text)
        if dialog.exec():
            text, url = dialog.get_data()
            # If user didn't provide text but provided URL, use URL as text
            if not text and url:
                text = url
            
            if text and url:
                cursor.insertText(f"[{text}]({url})")
            
    def insert_image(self):
        self.textCursor().insertText("![Alt text](image_url)")

class DocumentWidget(QWidget):
    link_clicked = Signal(str) # Emits path or URL when a link is clicked
    modification_changed = Signal(bool) # Emits when modified state changes

    def __init__(self, file_path, content, base_dir=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.base_dir = base_dir  # Project root for resolving relative paths
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
        self.editor.document().setModified(False) # Reset initial state
        self.editor.document().modificationChanged.connect(self.on_modification_changed)
        
        self.stack.addWidget(self.editor)
        
        # Preview
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False) # Handle links manually
        self.preview.anchorClicked.connect(self.handle_link)
        
        # Set base directory for resolving relative paths in images
        if self.base_dir:
            self.preview.setSearchPaths([self.base_dir])
        
        self.stack.addWidget(self.preview)
        
        self.layout.addWidget(self.stack)

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
            body { font-family: sans-serif; }
            code { background-color: #f0f0f0; padding: 2px 4px; border-radius: 4px; }
            pre { background-color: #f0f0f0; padding: 10px; border-radius: 4px; }
            blockquote { 
                border-left: 4px solid #ccc; 
                margin: 0; 
                padding-left: 10px; 
                color: #666; 
            }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
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

class ImageViewerWidget(QWidget):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        scroll.setWidget(self.image_label)
        
        self.load_image()
        
    def load_image(self):
        pixmap = QPixmap(self.file_path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("Failed to load image")

class EditorWidget(QWidget):
    modification_changed = Signal(bool) # Emits when current tab's modification state changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.layout.addWidget(self.tabs)
        
        self.open_files = {} # path -> widget
        self.project_path = None  # Track project root for relative path resolution

    def set_project_path(self, path):
        """Set the project root path for resolving relative paths in markdown."""
        self.project_path = path

    def open_file(self, path, content):
        if path in self.open_files:
            self.tabs.setCurrentWidget(self.open_files[path])
            return
        
        # Check extension
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            widget = ImageViewerWidget(path)
        else:
            widget = DocumentWidget(path, content if content is not None else "", self.project_path)
            widget.link_clicked.connect(self.handle_link_click)
            widget.modification_changed.connect(lambda m: self.on_doc_modified(widget, m))
            
        widget.setProperty("file_path", path)
        
        # Add to tabs
        index = self.tabs.addTab(widget, os.path.basename(path))
        self.tabs.setCurrentIndex(index)
        self.open_files[path] = widget

    def on_doc_modified(self, widget, modified):
        index = self.tabs.indexOf(widget)
        if index != -1:
            title = os.path.basename(widget.property("file_path"))
            if modified:
                title += " •"
            self.tabs.setTabText(index, title)
            
            # If this is the current tab, emit signal
            if widget == self.tabs.currentWidget():
                self.modification_changed.emit(modified)

    def on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, DocumentWidget):
            self.modification_changed.emit(widget.is_modified())
        else:
            self.modification_changed.emit(False)

    def is_current_modified(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, DocumentWidget):
            return widget.is_modified()
        return False

    def mark_current_saved(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, DocumentWidget):
            widget.set_modified(False)

    def handle_link_click(self, path):
        # Check if it's a URL
        if path.startswith("http://") or path.startswith("https://"):
            QDesktopServices.openUrl(path)
            return
            
        # Otherwise assume it's a file path
        if os.path.exists(path):
            # Read content and open
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.open_file(path, content)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open linked file: {e}")
        else:
            QMessageBox.warning(self, "Error", f"File not found: {path}")

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        path = widget.property("file_path")
        if path in self.open_files:
            del self.open_files[path]
        self.tabs.removeTab(index)

    def get_current_document(self):
        return self.tabs.currentWidget()
        
    def get_current_editor(self):
        doc = self.get_current_document()
        if isinstance(doc, DocumentWidget):
            return doc.editor
        return None

    def undo(self):
        current = self.get_current_editor()
        if current: current.undo()

    def redo(self):
        current = self.get_current_editor()
        if current: current.redo()

    def cut(self):
        current = self.get_current_editor()
        if current: current.cut()

    def copy(self):
        current = self.get_current_editor()
        if current: current.copy()

    def paste(self):
        current = self.get_current_editor()
        if current: current.paste()

    def paste(self):
        current = self.get_current_editor()
        if current: current.paste()

    # Formatting Delegates
    def format_bold(self):
        current = self.get_current_editor()
        if current: current.format_bold()

    def format_italic(self):
        current = self.get_current_editor()
        if current: current.format_italic()

    def format_code(self):
        current = self.get_current_editor()
        if current: current.format_code()

    def format_code_block(self):
        current = self.get_current_editor()
        if current: current.format_code_block()

    def format_quote(self):
        current = self.get_current_editor()
        if current: current.format_quote()

    def format_h1(self):
        current = self.get_current_editor()
        if current: current.format_h1()

    def format_h2(self):
        current = self.get_current_editor()
        if current: current.format_h2()

    def format_h3(self):
        current = self.get_current_editor()
        if current: current.format_h3()

    def insert_link(self):
        current = self.get_current_editor()
        if current: current.insert_link()

    def insert_image(self):
        current = self.get_current_editor()
        if current: current.insert_image()

    def add_tab(self, widget, title):
        self.tabs.addTab(widget, title)
        self.tabs.setCurrentWidget(widget)

    def get_current_file(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, DocumentWidget):
            return current_widget.property("file_path"), current_widget.get_content()
        return None, None
