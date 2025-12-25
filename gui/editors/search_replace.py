"""Search and replace widget for text editors."""

import re
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QCheckBox, QLabel, QSpinBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QTextCursor, QTextDocument


class SearchReplaceWidget(QWidget):
    """Search and replace widget with regex support."""
    
    search_requested = Signal(str, bool)  # text, use_regex
    replace_requested = Signal(str, str, bool)  # find_text, replace_text, use_regex
    replace_all_requested = Signal(str, str, bool)  # find_text, replace_text, use_regex
    close_requested = Signal()
    
    def __init__(self, parent=None, editor=None):
        super().__init__(parent)
        self.editor = editor
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Search row
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Find:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search text...")
        self.search_input.returnPressed.connect(self.find_next)
        search_layout.addWidget(self.search_input)
        
        self.find_button = QPushButton("Find")
        self.find_button.clicked.connect(self.find_next)
        search_layout.addWidget(self.find_button)
        
        self.find_all_button = QPushButton("Find All")
        self.find_all_button.clicked.connect(self.find_all)
        search_layout.addWidget(self.find_all_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.on_close)
        search_layout.addWidget(self.close_button)
        
        layout.addLayout(search_layout)
        
        # Replace row
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(QLabel("Replace:"))
        
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement text...")
        self.replace_input.returnPressed.connect(self.replace_next)
        replace_layout.addWidget(self.replace_input)
        
        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_next)
        replace_layout.addWidget(self.replace_button)
        
        self.replace_all_button = QPushButton("Replace All")
        self.replace_all_button.clicked.connect(self.replace_all)
        replace_layout.addWidget(self.replace_all_button)
        
        layout.addLayout(replace_layout)
        
        # Options row
        options_layout = QHBoxLayout()
        
        self.regex_checkbox = QCheckBox("Use Regex")
        options_layout.addWidget(self.regex_checkbox)
        
        self.case_sensitive_checkbox = QCheckBox("Case Sensitive")
        options_layout.addWidget(self.case_sensitive_checkbox)
        
        self.match_count_label = QLabel("Matches: 0")
        options_layout.addWidget(self.match_count_label)
        
        options_layout.addStretch()
        
        layout.addLayout(options_layout)
        
        self.setMaximumHeight(120)
        
    def find_next(self):
        """Find next occurrence."""
        if not self.editor:
            return
        
        search_text = self.search_input.text()
        if not search_text:
            return
        
        use_regex = self.regex_checkbox.isChecked()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        
        self._find_in_editor(search_text, use_regex, case_sensitive, find_next=True)
        
    def find_all(self):
        """Find all occurrences."""
        if not self.editor:
            return
        
        search_text = self.search_input.text()
        if not search_text:
            return
        
        use_regex = self.regex_checkbox.isChecked()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        
        matches = self._find_all_in_editor(search_text, use_regex, case_sensitive)
        self.match_count_label.setText(f"Matches: {len(matches)}")
        
    def replace_next(self):
        """Replace next occurrence."""
        if not self.editor:
            return
        
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        
        if not search_text:
            return
        
        use_regex = self.regex_checkbox.isChecked()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        
        self._replace_in_editor(search_text, replace_text, use_regex, case_sensitive, replace_all=False)
        
    def replace_all(self):
        """Replace all occurrences."""
        if not self.editor:
            return
        
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        
        if not search_text:
            return
        
        use_regex = self.regex_checkbox.isChecked()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        
        count = self._replace_in_editor(search_text, replace_text, use_regex, case_sensitive, replace_all=True)
        self.match_count_label.setText(f"Replaced: {count}")
        
    def _find_in_editor(self, search_text, use_regex, case_sensitive, find_next=False):
        """Find text in editor and highlight it."""
        document = self.editor.document()
        cursor = self.editor.textCursor()
        
        if find_next:
            # Start search from current position
            cursor.movePosition(QTextCursor.NextCharacter)
        else:
            # Start from beginning
            cursor.movePosition(QTextCursor.Start)
        
        self.editor.setTextCursor(cursor)
        
        # Create search flags
        flags = QTextDocument.FindFlags()
        if case_sensitive:
            flags |= QTextDocument.FindCaseSensitively
        
        # If regex, we need to handle it differently
        if use_regex:
            self._find_with_regex(search_text, case_sensitive)
        else:
            cursor = document.find(search_text, cursor, flags)
            if not cursor.isNull():
                self.editor.setTextCursor(cursor)
                return True
        return False
    
    def _find_all_in_editor(self, search_text, use_regex, case_sensitive):
        """Find all occurrences and return positions."""
        text = self.editor.toPlainText()
        matches = []
        
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                for match in re.finditer(search_text, text, flags):
                    matches.append((match.start(), match.end(), match.group()))
            except re.error:
                return []
        else:
            if not case_sensitive:
                search_text_lower = search_text.lower()
                text_lower = text.lower()
                start = 0
                while True:
                    pos = text_lower.find(search_text_lower, start)
                    if pos == -1:
                        break
                    matches.append((pos, pos + len(search_text), search_text))
                    start = pos + 1
            else:
                start = 0
                while True:
                    pos = text.find(search_text, start)
                    if pos == -1:
                        break
                    matches.append((pos, pos + len(search_text), search_text))
                    start = pos + 1
        
        # Highlight all matches
        self._highlight_matches(matches)
        return matches
    
    def _highlight_matches(self, matches):
        """Highlight all matches in the editor."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.editor.setTextCursor(cursor)
        
        # Highlight first match if any
        if matches:
            cursor.setPosition(matches[0][0])
            cursor.setPosition(matches[0][1], QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
    
    def _find_with_regex(self, pattern, case_sensitive):
        """Find text using regex."""
        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        start_pos = cursor.position()
        
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            for match in re.finditer(pattern, text, flags):
                if match.start() >= start_pos:
                    cursor.setPosition(match.start())
                    cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                    self.editor.setTextCursor(cursor)
                    return True
        except re.error:
            pass
        
        return False
    
    def _replace_in_editor(self, search_text, replace_text, use_regex, case_sensitive, replace_all=False):
        """Replace text in editor."""
        document = self.editor.document()
        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        count = 0
        
        if replace_all:
            # Replace all occurrences
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                try:
                    new_text = re.sub(search_text, replace_text, text, flags=flags)
                    count = len(re.findall(search_text, text, flags=flags))
                    self.editor.setPlainText(new_text)
                except re.error:
                    pass
            else:
                if not case_sensitive:
                    # Case-insensitive replacement
                    new_text = re.sub(re.escape(search_text), replace_text, text, flags=re.IGNORECASE)
                    count = len(re.findall(re.escape(search_text), text, flags=re.IGNORECASE))
                else:
                    new_text = text.replace(search_text, replace_text)
                    count = text.count(search_text)
                
                self.editor.setPlainText(new_text)
        else:
            # Replace single occurrence
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            
            flags = QTextDocument.FindFlags()
            if case_sensitive:
                flags |= QTextDocument.FindCaseSensitively
            
            if use_regex:
                cursor = self.editor.textCursor()
                text_from_cursor = text[cursor.position():]
                
                try:
                    match = re.search(search_text, text_from_cursor, 
                                    0 if case_sensitive else re.IGNORECASE)
                    if match:
                        # Calculate absolute position
                        abs_start = cursor.position() + match.start()
                        abs_end = cursor.position() + match.end()
                        
                        # Replace the match
                        replacement = re.sub(search_text, replace_text, match.group(),
                                           flags=0 if case_sensitive else re.IGNORECASE)
                        
                        cursor.setPosition(abs_start)
                        cursor.setPosition(abs_end, QTextCursor.KeepAnchor)
                        cursor.insertText(replacement)
                        self.editor.setTextCursor(cursor)
                        count = 1
                except re.error:
                    pass
            else:
                cursor = document.find(search_text, cursor, flags)
                if not cursor.isNull():
                    cursor.insertText(replace_text)
                    self.editor.setTextCursor(cursor)
                    count = 1
        
        return count
    
    def on_close(self):
        """Close the search/replace widget."""
        self.close_requested.emit()
        self.hide()
    
    def set_editor(self, editor):
        """Set the editor to search in."""
        self.editor = editor
    
    def focus_search(self):
        """Focus the search input field."""
        self.search_input.setFocus()
        self.search_input.selectAll()
