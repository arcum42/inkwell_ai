"""Dialog for searching imageboard tools directly from the UI."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


# Mapping of display names to API parameter values for different imageboards
SORT_OPTIONS = {
    "DERPIBOORU": {
        "Score (Highest)": "score",
        "Newest": "first_seen_at",
        "Trending": "wilson_score",
    },
    "TANTABUS": {
        "Score (Highest)": "score",
        "Newest": "first_seen_at",
        "Trending": "wilson_score",
    },
    "E621": {
        "Score (Highest)": "score",
        "Newest": "id",
        "Trending": "note_count",
    },
}


class ImageboardSearchDialog(QDialog):
    """Dialog for searching imageboard tools (Derpibooru, Tantabus, E621)."""
    
    def __init__(self, tool_name: str, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.query = None
        self.sort = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle(f"Search {self.tool_name}")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Tags input
        tags_label = QLabel("Search Tags:")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Enter tags separated by commas (e.g., fluttershy, cute)")
        layout.addWidget(tags_label)
        layout.addWidget(self.tags_input)
        
        # Sort options
        sort_label = QLabel("Sort By:")
        self.sort_combo = QComboBox()
        
        # Get sort options for this tool
        sort_options = SORT_OPTIONS.get(self.tool_name, {
            "Score (Highest)": "score",
            "Newest": "first_seen_at",
        })
        
        display_names = list(sort_options.keys())
        self.sort_combo.addItems(display_names)
        self.sort_combo.setCurrentText(display_names[0])
        
        # Store the mapping for later
        self._sort_mapping = sort_options
        
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()
        layout.addLayout(sort_layout)
        
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
        if not self.tags_input.text().strip():
            QMessageBox.warning(self, "Empty Search", "Please enter at least one tag to search for.")
            return
        
        self.query = self.tags_input.text().strip()
        
        # Map display name to API value
        display_name = self.sort_combo.currentText()
        self.sort = self._sort_mapping.get(display_name, "score")
        self.accept()
    
    def get_query(self) -> str:
        """Return the search query."""
        return self.query or ""
    
    def get_sort(self) -> str:
        """Return the sort preference (API parameter value)."""
        return self.sort or "score"
