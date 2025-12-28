"""Dialog for image search tool."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox
)


class ImageSearchDialog(QDialog):
    """Dialog for searching images directly from the UI."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle("Search for Images")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Search input
        label = QLabel("Image Search Terms:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter what you want to find (e.g., cat, sunset, landscape)")
        layout.addWidget(label)
        layout.addWidget(self.search_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        search_btn = QPushButton("Search")
        cancel_btn = QPushButton("Cancel")
        search_btn.clicked.connect(self.on_search)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(search_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
    def on_search(self):
        """Handle search button click."""
        if not self.search_input.text().strip():
            QMessageBox.warning(self, "Empty Search", "Please enter search terms.")
            return
        
        self.query = self.search_input.text().strip()
        self.accept()
    
    def get_query(self) -> str:
        """Return the search query."""
        return self.query or ""
