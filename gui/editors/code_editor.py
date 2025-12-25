"""Plain text editor with Markdown formatting capabilities."""

from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextCursor

from .dialogs import LinkDialog

class CodeEditor(QPlainTextEdit):
    """Plain text editor with Markdown formatting methods."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
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
