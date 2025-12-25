from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QListWidget, QTextBrowser, QSplitter, QMessageBox, QLabel)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import json
from datetime import datetime


class ChatHistoryDialog(QDialog):
    """Dialog to browse and manage chat history."""
    
    message_copy_requested = Signal(str)  # Emits message content to copy
    
    def __init__(self, settings, parent=None, project_path=None):
        super().__init__(parent)
        self.settings = settings
        self.project_path = project_path
        self.setWindowTitle("Chat History")
        self.resize(900, 600)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel("Browse previous chat sessions. Click a message to copy it to current chat.")
        info_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Splitter for sessions list and chat display
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Sessions list
        left_panel = QVBoxLayout()
        left_widget = QListWidget()
        
        sessions_label = QLabel("Saved Chat Sessions:")
        sessions_label.setStyleSheet("font-weight: bold;")
        left_panel.addWidget(sessions_label)
        
        self.sessions_list = QListWidget()
        self.sessions_list.currentRowChanged.connect(self.on_session_selected)
        left_panel.addWidget(self.sessions_list)
        
        # Buttons for session list
        session_buttons = QHBoxLayout()
        delete_session_btn = QPushButton("Delete Session")
        delete_session_btn.clicked.connect(self.delete_selected_session)
        session_buttons.addWidget(delete_session_btn)
        
        clear_all_btn = QPushButton("Clear All History")
        clear_all_btn.clicked.connect(self.clear_all_history)
        session_buttons.addWidget(clear_all_btn)
        left_panel.addLayout(session_buttons)
        
        left_container = QVBoxLayout()
        left_container_widget = QListWidget()
        left_container_widget.setLayout(left_panel)
        
        # Right side: Chat display
        right_panel = QVBoxLayout()
        
        chat_label = QLabel("Chat Messages (click to copy to current chat):")
        chat_label.setStyleSheet("font-weight: bold;")
        right_panel.addWidget(chat_label)
        
        self.chat_display = QListWidget()
        self.chat_display.itemClicked.connect(self.on_message_clicked)
        right_panel.addWidget(self.chat_display)
        
        # Use containers for splitter
        left_widget_container = QListWidget()
        left_widget_container.setLayout(left_panel)
        
        right_widget_container = QListWidget()
        right_widget_container.setLayout(right_panel)
        
        # Actually, QSplitter needs QWidgets, not layouts
        # Let me restructure this properly
        from PySide6.QtWidgets import QWidget
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Load chat history
        self.load_chat_history()
    
    def load_chat_history(self):
        """Load chat sessions from settings."""
        self.sessions_list.clear()
        self.chat_display.clear()
        
        # Generate project-specific key
        import hashlib
        if self.project_path:
            key = hashlib.md5(self.project_path.encode()).hexdigest()
            sessions_key = f"chat_history/{key}"
        else:
            sessions_key = "chat_history"  # Fallback for old format
        
        print(f"DEBUG: Loading chat history from key: {sessions_key}")
        
        # Get stored chat sessions
        chat_sessions = self.settings.value(sessions_key, [])
        if not isinstance(chat_sessions, list):
            chat_sessions = []
        
        print(f"DEBUG: Found {len(chat_sessions)} chat sessions")
        
        self.chat_sessions = chat_sessions
        
        # Populate sessions list
        for i, session in enumerate(chat_sessions):
            timestamp = session.get('timestamp', 'Unknown time')
            title = session.get('title', 'Untitled Chat')
            message_count = len(session.get('messages', []))
            
            # Format display
            display_text = f"{timestamp} - {title} ({message_count} messages)"
            self.sessions_list.addItem(display_text)
    
    def on_session_selected(self, index):
        """Display selected chat session."""
        if index < 0 or index >= len(self.chat_sessions):
            return
        
        session = self.chat_sessions[index]
        messages = session.get('messages', [])
        
        self.chat_display.clear()
        
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            
            # Format display
            sender = "User" if role == "user" else "AI"
            color = "green" if role == "user" else "blue"
            
            # Truncate long messages for display
            preview = content[:100] + "..." if len(content) > 100 else content
            display_text = f"[{sender}] {preview}"
            
            item = self.chat_display.addItem(display_text)
            # Store full content in item data
            self.chat_display.item(self.chat_display.count() - 1).setData(Qt.UserRole, content)
    
    def on_message_clicked(self, item):
        """Copy clicked message to current chat."""
        content = item.data(Qt.UserRole)
        if content:
            self.message_copy_requested.emit(content)
            self.statusBar().showMessage(f"Message copied to current chat", 2000) if hasattr(self, 'statusBar') else None
            QMessageBox.information(self, "Copied", "Message copied to current chat!")
    
    def delete_selected_session(self):
        """Delete the selected chat session."""
        current_row = self.sessions_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a chat session to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Session",
            "Are you sure you want to delete this chat session?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.chat_sessions[current_row]
            self.save_chat_history()
            self.load_chat_history()
    
    def clear_all_history(self):
        """Clear all chat history."""
        reply = QMessageBox.question(
            self,
            "Clear All History",
            "Are you sure you want to clear all chat history? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.chat_sessions = []
            self.save_chat_history()
            self.load_chat_history()
            QMessageBox.information(self, "Cleared", "All chat history has been cleared.")
    
    def save_chat_history(self):
        """Save chat sessions to settings."""
        # Generate project-specific key
        import hashlib
        if self.project_path:
            key = hashlib.md5(self.project_path.encode()).hexdigest()
            sessions_key = f"chat_history/{key}"
        else:
            sessions_key = "chat_history"
        
        self.settings.setValue(sessions_key, self.chat_sessions)
