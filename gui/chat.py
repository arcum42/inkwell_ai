import html

import markdown
from PySide6 import QtGui
from PySide6.QtCore import Signal, Qt, QSize, QRect, QPoint
from PySide6.QtGui import QClipboard, QKeySequence, QFont, QShortcut
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QPlainTextEdit, QPushButton, QHBoxLayout, QLabel, QLayout, QComboBox
from PySide6.QtCore import QSettings


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
    provider_changed = Signal(str)  # Emits new provider name (Ollama or LM Studio Native)
    model_changed = Signal(str)  # Emits new model name
    refresh_models_requested = Signal()  # Request to refresh available models
    context_level_changed = Signal(str)  # Emits context level: "None", "Visible", "All", "Full"
    mode_changed = Signal(str)  # Emits mode: "ask" or "edit"
    schema_changed = Signal(str)  # Emits schema id or "None"
    message_copied = Signal(str)  # Emits "message" or "chat" when copied
    persona_changed = Signal(str)  # Emits persona name when changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.messages = []  # Store messages as (sender, text) tuples
        
        # Apply font settings
        self.apply_font_settings()
        
        # Zoom shortcuts
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        # Model Selection Controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 5)
        controls_layout.setSpacing(8)
        
        # Provider dropdown
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio (Native SDK)"])
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
        
        # Persona Selection (if project is open)
        persona_layout = QHBoxLayout()
        persona_layout.setContentsMargins(0, 0, 0, 5)
        persona_layout.setSpacing(8)
        
        persona_label = QLabel("Persona:")
        persona_label.setStyleSheet("font-size: 9pt;")
        persona_layout.addWidget(persona_label)
        
        self.persona_combo = QComboBox()
        self.persona_combo.currentIndexChanged.connect(self.on_persona_changed)
        persona_layout.addWidget(self.persona_combo, 1)
        
        self.layout.addLayout(persona_layout)
        
        # Chat History
        self.history = ChatBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setOpenLinks(False) # Disable auto-navigation for all links
        self.history.anchorClicked.connect(self.on_anchor_clicked)
        self.layout.addWidget(self.history, 1)  # Give this most of the space (stretch factor 1)

        # Thinking state (used when models emit reasoning text)
        self.thinking_buffer = ""
        self.thinking_active = False
        self.thinking_expanded = False
        self.thinking_present = False
        self.thinking_title = "Assistant is thinking…"
        self.current_mode = "edit"  # Default mode: edit or ask
        self.streaming_response = False  # Track if we're currently streaming a response
        self._streaming_buffer = ""  # Buffer for accumulating streaming chunks
        self.raw_view = False  # Track if raw view is active
        
        # Chat Control Buttons - Wrappable layout
        button_layout = FlowLayout()
        button_layout.setSpacing(5)
        
        raw_view_btn = QPushButton("📜")
        raw_view_btn.setMaximumWidth(40)
        raw_view_btn.setToolTip("Toggle raw message view (shows unparsed LLM responses)")
        raw_view_btn.setCheckable(True)
        raw_view_btn.toggled.connect(self.on_raw_view_toggled)
        button_layout.addWidget(raw_view_btn)
        self.raw_view_btn = raw_view_btn
        
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

        # Schema Selector (advanced)
        schema_layout = QHBoxLayout()
        schema_layout.setContentsMargins(0, 0, 0, 5)
        schema_layout.setSpacing(5)

        schema_label = QLabel("Schema:")
        schema_label.setStyleSheet("font-size: 9pt;")
        schema_layout.addWidget(schema_label)

        self.schema_combo = QComboBox()
        self._populate_schema_dropdown()
        self.schema_combo.currentIndexChanged.connect(self.on_schema_changed)
        schema_layout.addWidget(self.schema_combo, 1)

        self.layout.addLayout(schema_layout)
        
        # Mode Selector
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 5)
        mode_layout.setSpacing(5)
        
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-size: 9pt;")
        mode_layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ask", "Edit"])
        self.mode_combo.setCurrentIndex(1)  # Default to Edit
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo, 1)
        
        self.layout.addLayout(mode_layout)
        
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
    
    def apply_font_settings(self):
        """Apply font settings from QSettings to chat history and input."""
        settings = QSettings("InkwellAI", "InkwellAI")
        font_family = settings.value("editor_font_family", "Monospace")
        font_size = int(settings.value("editor_font_size", 11))
        
        font = QFont(font_family, font_size)
        if hasattr(self, 'history'):
            self.history.setFont(font)
        if hasattr(self, 'input_field'):
            self.input_field.setFont(font)
    
    def zoom_in(self):
        """Increase font size by 1 point."""
        if hasattr(self, 'history'):
            current_font = self.history.font()
            current_font.setPointSize(min(32, current_font.pointSize() + 1))
            self.history.setFont(current_font)
            self.input_field.setFont(current_font)
    
    def zoom_out(self):
        """Decrease font size by 1 point."""
        if hasattr(self, 'history'):
            current_font = self.history.font()
            current_font.setPointSize(max(8, current_font.pointSize() - 1))
            self.history.setFont(current_font)
            self.input_field.setFont(current_font)

    def update_model_info(self, provider_name, model_name, available_models=None, vision_models=None, loaded_models=None):
        """Update model info and populate dropdown.
        
        Args:
            provider_name: Name of the provider (Ollama or LM Studio)
            model_name: Current model name
            available_models: List of available model names
            vision_models: List of model names that support vision
            loaded_models: List of models currently loaded (if known)
        """
        # Set provider combo without triggering signal
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentText(provider_name)
        self.provider_combo.blockSignals(False)
        
        # Update model combo with vision indicators
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        loaded_set = set(loaded_models or [])
        
        if available_models:
            vision_models = vision_models or []
            for model in available_models:
                eye = "👁️ " if model in vision_models else ""
                loaded = "🟢 " if model in loaded_set else ""
                display_text = f"{loaded}{eye}{model}" if (loaded or eye) else model
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
    
    def set_available_models(self, models, vision_models=None, loaded_models=None):
        """Update the list of available models in the dropdown with vision/loaded indicators."""
        current_data = self.model_combo.currentData() or self.model_combo.currentText()
        
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        loaded_set = set(loaded_models or [])
        
        vision_models = vision_models or []
        for model in models:
            eye = "👁️ " if model in vision_models else ""
            loaded = "🟢 " if model in loaded_set else ""
            display_text = f"{loaded}{eye}{model}" if (loaded or eye) else model
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
            # Re-populate schema list for the selected provider
            self._populate_schema_dropdown(provider_name)
    
    def on_model_changed(self, index):
        """Emit signal when model changes (gets actual model name from combo box data)."""
        if index >= 0:
            actual_model = self.model_combo.currentData()
            if actual_model:
                self.model_changed.emit(actual_model)
    
    def on_refresh_models(self):
        """Emit signal to refresh available models."""
        self.refresh_models_requested.emit()
    
    def on_persona_changed(self, index):
        """Emit signal when persona changes."""
        if index >= 0:
            persona_name = self.persona_combo.currentText()
            if persona_name:
                self.persona_changed.emit(persona_name)
    
    def update_personas(self, personas, active_name=None):
        """Update the persona dropdown with available personas.
        
        Args:
            personas: Dict of {name: prompt}
            active_name: Name of the currently active persona
        """
        self.persona_combo.blockSignals(True)
        self.persona_combo.clear()
        
        if not personas:
            self.persona_combo.addItem("(No personas)")
            self.persona_combo.setEnabled(False)
        else:
            sorted_names = sorted(personas.keys())
            for name in sorted_names:
                self.persona_combo.addItem(name)
            
            # Set the active persona
            if active_name and active_name in personas:
                self.persona_combo.setCurrentText(active_name)
            
            self.persona_combo.setEnabled(True)
        
        self.persona_combo.blockSignals(False)
    
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
    
    def on_mode_changed(self, index):
        """Emit signal when mode changes."""
        mode = self.mode_combo.itemText(index).lower()
        self.current_mode = mode
        self.mode_changed.emit(mode)

    def on_schema_changed(self, index):
        """Persist schema selection and emit signal."""
        sid = self.schema_combo.itemData(index)
        # Store in settings for controller/worker use
        settings = QSettings("InkwellAI", "InkwellAI")
        settings.setValue("structured_schema_id", sid or "None")
        self.schema_changed.emit(sid or "None")

    def _populate_schema_dropdown(self, provider_display: str | None = None):
        """Fill schema dropdown based on provider support and stored selection."""
        try:
            from core.llm.schemas import list_schemas
        except Exception:
            # If registry not available, show only None
            self.schema_combo.clear()
            self.schema_combo.addItem("None", None)
            return

        # Map display name to provider class name for allowlist filtering
        provider_display = provider_display or self.provider_combo.currentText()
        provider_map = {
            "Ollama": "OllamaProvider",
            "LM Studio (Native SDK)": "LMStudioNativeProvider",
        }
        provider_class = provider_map.get(provider_display)

        self.schema_combo.blockSignals(True)
        self.schema_combo.clear()
        self.schema_combo.addItem("None", None)
        entries = list_schemas(allowed_provider=provider_class) if provider_class else []
        for entry in entries:
            sid = entry.get('id')
            desc = entry.get('description') or sid
            label = f"{sid}"
            if desc and desc != sid:
                label = f"{sid} — {desc}"
            self.schema_combo.addItem(label, sid)

        # Restore previous selection from settings
        settings = QSettings("InkwellAI", "InkwellAI")
        saved = settings.value("structured_schema_id", "None")
        # Find index by data
        for i in range(self.schema_combo.count()):
            data = self.schema_combo.itemData(i)
            if (saved == "None" and data is None) or (data == saved):
                self.schema_combo.setCurrentIndex(i)
                break
        self.schema_combo.blockSignals(False)

    def on_anchor_clicked(self, url):
        url_str = url.toString()
        
        if url_str == "show-thinking":
            # Show thinking text in a dialog without mixing into chat
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
            dialog = QDialog(self)
            dialog.setWindowTitle("Thinking trace")
            dialog.setMinimumSize(500, 300)
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setPlainText(self.thinking_buffer if self.thinking_buffer else "(No thinking text captured)")
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            buttons.accepted.connect(dialog.accept)
            layout.addWidget(buttons)
            dialog.exec()
            return
        if url_str == "toggle-thinking":
            self.thinking_expanded = not self.thinking_expanded
            self._render_thinking_block(done=not self.thinking_active)
            return
        if url_str.startswith("raw:"):
            try:
                msg_id = url_str.split(":", 1)[1]
                msg_index = int(msg_id)
                self.handle_raw_message(msg_index)
                return
            except Exception:
                pass
        
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
        
        msg_tuple = self.messages[msg_index]
        sender = msg_tuple[0]
        old_text = msg_tuple[1]
        raw_text = msg_tuple[2] if len(msg_tuple) > 2 else old_text
        
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
                # Preserve raw text (or use new text as raw)
                self.messages[msg_index] = (sender, new_text, raw_text)
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
        for msg_tuple in temp_messages:
            sender = msg_tuple[0]
            text = msg_tuple[1]
            raw_text = msg_tuple[2] if len(msg_tuple) > 2 else text
            self.append_message(sender, text, raw_text=raw_text)
    
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

    def append_message(self, sender, text, raw_text=None):
        # Store message for later reference (with optional raw version)
        msg_index = len(self.messages)
        self.messages.append((sender, text, raw_text or text))  # Store as 3-tuple
        autoscroll = self._should_autoscroll()
        
        # Check if we should combine with previous System message (only in normal view)
        if not self.raw_view and sender == "System" and self.messages and len(self.messages) >= 2:
            prev_sender = self.messages[-2][0] if len(self.messages) >= 2 else None
            if prev_sender == "System":
                # Combine with previous system message
                self._combine_system_message(msg_index, text)
                if autoscroll:
                    self._scroll_to_bottom(force=True)
                return
        
        # Choose display text based on view mode
        display_text = (raw_text or text) if self.raw_view else text
        
        # Format based on view mode
        if self.raw_view:
            # Raw view: plain text in monospace, no markdown parsing
            escaped_text = html.escape(display_text)
            html_content = f'<pre style="white-space: pre-wrap; font-family: monospace; font-size: 10pt;">{escaped_text}</pre>'
        else:
            # Normal view: markdown rendering
            html_content = markdown.markdown(display_text)
        
        # Format the message block with edit/delete controls
        sender_color = "#4CAF50" if sender == "User" else ("#2196F3" if sender == "Assistant" else "#888")
        
        # Add message controls (without Raw button)
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
        if autoscroll:
            self._scroll_to_bottom(force=True)
    
    def _combine_system_message(self, msg_index, new_text):
        """Combine a new system message with the previous system message block."""
        # Find and update the last system message block in the history
        doc = self.history.document()
        cursor = QtGui.QTextCursor(doc)  # Use a QTextCursor; doc.end() returns a QTextBlock
        
        # Search backwards for the last system message block
        cursor.movePosition(QtGui.QTextCursor.Start)
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
        html = cursor.selection().toHtml()
        
        # Find the last System message div
        import re
        # Pattern to find the last system message content div
        pattern = r'(<div[^>]*data-msg-index="(\d+)"[^>]*>.*?<b[^>]*>System:</b>.*?<div[^>]*>)(.*?)(</div>.*?</div>\s*<hr>)'
        matches = list(re.finditer(pattern, html, re.DOTALL))
        
        if matches:
            last_match = matches[-1]
            prev_index = int(last_match.group(2))
            
            # Get previous message content and append new text
            prev_content = self.messages[prev_index][1]
            combined_text = prev_content + "\n" + new_text
            
            # Update stored message
            self.messages[prev_index] = ("System", combined_text, combined_text)
            
            # Rebuild the combined HTML
            html_content = markdown.markdown(combined_text)
            sender_color = "#888"
            
            controls_html = f'''
            <div style="margin-top: 5px;">
                <a href="edit:{prev_index}" style="color: #666; font-size: 9pt; text-decoration: none; margin-right: 10px;">✏️ Edit</a>
                <a href="delete:{prev_index}" style="color: #666; font-size: 9pt; text-decoration: none; margin-right: 10px;">🗑️ Delete</a>
                <a href="copy:{prev_index}" style="color: #666; font-size: 9pt; text-decoration: none;">📋 Copy</a>
            </div>
            '''
            
            new_formatted_msg = f"""
            <div style="margin-bottom: 10px;" data-msg-index="{prev_index}">
                <b style="color: {sender_color};">System:</b>
                <div style="margin-top: 5px;">{html_content}</div>
                {controls_html}
            </div>
            <hr>
            """
            
            # Replace the old system message with the combined one
            # Remove the last system message block and hr
            cursor.movePosition(QtGui.QTextCursor.End)
            # Find last <hr> and select everything from the previous <hr> to the end
            search_text = '<div style="margin-bottom: 10px;" data-msg-index="' + str(prev_index) + '"'
            cursor.movePosition(QtGui.QTextCursor.Start)
            cursor = doc.find(search_text, cursor)
            if not cursor.isNull():
                start_pos = cursor.position()
                cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                cursor.insertHtml(new_formatted_msg)

    def begin_thinking(self):
        """Show a lightweight thinking indicator with a toggle link."""
        self.thinking_buffer = ""
        self.thinking_active = True
        self.thinking_expanded = False
        self.thinking_present = True
        self._render_thinking_block()

    def append_thinking_chunk(self, chunk: str):
        """Accumulate thinking text without showing it inline."""
        if not self.thinking_active:
            return
        self.thinking_buffer += chunk
        if self.thinking_present and self.thinking_expanded:
            self._render_thinking_block()

    def finish_thinking(self):
        """Mark thinking as done and update indicator text."""
        if not self.thinking_active:
            return
        self.thinking_active = False
        self.thinking_present = True
        self._render_thinking_block(done=True)

    def _render_thinking_block(self, done: bool = False):
        """Insert or update the inline thinking block with toggle and optional content."""
        if not self.thinking_present:
            return
        autoscroll = self._should_autoscroll()
        self._remove_thinking_blocks()

        status = "complete" if done else "in progress"
        title = self.thinking_title if not done else "Thinking complete"
        toggle_label = "Hide" if self.thinking_expanded else "Show"
        content_html = ""
        if self.thinking_expanded and self.thinking_buffer:
            escaped = html.escape(self.thinking_buffer)
            content_html = (
                '<div style="margin-top:4px;white-space:pre-wrap;font-family:monospace;'
                'font-size:10pt;border-top:1px dashed #ccc;padding-top:4px;">'
                f"{escaped}"
                "</div>"
            )

        body = (
            '<div style="background:#f5f5f5;padding:6px;border:1px solid #ddd;">'
            f"<b>{title}</b> "
            f'<span style="font-size:9pt;color:#666;">({status})</span> '
            f'<a href="toggle-thinking">{toggle_label}</a> | '
            '<a href="show-thinking">Dialog</a>'
            '</div>'
            f"{content_html}"
        )

        self.history.append(body)
        if autoscroll:
            self._scroll_to_bottom()

    def _remove_thinking_blocks(self):
        """Remove any existing thinking blocks to avoid duplication before re-rendering."""
        doc = self.history.document()
        # Loop until no toggle anchors remain
        while True:
            cursor = doc.find("toggle-thinking", 0)
            if cursor.isNull():
                break
            cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
            cursor.select(QtGui.QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            # Remove potential trailing content block if present (expanded state)
            cursor.select(QtGui.QTextCursor.BlockUnderCursor)
            if cursor.selectedText():
                cursor.removeSelectedText()
                cursor.deletePreviousChar()

    def begin_streaming_response(self):
        """Prepare to accumulate a streaming response in a buffer.
        
        Don't add anything to the chat display yet - just initialize the buffer.
        The complete message will be added when streaming finishes.
        """
        if not self.streaming_response:
            self.streaming_response = True
            # Store index where streaming message will be inserted
            self._streaming_msg_index = len(self.messages)
            # Initialize streaming buffer for this message
            self._streaming_buffer = ""
    
    def finish_streaming_response(self, final_text: str, raw_text: str = None):
        """Add the streamed response to the chat as a complete message.
        
        Args:
            final_text: Final formatted response after parsing
            raw_text: Original unparsed response for Raw button (optional)
        """
        if not self.streaming_response:
            return
        
        self.streaming_response = False
        
        # If no final_text provided, use the accumulated streaming buffer
        if not final_text and hasattr(self, '_streaming_buffer'):
            final_text = self._streaming_buffer
        
        # Add the complete response as a single message (seamless)
        self.append_message("Assistant", final_text, raw_text=raw_text or final_text)
        
        # Clear the streaming buffer
        self._streaming_buffer = ""

    def append_response_chunk(self, chunk: str):
        """Append a chunk of streaming response to the chat.
        
        Called as tokens arrive from the LLM during streaming.
        Accumulates chunks in a buffer without displaying them yet.
        The full message will be displayed when streaming is complete.
        
        Args:
            chunk: String token/chunk to append
        """
        if not self.streaming_response or not hasattr(self, '_streaming_buffer'):
            return
        
        # Just accumulate the chunk - don't display it yet
        self._streaming_buffer += chunk

    def handle_copy_message(self, msg_index):
        """Copy a single message's raw text to clipboard."""
        if msg_index >= len(self.messages):
            return
        msg_tuple = self.messages[msg_index]
        text = msg_tuple[1]  # Copy display text
        clipboard = QtGui.QGuiApplication.clipboard()
        clipboard.setText(text, QClipboard.Clipboard)
        self.message_copied.emit("message")

    def on_raw_view_toggled(self, checked):
        """Toggle between normal and raw message view."""
        self.raw_view = checked
        self.rebuild_chat_display()

    def _should_autoscroll(self, threshold: int = 4) -> bool:
        """Return True if the view is within `threshold` pixels of bottom."""
        scrollbar = self.history.verticalScrollBar()
        return scrollbar.maximum() - scrollbar.value() <= threshold

    def _scroll_to_bottom(self, force: bool = False):
        """Scroll to bottom if force or user was already near bottom."""
        scrollbar = self.history.verticalScrollBar()
        if force or self._should_autoscroll():
            scrollbar.setValue(scrollbar.maximum())
    
    def clear_chat(self):
        """Clear all messages."""
        self.messages.clear()
        self.history.clear()
        self.thinking_buffer = ""
        self.thinking_active = False
        self.thinking_present = False
        self.thinking_expanded = False
        self._streaming_buffer = ""
        self.streaming_response = False

    def show_thinking(self):
        """Appends a temporary 'Thinking...' message."""
        autoscroll = self._should_autoscroll()
        self.history.append('<div style="color: gray; font-style: italic;">AI is thinking...</div>')
        if autoscroll:
            self._scroll_to_bottom()

    def remove_thinking(self):
        """Removes the last block (assumed to be the 'Thinking...' message)."""
        if not self.thinking_present:
            return
        self._remove_thinking_blocks()
        self.thinking_present = False
        self.thinking_active = False
        self.thinking_expanded = False
        self.thinking_buffer = ""

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

