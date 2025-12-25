"""Plain text editor with Markdown formatting and spell-checking capabilities."""

import re
from PySide6.QtWidgets import QPlainTextEdit, QMenu
from PySide6.QtGui import QTextCursor, QTextFormat, QColor, QTextCharFormat
from PySide6.QtCore import Qt, QTimer

from .dialogs import LinkDialog


class CodeEditor(QPlainTextEdit):
    """Plain text editor with Markdown formatting and spell-checking."""
    
    def __init__(self, parent=None, spell_checker=None):
        super().__init__(parent)
        self.spell_checker = spell_checker
        self.misspelled_words = set()
        self.spell_check_timer = QTimer()
        self.spell_check_timer.setSingleShot(True)
        self.spell_check_timer.timeout.connect(self._do_spell_check)
        
        # Connect text changes for spell-checking
        if self.spell_checker:
            self.textChanged.connect(self._on_text_changed)
    
    def set_spell_checker(self, spell_checker):
        """Set spell-checker instance.
        
        Args:
            spell_checker: InkwellSpellChecker instance
        """
        self.spell_checker = spell_checker
        if spell_checker:
            self.textChanged.connect(self._on_text_changed)
    
    def _on_text_changed(self):
        """Handle text changes - schedule spell-check with debounce."""
        if self.spell_checker and self.spell_checker.is_enabled():
            self.spell_check_timer.stop()
            self.spell_check_timer.start(500)  # Debounce: check after 500ms of inactivity
    
    def _do_spell_check(self):
        """Perform spell-check on entire document."""
        if not self.spell_checker or not self.spell_checker.is_enabled():
            return
        
        text = self.toPlainText()
        misspelled = self.spell_checker.check_text(text)
        self._highlight_misspelled(misspelled)
    
    def _highlight_misspelled(self, misspelled_words: set):
        """Highlight misspelled words with red underline.
        
        Args:
            misspelled_words: Set of misspelled words
        """
        self.misspelled_words = misspelled_words
        # Preserve document modified state so spell-check formatting doesn't re-flag the tab
        doc = self.document()
        was_modified = doc.isModified()
        
        # Create format for misspelled words (red wavy underline)
        misspelled_format = QTextCharFormat()
        misspelled_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        misspelled_format.setUnderlineColor(QColor(255, 0, 0))  # Red
        
        # Apply formatting to all misspelled words
        cursor = QTextCursor(doc)
        
        while not cursor.atEnd():
            cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
            word = cursor.selectedText().lower()
            
            # Extract alphabetic part of word
            alpha_word = re.sub(r'[^a-z]', '', word)
            
            if alpha_word in misspelled_words:
                cursor.setCharFormat(misspelled_format)
            else:
                # Reset format
                cursor.setCharFormat(QTextCharFormat())
            
            cursor.movePosition(QTextCursor.NextWord)
        
        # Restore original modified flag
        if doc.isModified() != was_modified:
            doc.setModified(was_modified)
    
    def contextMenuEvent(self, event):
        """Handle right-click context menu with spell-check suggestions."""
        cursor = self.cursorForPosition(event.pos())
        
        # Find the word at cursor
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText().lower()
        alpha_word = re.sub(r'[^a-z]', '', word)
        
        menu = QMenu(self)
        
        # Add spell-check suggestions if word is misspelled
        if self.spell_checker and alpha_word in self.misspelled_words:
            suggestions = self.spell_checker.get_corrections(alpha_word, max_suggestions=5)
            
            if suggestions:
                for suggestion in suggestions:
                    action = menu.addAction(suggestion)
                    action.triggered.connect(lambda checked, s=suggestion, c=cursor: self._replace_word(c, s))
                menu.addSeparator()
            
            # Add to custom dictionary option
            add_action = menu.addAction(f"Add '{word}' to Dictionary")
            add_action.triggered.connect(lambda: self._add_to_dictionary(word))
            menu.addSeparator()
        
        # Add standard formatting options
        menu.addAction("Cut").triggered.connect(self.cut)
        menu.addAction("Copy").triggered.connect(self.copy)
        menu.addAction("Paste").triggered.connect(self.paste)
        
        menu.exec(event.globalPos())
    
    def _replace_word(self, cursor, replacement):
        """Replace word with suggestion.
        
        Args:
            cursor: QTextCursor positioned at word
            replacement: Replacement text
        """
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(replacement)
        self.setTextCursor(cursor)
    
    def _add_to_dictionary(self, word: str):
        """Add word to custom dictionary.
        
        Args:
            word: Word to add
        """
        if self.spell_checker:
            self.spell_checker.add_word_to_custom_dict(word)
            # Remove from misspelled and rehighlight
            self._do_spell_check()
    
    def wrap_selection(self, prefix, suffix=""):
        """Wraps the selected text with prefix/suffix, or inserts both at cursor."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"{prefix}{text}{suffix}")
        else:
            cursor.insertText(f"{prefix}{suffix}")
            # Move cursor back to insert point
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(suffix))
            self.setTextCursor(cursor)
    
    def format_bold(self):
        self.wrap_selection("**", "**")
        
    def format_italic(self):
        self.wrap_selection("*", "*")
        
    def format_code(self):
        self.wrap_selection("`", "`")
        
    def format_code_block(self):
        self.wrap_selection("```\n", "\n```")
        
    def format_quote(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            lines = text.split('\u2029')  # Qt paragraph separator
            quoted = "\n".join([f"> {line}" for line in lines])
            cursor.insertText(quoted)
        else:
            cursor.insertText("> ")
    
    def format_h1(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("# ")
        
    def format_h2(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("## ")
        
    def format_h3(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("### ")
    
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

