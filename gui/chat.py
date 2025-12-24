from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLineEdit, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6 import QtGui # Need QtGui for cursors in thinking logic
from PySide6.QtGui import QClipboard

import markdown

class ChatBrowser(QTextBrowser):
    def setSource(self, url):
        if url.scheme() == "edit":
            return
        super().setSource(url)

class ChatWidget(QWidget):
    message_sent = Signal(str)
    link_clicked = Signal(str)
    save_chat_requested = Signal(str)  # Emits formatted chat content
    copy_to_file_requested = Signal(str)  # Emits formatted chat content

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Model Indicator
        self.model_label = QLabel("Model: Loading...")
        self.model_label.setStyleSheet("color: #666; font-size: 10pt; font-style: italic; margin-bottom: 2px;")
        self.model_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.model_label)
        
        # Chat History
        self.history = ChatBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setOpenLinks(False) # Disable auto-navigation for all links
        self.history.anchorClicked.connect(self.on_anchor_clicked)
        self.layout.addWidget(self.history)
        
        # Chat Control Buttons
        button_layout = QHBoxLayout()
        
        save_chat_btn = QPushButton("Save Chat as File")
        save_chat_btn.clicked.connect(self.on_save_chat)
        button_layout.addWidget(save_chat_btn)
        
        copy_to_file_btn = QPushButton("Copy Chat to Open File")
        copy_to_file_btn.clicked.connect(self.on_copy_to_file)
        button_layout.addWidget(copy_to_file_btn)
        
        copy_to_clipboard_btn = QPushButton("Copy Chat to Clipboard")
        copy_to_clipboard_btn.clicked.connect(self.on_copy_to_clipboard)
        button_layout.addWidget(copy_to_clipboard_btn)
        
        self.layout.addLayout(button_layout)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        
        self.layout.addLayout(input_layout)

    def update_model_info(self, model_name, is_vision):
        vision_icon = "👁️" if is_vision else ""
        self.model_label.setText(f"Model: {model_name} {vision_icon}")

    def on_anchor_clicked(self, url):
        self.link_clicked.emit(url.toString())

    def send_message(self):
        text = self.input_field.text().strip()
        if text:
            self.append_message("User", text)
            self.message_sent.emit(text)
            self.input_field.clear()

    def append_message(self, sender, text):
        # Convert Markdown to HTML
        html_content = markdown.markdown(text)
        
        # Format the message block
        sender_color = "#4CAF50" if sender == "User" else "#2196F3"
        formatted_msg = f"""
        <div style="margin-bottom: 10px;">
            <b style="color: {sender_color};">{sender}:</b>
            <div style="margin-top: 5px;">{html_content}</div>
        </div>
        <hr>
        """
        self.history.append(formatted_msg)

    def show_thinking(self):
        """Appends a temporary 'Thinking...' message."""
        # We use a special ID or marker we can find/remove? 
        # Actually, since we append, it's at the end. We can just remember we added it.
        # But QTextBrowser appends HTML. 
        # A simple way is to append a block.
        self.history.append('<div style="color: gray; font-style: italic;">AI is thinking...</div>')
        self.history.moveCursor(QtGui.QTextCursor.End) # Ensure we scroll to bottom

    def remove_thinking(self):
        """Removes the last block (assumed to be the 'Thinking...' message)."""
        # This is tricky with pure HTML append.
        # We can use the cursor to select the last block and delete it.
        cursor = self.history.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        
        # Select the last block/line. 
        # "AI is thinking..." might be its own block.
        cursor.select(QtGui.QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Also remove the newline/block separator if needed
        cursor.deletePreviousChar()

    def get_chat_as_text(self):
        """Returns the formatted chat history as plain text."""
        return self.history.toPlainText()
    
    def get_chat_as_markdown(self):
        """Returns the formatted chat history with minimal markdown formatting."""
        # Extract from the HTML history - this is the original messages stored
        # Since we convert to HTML when appending, we need a different approach
        # We'll use the plain text and format it nicely
        return self.history.toPlainText()

    def on_save_chat(self):
        """Emit signal to save chat as a new file."""
        content = self.get_chat_as_text()
        self.save_chat_requested.emit(content)

    def on_copy_to_file(self):
        """Emit signal to copy chat to the currently open file."""
        content = self.get_chat_as_text()
        self.copy_to_file_requested.emit(content)

    def on_copy_to_clipboard(self):
        """Copy chat contents to clipboard."""
        content = self.get_chat_as_text()
        clipboard = QtGui.QGuiApplication.clipboard()
        clipboard.setText(content, QClipboard.Clipboard)

