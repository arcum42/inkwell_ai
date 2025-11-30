from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QDialogButtonBox, QSplitter, QWidget, QPushButton, QStackedWidget, QTextBrowser
from PySide6.QtCore import Qt
import markdown

class DiffPanel(QWidget):
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with Toggle
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch()
        
        self.toggle_btn = QPushButton("Show Preview")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self.toggle_view)
        header_layout.addWidget(self.toggle_btn)
        
        self.layout.addLayout(header_layout)
        
        # Stack
        self.stack = QStackedWidget()
        
        # Text View
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(content if content else "")
        self.stack.addWidget(self.text_edit)
        
        # Preview View
        self.preview = QTextBrowser()
        if content:
            html = markdown.markdown(content, extensions=['fenced_code', 'tables'])
            self.preview.setHtml(html)
        self.stack.addWidget(self.preview)
        
        self.layout.addWidget(self.stack)

    def toggle_view(self):
        if self.toggle_btn.isChecked():
            self.toggle_btn.setText("Show Text")
            self.stack.setCurrentIndex(1)
        else:
            self.toggle_btn.setText("Show Preview")
            self.stack.setCurrentIndex(0)

class DiffDialog(QDialog):
    def __init__(self, file_path, old_content, new_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Review Changes - {file_path}")
        self.resize(1200, 700)
        
        layout = QVBoxLayout(self)
        
        # Info
        if old_content is None:
            layout.addWidget(QLabel(f"Creating NEW file: {file_path}"))
        else:
            layout.addWidget(QLabel(f"Modifying file: {file_path}"))
            
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Old Panel
        self.old_panel = DiffPanel("Current Content", old_content)
        splitter.addWidget(self.old_panel)
        
        # New Panel
        self.new_panel = DiffPanel("Proposed Content", new_content)
        splitter.addWidget(self.new_panel)
        
        layout.addWidget(splitter)
        
        # Buttons
        # Use Ok button but rename it to "Apply Changes" so it emits the accepted signal correctly
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Apply Changes")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
