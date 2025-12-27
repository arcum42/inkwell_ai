"""Main editor widget coordinating tabs and documents."""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut

from .document_viewer import DocumentWidget
from .image_viewer import ImageViewerWidget
from .search_replace import SearchReplaceWidget

class EditorWidget(QWidget):
    """Tab-based editor widget managing multiple documents and images."""
    
    modification_changed = Signal(bool)  # Emits when current tab's modification state changes
    batch_edit_requested = Signal(str, str)  # path, content
    tab_closed = Signal()  # Emits when a tab is closed

    def __init__(self, parent=None, spell_checker=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.spell_checker = spell_checker
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.layout.addWidget(self.tabs)
        
        # Add search/replace widget
        self.search_replace = SearchReplaceWidget(self)
        self.search_replace.hide()
        self.search_replace.close_requested.connect(self.hide_search)
        self.layout.addWidget(self.search_replace)
        
        # Zoom shortcuts
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        self.open_files = {}  # path -> widget
        self.project_path = None  # Track project root for relative path resolution
    
    def zoom_in(self):
        """Increase font size in current editor."""
        widget = self.tabs.currentWidget()
        if isinstance(widget, DocumentWidget):
            widget.zoom_in()
    
    def zoom_out(self):
        """Decrease font size in current editor."""
        widget = self.tabs.currentWidget()
        if isinstance(widget, DocumentWidget):
            widget.zoom_out()
    
    def apply_font_settings(self):
        """Apply font settings to all open documents."""
        for widget in self.open_files.values():
            if isinstance(widget, DocumentWidget):
                widget.apply_font_settings()

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
            widget = DocumentWidget(path, content if content is not None else "", self.project_path, 
                                   spell_checker=self.spell_checker)
            widget.link_clicked.connect(self.handle_link_click)
            widget.modification_changed.connect(lambda m: self.on_doc_modified(widget, m))
            widget.batch_edit_requested.connect(self.propagate_batch_edit)
            
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
        # Emit signal so MainWindow can update project state
        self.tab_closed.emit()

    def get_current_document(self):
        return self.tabs.currentWidget()
        
    def get_current_editor(self):
        doc = self.get_current_document()
        if isinstance(doc, DocumentWidget):
            return doc.editor
        return None

    def undo(self):
        current = self.get_current_editor()
        if current:
            current.undo()

    def redo(self):
        current = self.get_current_editor()
        if current:
            current.redo()

    def cut(self):
        current = self.get_current_editor()
        if current:
            current.cut()

    def copy(self):
        current = self.get_current_editor()
        if current:
            current.copy()

    def paste(self):
        current = self.get_current_editor()
        if current:
            current.paste()

    # Formatting Delegates
    def format_bold(self):
        current = self.get_current_editor()
        if current:
            current.format_bold()

    def format_italic(self):
        current = self.get_current_editor()
        if current:
            current.format_italic()

    def format_code(self):
        current = self.get_current_editor()
        if current:
            current.format_code()

    def format_code_block(self):
        current = self.get_current_editor()
        if current:
            current.format_code_block()

    def format_quote(self):
        current = self.get_current_editor()
        if current:
            current.format_quote()

    def format_h1(self):
        current = self.get_current_editor()
        if current:
            current.format_h1()

    def format_h2(self):
        current = self.get_current_editor()
        if current:
            current.format_h2()

    def format_h3(self):
        current = self.get_current_editor()
        if current:
            current.format_h3()

    def insert_link(self):
        current = self.get_current_editor()
        if current:
            current.insert_link()

    def insert_image(self):
        current = self.get_current_editor()
        if current:
            current.insert_image()

    def add_tab(self, widget, title):
        self.tabs.addTab(widget, title)
        self.tabs.setCurrentWidget(widget)

    def get_current_file(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, DocumentWidget):
            return current_widget.property("file_path"), current_widget.get_content()
        return None, None

    def propagate_batch_edit(self, path, content):
        self.batch_edit_requested.emit(path, content)

    def update_open_file_path(self, old_path, new_path):
        """Update tabs and internal mapping when a file or folder is renamed/moved.
        - If a single file matches `old_path`, retarget it.
        - If a folder moved/renamed, retarget all open files under that folder.
        """
        sep = os.sep
        # Handle folder moves: update all open files under old_path
        updated = False
        for path in list(self.open_files.keys()):
            if path == old_path or path.startswith(old_path + sep):
                widget = self.open_files.pop(path)
                # Compute new path
                if path == old_path:
                    new_widget_path = new_path
                else:
                    suffix = path[len(old_path):]
                    new_widget_path = new_path + suffix
                # Update widget property
                widget.setProperty("file_path", new_widget_path)
                # Update tab title
                index = self.tabs.indexOf(widget)
                if index != -1:
                    title = os.path.basename(new_widget_path)
                    if isinstance(widget, DocumentWidget) and widget.is_modified():
                        title += " •"
                    self.tabs.setTabText(index, title)
                # Reinsert with new key
                self.open_files[new_widget_path] = widget
                updated = True
        return updated

    def show_search(self):
        """Show and focus the search/replace widget."""
        editor = self.get_current_editor()
        if editor:
            self.search_replace.set_editor(editor)
            self.search_replace.show()
            self.search_replace.focus_search()

    def hide_search(self):
        """Hide the search/replace widget."""
        self.search_replace.hide()
