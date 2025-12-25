"""Dialog for managing custom dictionary."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt


class DictionaryDialog(QDialog):
    """Dialog for adding/removing words from custom dictionary."""
    
    def __init__(self, spell_checker, parent=None):
        super().__init__(parent)
        self.spell_checker = spell_checker
        self.setWindowTitle("Manage Custom Dictionary")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        label = QLabel("Words in your custom dictionary:")
        layout.addWidget(label)
        
        # List of words
        self.word_list = QListWidget()
        self._refresh_word_list()
        layout.addWidget(self.word_list)
        
        # Add word section
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Add word:"))
        self.new_word_input = QLineEdit()
        self.new_word_input.setPlaceholderText("Enter word and press Add")
        self.new_word_input.returnPressed.connect(self._add_word)
        add_layout.addWidget(self.new_word_input)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_word)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        button_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _refresh_word_list(self):
        """Refresh the word list display."""
        self.word_list.clear()
        words = self.spell_checker.get_custom_words()
        for word in words:
            self.word_list.addItem(word)
    
    def _add_word(self):
        """Add a new word to the dictionary."""
        word = self.new_word_input.text().strip()
        if not word:
            QMessageBox.warning(self, "Empty Word", "Please enter a word to add.")
            return
        
        if not word.isalpha():
            QMessageBox.warning(self, "Invalid Word", "Words must contain only letters.")
            return
        
        self.spell_checker.add_word_to_custom_dict(word)
        self.new_word_input.clear()
        self._refresh_word_list()
        QMessageBox.information(self, "Success", f"Added '{word}' to dictionary.")
    
    def _remove_selected(self):
        """Remove selected word from dictionary."""
        current_item = self.word_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a word to remove.")
            return
        
        word = current_item.text()
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove '{word}' from custom dictionary?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.spell_checker.remove_word_from_custom_dict(word)
            self._refresh_word_list()
    
    def _clear_all(self):
        """Clear all words from custom dictionary."""
        reply = QMessageBox.question(
            self, "Confirm Clear",
            "Clear all words from custom dictionary? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.spell_checker.custom_dict.clear()
            self._refresh_word_list()
            QMessageBox.information(self, "Cleared", "Custom dictionary cleared.")
