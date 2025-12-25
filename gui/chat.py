from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QPlainTextEdit, QPushButton, QHBoxLayout, QLabel, QLayout, QComboBox
from PySide6.QtCore import Signal, Qt, QSize, QRect, QPoint
from PySide6 import QtGui # Need QtGui for cursors in thinking logic
from PySide6.QtGui import QClipboard

import markdown


class FlowLayout(QLayout):
    """A layout that arranges widgets in rows, wrapping to the next row when needed."""
    
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
    
    def __del__(self):
        while self.count():
            self.takeAt(0)
    
    def addItem(self, item):
        self.itemList.append(item)
    
    def count(self):
        return len(self.itemList)
    
    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None
    
    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None
    
    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)
    
    def sizeHint(self):
        return self.minimumSize()
    
    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size
    
    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        
        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing()
            spaceY = self.spacing()
            nextX = x + item.sizeHint().width() + spaceX
            
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            
            if not testOnly:
                item.setGeometry(QRect(x, y, item.sizeHint().width(), item.sizeHint().height()))
            
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        
        return y + lineHeight - rect.y()


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
    message_deleted = Signal(int)  # Emits message index to delete
    message_edited = Signal(int, str)  # Emits message index and new content
    regenerate_requested = Signal()  # Request to regenerate last response
    continue_requested = Signal()  # Request to continue generation
    new_chat_requested = Signal()  # Request to start a new chat (saves current first)
    provider_changed = Signal(str)  # Emits new provider name (Ollama or LM Studio)
    model_changed = Signal(str)  # Emits new model name
    refresh_models_requested = Signal()  # Request to refresh available models
    context_level_changed = Signal(str)  # Emits context level: "None", "Visible", "All", "Full"
    message_copied = Signal(str)  # Emits "message" or "chat" when copied

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.messages = []  # Store messages as (sender, text) tuples
        
        # Model Selection Controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 5)
        controls_layout.setSpacing(8)
        
        # Provider dropdown
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio"])
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        self.provider_combo.setMinimumWidth(100)
        controls_layout.addWidget(self.provider_combo)
        
        # Model dropdown
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)  # Use index change instead of text
        controls_layout.addWidget(self.model_combo, 1)  # Give model combo most of the space
        
        # Refresh button
        refresh_btn = QPushButton("🔃")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.setToolTip("Refresh available models")
        refresh_btn.clicked.connect(self.on_refresh_models)
        controls_layout.addWidget(refresh_btn)
        
        self.layout.addLayout(controls_layout)
        
        # Chat History
        self.history = ChatBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setOpenLinks(False) # Disable auto-navigation for all links
        self.history.anchorClicked.connect(self.on_anchor_clicked)
        self.layout.addWidget(self.history, 1)  # Give this most of the space (stretch factor 1)
        
        # Chat Control Buttons - Wrappable layout
        button_layout = FlowLayout()
        button_layout.setSpacing(5)
        
        regenerate_btn = QPushButton("🔄")
        regenerate_btn.setMaximumWidth(40)
        regenerate_btn.setToolTip("Regenerate the last AI response")
        regenerate_btn.clicked.connect(self.on_regenerate)
        button_layout.addWidget(regenerate_btn)

        continue_btn = QPushButton("⏩")
        continue_btn.setMaximumWidth(40)
        continue_btn.setToolTip("Continue the AI response if it stopped early")
        continue_btn.clicked.connect(self.on_continue)
        button_layout.addWidget(continue_btn)
        
        new_chat_btn = QPushButton("🆕")
        new_chat_btn.setMaximumWidth(40)
        new_chat_btn.setToolTip("Start a new chat (saves current chat to history)")
        new_chat_btn.clicked.connect(self.on_new_chat)
        button_layout.addWidget(new_chat_btn)
        
        save_chat_btn = QPushButton("📁")
        save_chat_btn.setMaximumWidth(40)
        save_chat_btn.setToolTip("Save chat as file")
        save_chat_btn.clicked.connect(self.on_save_chat)
        button_layout.addWidget(save_chat_btn)
        
        copy_to_file_btn = QPushButton("📄")
        copy_to_file_btn.setMaximumWidth(40)
        copy_to_file_btn.setToolTip("Copy chat to open file")
        copy_to_file_btn.clicked.connect(self.on_copy_to_file)
        button_layout.addWidget(copy_to_file_btn)
        
        copy_to_clipboard_btn = QPushButton("📋")
        copy_to_clipboard_btn.setMaximumWidth(40)
        copy_to_clipboard_btn.setToolTip("Copy chat to clipboard")
        copy_to_clipboard_btn.clicked.connect(self.on_copy_to_clipboard)
        button_layout.addWidget(copy_to_clipboard_btn)
        
        self.layout.addLayout(button_layout)
        
        # Context Level Selector
        context_layout = QHBoxLayout()
        context_layout.setContentsMargins(0, 0, 0, 5)
        context_layout.setSpacing(5)
        
        context_label = QLabel("Context:")
        context_label.setStyleSheet("font-size: 9pt;")
        context_layout.addWidget(context_label)
        
        self.context_combo = QComboBox()
        self.context_combo.addItems([
            "None",
            "Visible Tab + Mentioned",
            "All Open Tabs",
            "Full"
        ])
        self.context_combo.setCurrentIndex(1)  # Default to "Visible Tab + Mentioned"
        self.context_combo.currentIndexChanged.connect(self.on_context_level_changed)
        context_layout.addWidget(self.context_combo, 1)
        
        self.layout.addLayout(context_layout)
        
        # Input Area - Taller with QPlainTextEdit for multi-line
        input_layout = QVBoxLayout()
        input_layout.setContentsMargins(0, 5, 0, 0)
        input_layout.setSpacing(5)
        
        self.input_field = QPlainTextEdit()
        self.input_field.setPlaceholderText("Type a message... (Ctrl+Enter to send)")
        self.input_field.setMaximumHeight(80)  # Allow up to 4-5 lines
        self.input_field.setMinimumHeight(40)  # Minimum 2 lines
        input_layout.addWidget(self.input_field)
        
        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.addStretch()
        self.send_btn = QPushButton("Send (Ctrl+Enter)")
        self.send_btn.clicked.connect(self.send_message)
        send_layout.addWidget(self.send_btn)
        
        input_layout.addLayout(send_layout)
        self.layout.addLayout(input_layout)

    def update_model_info(self, provider_name, model_name, available_models=None, vision_models=None):
        """Update model info and populate dropdown.
        
        Args:
            provider_name: Name of the provider (Ollama or LM Studio)
            model_name: Current model name
            available_models: List of available model names
            vision_models: List of model names that support vision
        """
        # Set provider combo without triggering signal
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentText(provider_name)
        self.provider_combo.blockSignals(False)
        
        # Update model combo with vision indicators
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        
        if available_models:
            vision_models = vision_models or []
            for model in available_models:
                display_text = f"👁️ {model}" if model in vision_models else model
                self.model_combo.addItem(display_text, model)  # Store actual model name in data
            
            # Set current model
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == model_name:
                    self.model_combo.setCurrentIndex(i)
                    break
        else:
            self.model_combo.addItem(model_name, model_name)
            self.model_combo.setCurrentIndex(0)
        
        self.model_combo.blockSignals(False)
    
    def set_available_models(self, models, vision_models=None):
        """Update the list of available models in the dropdown with vision indicators."""
        current_data = self.model_combo.currentData() or self.model_combo.currentText()
        
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        
        vision_models = vision_models or []
        for model in models:
            display_text = f"👁️ {model}" if model in vision_models else model
            self.model_combo.addItem(display_text, model)
        
        # Try to restore previous selection
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == current_data:
                self.model_combo.setCurrentIndex(i)
                break
        
        self.model_combo.blockSignals(False)
    
    def on_provider_changed(self, provider_name):
        """Emit signal when provider changes."""
        if provider_name:
            self.provider_changed.emit(provider_name)
    
    def on_model_changed(self, index):
        """Emit signal when model changes (gets actual model name from combo box data)."""
        if index >= 0:
            actual_model = self.model_combo.currentData()
            if actual_model:
                self.model_changed.emit(actual_model)
    
    def on_refresh_models(self):
        """Emit signal to refresh available models."""
        self.refresh_models_requested.emit()
    
    def on_context_level_changed(self, index):
        """Emit signal when context level changes."""
        level = self.context_combo.itemText(index)
        # Convert to internal format
        if level == "None":
            level = "none"
        elif level == "Visible Tab + Mentioned":
            level = "visible"
        elif level == "All Open Tabs":
            level = "all_open"
        elif level == "Full":
            level = "full"
        self.context_level_changed.emit(level)

    def on_anchor_clicked(self, url):
        url_str = url.toString()
        
        # Handle edit/delete links - parse both index and UUID formats
        if url_str.startswith("edit:"):
            try:
                msg_id = url_str.split(":", 1)[1]  # Split on first colon only
                # Try as integer index first (inline message edit)
                try:
                    msg_index = int(msg_id)
                    self.handle_edit_message(msg_index)
                    return
                except ValueError:
                    # UUID edit link for pending changes -> bubble up to main window
                    self.link_clicked.emit(url_str)
                    return
            except Exception:
                pass
        elif url_str.startswith("delete:"):
            try:
                msg_id = url_str.split(":", 1)[1]  # Split on first colon only
                # Try as integer index first, then treat as UUID
                try:
                    msg_index = int(msg_id)
                    self.handle_delete_message(msg_index)
                except ValueError:
                    # It's a UUID, not an index - ignore for now
                    pass
            except Exception:
                pass
        elif url_str.startswith("copy:"):
            try:
                msg_id = url_str.split(":", 1)[1]
                msg_index = int(msg_id)
                self.handle_copy_message(msg_index)
            except Exception:
                pass
        else:
            self.link_clicked.emit(url_str)
    
    def handle_edit_message(self, msg_index):
        """Open dialog to edit a message."""
        if msg_index >= len(self.messages):
            return
        
        sender, old_text = self.messages[msg_index]
        
        # Use QInputDialog for multiline input
        from PySide6.QtWidgets import QInputDialog, QTextEdit, QDialog, QVBoxLayout, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {sender} Message")
        dialog.setMinimumSize(500, 300)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(old_text)
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            new_text = text_edit.toPlainText().strip()
            if new_text and new_text != old_text:
                self.messages[msg_index] = (sender, new_text)
                self.message_edited.emit(msg_index, new_text)
                self.rebuild_chat_display()
    
    def handle_delete_message(self, msg_index):
        """Delete a message and emit signal."""
        if msg_index >= len(self.messages):
            return
        
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Delete Message",
            "Are you sure you want to delete this message?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.message_deleted.emit(msg_index)
    
    def rebuild_chat_display(self):
        """Rebuild the entire chat display from stored messages."""
        self.history.clear()
        temp_messages = list(self.messages)
        self.messages.clear()
        for sender, text in temp_messages:
            self.append_message(sender, text)
    
    def on_regenerate(self):
        """Request to regenerate the last AI response."""
        self.regenerate_requested.emit()

    def on_continue(self):
        """Request to continue the current AI response."""
        self.continue_requested.emit()
    
    def on_new_chat(self):
        """Request to start a new chat (saves current first)."""
        self.new_chat_requested.emit()
    
    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if text:
            self.append_message("User", text)
            self.message_sent.emit(text)
            self.input_field.clear()

    def keyPressEvent(self, event):
        """Override to handle Ctrl+Enter for sending messages."""
        if event.key() == Qt.Key_Return and (event.modifiers() & Qt.ControlModifier):
            if self.input_field.hasFocus():
                self.send_message()
                return
        super().keyPressEvent(event)

    def append_message(self, sender, text):
        # Store message for later reference
        msg_index = len(self.messages)
        self.messages.append((sender, text))
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(text)
        
        # Format the message block with edit/delete controls
        sender_color = "#4CAF50" if sender == "User" else "#2196F3"
        
        # Add message controls (edit and delete)
        controls_html = f'''
        <div style="margin-top: 5px;">
            <a href="edit:{msg_index}" style="color: #666; font-size: 9pt; text-decoration: none; margin-right: 10px;">✏️ Edit</a>
            <a href="delete:{msg_index}" style="color: #666; font-size: 9pt; text-decoration: none; margin-right: 10px;">🗑️ Delete</a>
            <a href="copy:{msg_index}" style="color: #666; font-size: 9pt; text-decoration: none;">📋 Copy</a>
        </div>
        '''
        
        formatted_msg = f"""
        <div style="margin-bottom: 10px;" data-msg-index="{msg_index}">
            <b style="color: {sender_color};">{sender}:</b>
            <div style="margin-top: 5px;">{html_content}</div>
            {controls_html}
        </div>
        <hr>
        """
        self.history.append(formatted_msg)

    def handle_copy_message(self, msg_index):
        """Copy a single message's raw text to clipboard."""
        if msg_index >= len(self.messages):
            return
        _, text = self.messages[msg_index]
        clipboard = QtGui.QGuiApplication.clipboard()
        clipboard.setText(text, QClipboard.Clipboard)
        self.message_copied.emit("message")
    
    def clear_chat(self):
        """Clear all messages."""
        self.messages.clear()
        self.history.clear()

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
        self.message_copied.emit("chat")

