"""Dialog components for editor package."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

class LinkDialog(QDialog):
    """Dialog for inserting Markdown links."""
    def __init__(self, parent=None, text="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Insert Link")
        self.layout = QVBoxLayout(self)
        
        # Text field
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Text:"))
        self.text_edit = QLineEdit(text)
        text_layout.addWidget(self.text_edit)
        self.layout.addLayout(text_layout)
        
        # URL field
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_edit = QLineEdit(url)
        url_layout.addWidget(self.url_edit)
        self.layout.addLayout(url_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        self.layout.addLayout(button_layout)

    def get_data(self):
        return self.text_edit.text(), self.url_edit.text()
