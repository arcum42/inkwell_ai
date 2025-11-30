from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class WelcomeWidget(QWidget):
    open_clicked = Signal()
    recent_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("Welcome to Inkwell AI")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #888;")
        self.layout.addWidget(title)
        
        subtitle = QLabel("Open a project to get started")
        subtitle.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 20px;")
        self.layout.addWidget(subtitle)
        
        open_btn = QPushButton("Open Project Folder")
        open_btn.setFixedSize(200, 40)
        open_btn.clicked.connect(self.open_clicked.emit)
        self.layout.addWidget(open_btn)
        
        self.layout.addSpacing(20)
        
        self.recent_label = QLabel("Recent Projects:")
        self.recent_label.setStyleSheet("font-weight: bold; margin-top: 20px;")
        self.recent_label.hide()
        self.layout.addWidget(self.recent_label)
        
        self.recent_layout = QVBoxLayout()
        self.layout.addLayout(self.recent_layout)

    def set_recent_projects(self, projects):
        # Clear existing
        while self.recent_layout.count():
            child = self.recent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not projects:
            self.recent_label.hide()
            return
            
        self.recent_label.show()
        for path in projects:
            btn = QPushButton(path)
            btn.setStyleSheet("text-align: left; padding: 5px; border: none; color: #2196F3;")
            btn.setCursor(Qt.PointingHandCursor)
            # Use default arg to capture path in lambda
            btn.clicked.connect(lambda checked=False, p=path: self.recent_clicked.emit(p))
            self.recent_layout.addWidget(btn)
