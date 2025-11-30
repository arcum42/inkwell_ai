from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLineEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal

import markdown

class ChatBrowser(QTextBrowser):
    def setSource(self, url):
        if url.scheme() == "edit":
            return
        super().setSource(url)

class ChatWidget(QWidget):
    message_sent = Signal(str)
    link_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Chat History
        self.history = ChatBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setOpenLinks(False) # Disable auto-navigation for all links
        self.history.anchorClicked.connect(self.on_anchor_clicked)
        self.layout.addWidget(self.history)
        
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
