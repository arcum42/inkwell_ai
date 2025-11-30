from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class WelcomeWidget(QWidget):
    open_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("Welcome to Inkwell AI")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #888;")
        layout.addWidget(title)
        
        subtitle = QLabel("Open a project to get started")
        subtitle.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 20px;")
        layout.addWidget(subtitle)
        
        open_btn = QPushButton("Open Project Folder")
        open_btn.setFixedSize(200, 40)
        open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(open_btn)
