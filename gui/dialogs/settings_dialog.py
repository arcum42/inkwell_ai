from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
    QGroupBox,
    QSpinBox,
    QWidget,
    QFontComboBox,
    QLabel,
    QTextEdit,
    QTabWidget,
    QListWidget,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from core.tool_base import get_registry
# Ensure tools are loaded and registered
import core.tools  # noqa: F401
from core.tools.registry import AVAILABLE_TOOLS

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(700, 600)
        
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.registry = get_registry()
        self.tool_checkboxes = {}
        self.tool_settings_widgets = {}  # tool_name -> {setting_name -> widget}
        self.proj = getattr(parent, 'project_manager', None)
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Create tabs
        self.general_tab = self.create_general_tab()
        self.personas_tab = self.create_personas_tab()
        self.tools_tab = self.create_tools_tab()
        self.editing_tab = self.create_editing_tab()
        self.advanced_tab = self.create_advanced_tab()
        
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.personas_tab, "Personas")
        self.tabs.addTab(self.tools_tab, "Tools")
        self.tabs.addTab(self.editing_tab, "Editing")
        self.tabs.addTab(self.advanced_tab, "Advanced")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def create_general_tab(self):
        """Create the General settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form_layout = QFormLayout()
        
        # LLM Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio (Native SDK)"])
        current_provider = self.settings.value("llm_provider", "Ollama")
        # Map deprecated "LM Studio" to native SDK
        if current_provider == "LM Studio":
            current_provider = "LM Studio (Native SDK)"
            self.settings.setValue("llm_provider", current_provider)
        self.provider_combo.setCurrentText(current_provider)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        form_layout.addRow("LLM Provider:", self.provider_combo)
        
        # Ollama URL
        self.ollama_url = QLineEdit()
        self.ollama_url.setText(self.settings.value("ollama_url", "http://localhost:11434"))
        self.ollama_row = form_layout.rowCount()
        form_layout.addRow("Ollama URL:", self.ollama_url)
        
        # LM Studio URL (deprecated OpenAI-compatible)
        self.lm_studio_url = QLineEdit()
        self.lm_studio_url.setText(self.settings.value("lm_studio_url", "http://localhost:1234"))
        self.lm_studio_row = form_layout.rowCount()
        form_layout.addRow("LM Studio URL (deprecated):", self.lm_studio_url)
        
        # LM Studio Native SDK URL
        self.lm_studio_native_url = QLineEdit()
        self.lm_studio_native_url.setText(self.settings.value("lm_studio_native_url", "localhost:1234"))
        self.lm_native_row = form_layout.rowCount()
        form_layout.addRow("LM Studio Native URL:", self.lm_studio_native_url)
        
        # ComfyUI URL
        self.comfy_url = QLineEdit()
        self.comfy_url.setText(self.settings.value("comfy_url", "http://127.0.0.1:8188"))
        form_layout.addRow("ComfyUI URL:", self.comfy_url)
        
        # Font settings
        self.font_family_combo = QFontComboBox()
        default_font = self.settings.value("editor_font_family", "Monospace")
        self.font_family_combo.setCurrentFont(QFont(default_font))
        form_layout.addRow("Editor Font:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setValue(int(self.settings.value("editor_font_size", 11)))
        form_layout.addRow("Editor Font Size:", self.font_size_spin)

        # Default Image Save Folder
        self.default_image_folder = QLineEdit()
        self.default_image_folder.setPlaceholderText("assets/images")
        self.default_image_folder.setText(self.settings.value("default_image_folder", "assets/images"))
        form_layout.addRow("Default Image Folder:", self.default_image_folder)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Set URL visibility based on current provider
        self.form_layout = form_layout
        self.update_url_visibility(current_provider)
        
        return tab

    def create_personas_tab(self):
        """Create the Personas management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not self.proj or not self.proj.get_root_path():
            label = QLabel("Open a project to manage personas")
            label.setWordWrap(True)
            layout.addWidget(label)
            return tab
        
        # Top section with list and buttons
        top_layout = QHBoxLayout()
        
        # List of personas
        self.persona_list = QListWidget()
        self.persona_list.currentItemChanged.connect(self.on_persona_selected)
        top_layout.addWidget(self.persona_list, 2)
        
        # Buttons
        button_layout = QVBoxLayout()
        self.add_persona_btn = QPushButton("Add")
        self.add_persona_btn.clicked.connect(self.add_persona)
        button_layout.addWidget(self.add_persona_btn)
        
        self.remove_persona_btn = QPushButton("Remove")
        self.remove_persona_btn.clicked.connect(self.remove_persona)
        button_layout.addWidget(self.remove_persona_btn)
        
        self.set_active_btn = QPushButton("Set Active")
        self.set_active_btn.clicked.connect(self.set_active_persona)
        button_layout.addWidget(self.set_active_btn)
        
        button_layout.addStretch()
        top_layout.addLayout(button_layout)
        
        layout.addLayout(top_layout, 1)
        
        # Bottom section with persona editor
        editor_group = QGroupBox("Persona Details")
        editor_layout = QFormLayout()
        
        self.persona_name_edit = QLineEdit()
        self.persona_name_edit.setPlaceholderText("Persona name")
        editor_layout.addRow("Name:", self.persona_name_edit)
        
        self.persona_prompt_edit = QTextEdit()
        self.persona_prompt_edit.setPlaceholderText(
            "System prompt for this persona.\n\n"
            "Examples:\n"
            "• For fiction: 'You are a creative writing assistant specializing in fantasy fiction.'\n"
            "• For code: 'You are a Python expert who writes clean, documented code.'\n"
            "• For technical writing: 'You are a technical documentation specialist.'"
        )
        editor_layout.addRow("System Prompt:", self.persona_prompt_edit)
        
        self.save_persona_btn = QPushButton("Save Changes")
        self.save_persona_btn.clicked.connect(self.save_persona_changes)
        editor_layout.addRow("", self.save_persona_btn)
        
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group, 2)
        
        # Load personas
        self.load_personas()
        
        return tab

    def create_tools_tab(self):
        """Create the Tools configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not self.proj or not self.proj.get_root_path():
            label = QLabel("Open a project to configure tools")
            label.setWordWrap(True)
            layout.addWidget(label)
            return tab
        
        tools_group = QGroupBox("Project Tools")
        tools_layout = QVBoxLayout()
        enabled_set = self.proj.get_enabled_tools()
        
        # Build list from all known tool classes
        for tool_cls in AVAILABLE_TOOLS.values():
            try:
                tool = tool_cls()
            except Exception:
                continue
            # Tool checkbox
            label_text = tool.name
            if not tool.is_available():
                label_text = f"{tool.name} (missing deps)"
            cb = QCheckBox(label_text)
            cb.setChecked(True if (enabled_set is None or tool.name in enabled_set) else False)
            if not tool.is_available():
                cb.setEnabled(False)
            self.tool_checkboxes[tool.name] = cb
            tools_layout.addWidget(cb)
            
            # Tool settings (indented)
            settings_schema = tool.get_configurable_settings()
            if settings_schema:
                tool_settings_layout = QFormLayout()
                tool_settings_widget = QWidget()
                tool_settings_widget.setLayout(tool_settings_layout)
                tool_settings_widget.setStyleSheet("margin-left: 20px;")
                
                self.tool_settings_widgets[tool.name] = {}
                current_settings = self.proj.get_tool_settings(tool.name)
                
                for setting_name, schema in settings_schema.items():
                    setting_type = schema.get("type", "str")
                    default_val = schema.get("default")
                    desc = schema.get("description", "")
                    current_val = current_settings.get(setting_name, default_val)
                    
                    if setting_type == "int":
                        widget = QSpinBox()
                        widget.setRange(0, 10000)
                        widget.setValue(current_val)
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    elif setting_type == "bool":
                        widget = QCheckBox()
                        widget.setChecked(current_val)
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    else:  # str
                        widget = QLineEdit()
                        widget.setText(str(current_val))
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    
                    # Add description label if available
                    if desc:
                        desc_label = QLabel(f"<i>{desc}</i>")
                        desc_label.setWordWrap(True)
                        tool_settings_layout.addRow("", desc_label)
                
                tools_layout.addWidget(tool_settings_widget)
        
        tools_group.setLayout(tools_layout)
        layout.addWidget(tools_group)
        layout.addStretch()
        
        return tab

    def create_editing_tab(self):
        """Create the Editing preferences tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not self.proj or not self.proj.get_root_path():
            label = QLabel("Open a project to configure editing preferences")
            label.setWordWrap(True)
            layout.addWidget(label)
            return tab
        
        editing_group = QGroupBox("Editing Preferences")
        editing_layout = QFormLayout()
        
        self.apply_only_selection_cb = QCheckBox("Default to apply only within selection when available")
        default_apply_only = False
        try:
            default_apply_only = bool(self.proj.get_editing_settings().get('apply_only_selection_default', False))
        except Exception:
            default_apply_only = False
        self.apply_only_selection_cb.setChecked(default_apply_only)
        editing_layout.addRow(self.apply_only_selection_cb)
        
        editing_group.setLayout(editing_layout)
        layout.addWidget(editing_group)
        layout.addStretch()
        
        return tab

    def load_personas(self):
        """Load personas into the list widget."""
        self.persona_list.clear()
        personas = self.proj.get_all_personas()
        active_name, _ = self.proj.get_active_persona()
        
        for name in sorted(personas.keys()):
            prefix = "★ " if name == active_name else ""
            self.persona_list.addItem(f"{prefix}{name}")
        
        # Select the active persona if it exists
        if active_name:
            for i in range(self.persona_list.count()):
                if self.persona_list.item(i).text().endswith(active_name):
                    self.persona_list.setCurrentRow(i)
                    break

    def on_persona_selected(self, current, previous):
        """Load the selected persona into the editor."""
        if not current:
            self.persona_name_edit.clear()
            self.persona_prompt_edit.clear()
            return
        
        # Remove the star prefix if present
        name = current.text().lstrip("★ ")
        personas = self.proj.get_all_personas()
        
        if name in personas:
            self.persona_name_edit.setText(name)
            self.persona_prompt_edit.setPlainText(personas[name])

    def add_persona(self):
        """Add a new persona."""
        name, ok = QInputDialog.getText(self, "Add Persona", "Persona name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        personas = self.proj.get_all_personas()
        
        if name in personas:
            QMessageBox.warning(self, "Duplicate Name", f"A persona named '{name}' already exists.")
            return
        
        # Add with empty prompt
        if self.proj.add_persona(name, " "):  # Space to satisfy validation
            self.load_personas()
            # Select the new persona
            for i in range(self.persona_list.count()):
                if self.persona_list.item(i).text().endswith(name):
                    self.persona_list.setCurrentRow(i)
                    break

    def remove_persona(self):
        """Remove the selected persona."""
        current = self.persona_list.currentItem()
        if not current:
            QMessageBox.information(self, "No Selection", "Please select a persona to remove.")
            return
        
        name = current.text().lstrip("★ ")
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove the persona '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.proj.remove_persona(name):
                self.load_personas()
                self.persona_name_edit.clear()
                self.persona_prompt_edit.clear()

    def set_active_persona(self):
        """Set the selected persona as active."""
        current = self.persona_list.currentItem()
        if not current:
            QMessageBox.information(self, "No Selection", "Please select a persona to activate.")
            return
        
        name = current.text().lstrip("★ ")
        if self.proj.select_active_persona(name):
            self.load_personas()

    def save_persona_changes(self):
        """Save changes to the current persona."""
        current = self.persona_list.currentItem()
        if not current:
            QMessageBox.information(self, "No Selection", "Please select a persona to edit.")
            return
        
        old_name = current.text().lstrip("★ ")
        new_name = self.persona_name_edit.text().strip()
        prompt = self.persona_prompt_edit.toPlainText().strip()
        
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Persona name cannot be empty.")
            return
        
        if not prompt:
            QMessageBox.warning(self, "Invalid Prompt", "System prompt cannot be empty.")
            return
        
        personas = self.proj.get_all_personas()
        if new_name != old_name and new_name in personas:
            QMessageBox.warning(self, "Duplicate Name", f"A persona named '{new_name}' already exists.")
            return
        
        if self.proj.update_persona(old_name, new_name, prompt):
            self.load_personas()
            # Re-select the renamed persona
            for i in range(self.persona_list.count()):
                if self.persona_list.item(i).text().endswith(new_name):
                    self.persona_list.setCurrentRow(i)
                    break
        tools_group = QGroupBox("Project Tools")
        tools_layout = QVBoxLayout()
        enabled_set = None
        if proj and proj.get_root_path():
            enabled_set = proj.get_enabled_tools()
        
        # Build list from all known tool classes, not just currently registered
        for tool_cls in AVAILABLE_TOOLS.values():
            try:
                tool = tool_cls()
            except Exception:
                # Skip tools that cannot be constructed for UI listing
                continue
            # Tool checkbox
            label = tool.name
            if not tool.is_available():
                label = f"{tool.name} (missing deps)"
            cb = QCheckBox(label)
            cb.setChecked(True if (enabled_set is None or tool.name in enabled_set) else False)
            if not tool.is_available():
                cb.setEnabled(False)
            self.tool_checkboxes[tool.name] = cb
            tools_layout.addWidget(cb)
            
            # Tool settings (indented)
            settings_schema = tool.get_configurable_settings()
            if settings_schema and proj and proj.get_root_path():
                tool_settings_layout = QFormLayout()
                tool_settings_widget = QWidget()
                tool_settings_widget.setLayout(tool_settings_layout)
                tool_settings_widget.setStyleSheet("margin-left: 20px;")
                
                self.tool_settings_widgets[tool.name] = {}
                current_settings = proj.get_tool_settings(tool.name)
                
                for setting_name, schema in settings_schema.items():
                    setting_type = schema.get("type", "str")
                    default_val = schema.get("default")
                    desc = schema.get("description", "")
                    current_val = current_settings.get(setting_name, default_val)
                    
                    if setting_type == "int":
                        widget = QSpinBox()
                        widget.setRange(0, 10000)
                        widget.setValue(current_val)
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    elif setting_type == "bool":
                        widget = QCheckBox()
                        widget.setChecked(current_val)
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    else:  # str
                        widget = QLineEdit()
                        widget.setText(str(current_val))
                        tool_settings_layout.addRow(f"{setting_name}:", widget)
                        self.tool_settings_widgets[tool.name][setting_name] = widget
                    
                    # Add description label if available
                    if desc:
                        desc_label = QLabel(f"<i>{desc}</i>")
                        desc_label.setWordWrap(True)
                        tool_settings_layout.addRow("", desc_label)
                
                tools_layout.addWidget(tool_settings_widget)
        
    def update_url_visibility(self, provider_name: str):
        """Show only the URL field relevant to the current provider.
        ComfyUI URL is always visible.
        """
        ollama_label = self.form_layout.labelForField(self.ollama_url)
        lm_label = self.form_layout.labelForField(self.lm_studio_url)
        lm_native_label = self.form_layout.labelForField(self.lm_studio_native_url)

        is_ollama = (provider_name == "Ollama")
        # Keep legacy name handling for backwards compatibility
        is_lm = (provider_name == "LM Studio")
        is_lm_native = (provider_name == "LM Studio (Native SDK)") or is_lm

        # Toggle visibility for Ollama URL
        self.ollama_url.setVisible(is_ollama)
        if ollama_label:
            ollama_label.setVisible(is_ollama)

        # Toggle visibility for LM Studio URL
        self.lm_studio_url.setVisible(is_lm)
        if lm_label:
            lm_label.setVisible(is_lm)
        
        # Toggle visibility for LM Studio Native SDK URL
        self.lm_studio_native_url.setVisible(is_lm_native)
        if lm_native_label:
            lm_native_label.setVisible(is_lm_native)

    def create_advanced_tab(self):
        """Create the Advanced settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Warning label
        warning = QLabel(
            "⚠️ Advanced Settings - For troubleshooting only.\n"
            "Modifying these settings may affect LLM behavior."
        )
        warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 10px;")
        layout.addWidget(warning)

        # Structured Responses toggle
        structured_group = QGroupBox("Structured Responses (JSON Schema)")
        structured_layout = QVBoxLayout()
        structured_desc = QLabel(
            "Enable opt-in structured responses using JSON Schema. "
            "Currently supported for LM Studio (Native SDK) only. "
            "When enabled, you can choose a schema in chat advanced options."
        )
        structured_desc.setWordWrap(True)
        structured_layout.addWidget(structured_desc)

        self.structured_enabled_cb = QCheckBox("Enable structured responses")
        self.structured_enabled_cb.setChecked(bool(self.settings.value("structured_enabled", False, type=bool)))
        structured_layout.addWidget(self.structured_enabled_cb)
        structured_group.setLayout(structured_layout)
        layout.addWidget(structured_group)
        
        # Custom edit instructions
        instructions_group = QGroupBox("Custom Edit Instructions")
        instructions_layout = QVBoxLayout()
        
        instructions_label = QLabel(
            "Customize the instructions sent to the LLM for file editing (PATCH/UPDATE formats).\n"
            "Leave blank to use defaults. Changes apply immediately."
        )
        instructions_label.setWordWrap(True)
        instructions_layout.addWidget(instructions_label)
        
        self.custom_edit_instructions = QTextEdit()
        self.custom_edit_instructions.setPlaceholderText("Leave blank for default instructions...")
        self.custom_edit_instructions.setMinimumHeight(250)
        
        # Load custom instructions or set to default
        custom_text = self.settings.value("custom_edit_instructions", "")
        if custom_text:
            self.custom_edit_instructions.setPlainText(custom_text)
        else:
            # Show default instructions as placeholder
            default_instructions = self._get_default_edit_instructions()
            self.custom_edit_instructions.setPlaceholderText(default_instructions)
        
        instructions_layout.addWidget(self.custom_edit_instructions)
        
        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self.reset_edit_instructions)
        reset_layout.addWidget(reset_btn)
        instructions_layout.addLayout(reset_layout)
        
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        layout.addStretch()
        return tab
    
    def _get_default_edit_instructions(self):
        """Get the default edit instructions text."""
        return (
            "\n\n## Edit Formats\n"
            "Use PATCH for line-level edits or range replacements:\n"
            ":::PATCH path/to/file.md\n"
            "L42: old text => new text\n"
            "L20-L23:\n"
            "New content for lines 20-23...\n"
            "Multiple lines here...\n"
            ":::END:::\n"
            "\n"
            "Use UPDATE when replacing entire file or large sections:\n"
            ":::UPDATE path/to/file.md\n"
            "Complete new file content...\n"
            ":::END:::\n"
            "\n"
            "Image generation:\n"
            ":::GENERATE_IMAGE:::\n"
            "Prompt: Description...\n"
            ":::END:::\n"
            "\n"
            "CRITICAL RULES:\n"
            "- ALWAYS use :::PATCH::: or :::UPDATE::: directives for file edits\n"
            "- Output ONLY the directive blocks (:::PATCH...:::END:::)\n"
            "- Do NOT wrap directives in code fences (no ```text or ```patch)\n"
            "- Do NOT output edit: links or HTML anchors\n"
            "- Do NOT include reminders or instructions in your response\n"
            "- Do NOT include footnotes or citations unless specifically requested\n"
            "- Explanations can come AFTER the directive block\n"
            "- When editing selections repeatedly, continue using :::PATCH::: format for each edit\n"
        )
    
    def reset_edit_instructions(self):
        """Reset custom edit instructions to default."""
        default = self._get_default_edit_instructions()
        self.custom_edit_instructions.setPlainText(default)
    
    def on_provider_changed(self, provider_name: str):
        # Adjust URL visibility
        self.update_url_visibility(provider_name)

    def save_settings(self):
        self.settings.setValue("llm_provider", self.provider_combo.currentText())
        self.settings.setValue("ollama_url", self.ollama_url.text())
        self.settings.setValue("lm_studio_url", self.lm_studio_url.text())
        self.settings.setValue("lm_studio_native_url", self.lm_studio_native_url.text())
        self.settings.setValue("comfy_url", self.comfy_url.text())
        
        # Save font settings
        self.settings.setValue("editor_font_family", self.font_family_combo.currentFont().family())
        self.settings.setValue("editor_font_size", self.font_size_spin.value())
        
        # Save custom edit instructions
        custom_instructions = self.custom_edit_instructions.toPlainText().strip()
        self.settings.setValue("custom_edit_instructions", custom_instructions)

        # Save structured responses toggle
        self.settings.setValue("structured_enabled", bool(self.structured_enabled_cb.isChecked()))
        
        # Save default image folder
        folder_value = self.default_image_folder.text().strip()
        if not folder_value:
            folder_value = "assets/images"
        self.settings.setValue("default_image_folder", folder_value)

        # Persist project-specific configuration if a project is open
        if self.proj and self.proj.get_root_path():
            # Save tool configuration
            enabled = []
            for name, cb in self.tool_checkboxes.items():
                if cb.isEnabled() and cb.isChecked():
                    enabled.append(name)
            # If all available tools are checked, allow None (all)
            available_names = []
            for cls in AVAILABLE_TOOLS.values():
                try:
                    t = cls()
                except Exception:
                    continue
                if t.is_available():
                    available_names.append(t.name)
            if set(enabled) == set(available_names):
                self.proj.set_enabled_tools(None)
            else:
                self.proj.set_enabled_tools(enabled)
            
            # Collect per-tool settings
            tool_settings = {}
            for tool_name, settings_widgets in self.tool_settings_widgets.items():
                tool_config = {}
                for setting_name, widget in settings_widgets.items():
                    if isinstance(widget, QSpinBox):
                        tool_config[setting_name] = widget.value()
                    elif isinstance(widget, QCheckBox):
                        tool_config[setting_name] = widget.isChecked()
                    else:  # QLineEdit
                        tool_config[setting_name] = widget.text()
                if tool_config:
                    tool_settings[tool_name] = tool_config
            self.proj.set_tool_settings(tool_settings)

            # Persist editing preferences
            try:
                self.proj.set_editing_settings({
                    'apply_only_selection_default': bool(self.apply_only_selection_cb.isChecked()),
                })
            except Exception:
                pass
            
            # Save all project config (includes personas)
            self.proj.save_tool_config()
        
        self.accept()
