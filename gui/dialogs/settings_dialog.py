from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QPushButton, QHBoxLayout
from PySide6.QtCore import QSettings
from core.llm_provider import OllamaProvider

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 350)
        
        self.settings = QSettings("InkwellAI", "InkwellAI")
        
        layout = QVBoxLayout(self)
        
        self.form_layout = QFormLayout()
        
        # LLM Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio"])
        current_provider = self.settings.value("llm_provider", "Ollama")
        self.provider_combo.setCurrentText(current_provider)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        self.form_layout.addRow("LLM Provider:", self.provider_combo)
        
        # Ollama URL
        self.ollama_url = QLineEdit()
        self.ollama_url.setText(self.settings.value("ollama_url", "http://localhost:11434"))
        self.form_layout.addRow("Ollama URL:", self.ollama_url)
        
        # Model Selection (Ollama)
        model_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True) # Allow typing custom model names
        current_model = self.settings.value("ollama_model", "llama3")
        self.model_combo.setCurrentText(current_model)
        model_layout.addWidget(self.model_combo)
        
        refresh_btn = QPushButton("Refresh Models")
        refresh_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(refresh_btn)
        
        self.form_layout.addRow("Ollama Model:", model_layout)
        
        # LM Studio URL
        self.lm_studio_url = QLineEdit()
        self.lm_studio_url.setText(self.settings.value("lm_studio_url", "http://localhost:1234"))
        self.form_layout.addRow("LM Studio URL:", self.lm_studio_url)
        
        # ComfyUI URL
        self.comfy_url = QLineEdit()
        self.comfy_url.setText(self.settings.value("comfy_url", "http://127.0.0.1:8188"))
        self.form_layout.addRow("ComfyUI URL:", self.comfy_url)

        # Default Image Save Folder (relative to project)
        self.default_image_folder = QLineEdit()
        self.default_image_folder.setPlaceholderText("assets/images")
        self.default_image_folder.setText(self.settings.value("default_image_folder", "assets/images"))
        self.form_layout.addRow("Default Image Folder:", self.default_image_folder)
        
        layout.addLayout(self.form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initial population for selected provider
        self.refresh_models()

        # Set URL visibility based on current provider
        self.update_url_visibility(current_provider)

    def update_url_visibility(self, provider_name: str):
        """Show only the URL field relevant to the current provider.
        ComfyUI URL is always visible.
        """
        ollama_label = self.form_layout.labelForField(self.ollama_url)
        lm_label = self.form_layout.labelForField(self.lm_studio_url)

        is_ollama = (provider_name == "Ollama")
        is_lm = (provider_name == "LM Studio")

        # Toggle visibility for Ollama URL
        self.ollama_url.setVisible(is_ollama)
        if ollama_label:
            ollama_label.setVisible(is_ollama)

        # Toggle visibility for LM Studio URL
        self.lm_studio_url.setVisible(is_lm)
        if lm_label:
            lm_label.setVisible(is_lm)

    def on_provider_changed(self, provider_name: str):
        # Adjust URL visibility
        self.update_url_visibility(provider_name)

        # Refresh model list automatically for selected provider
        self.refresh_models()

    def refresh_models(self):
        # Choose provider based on current selection
        provider_name = self.provider_combo.currentText()
        if provider_name == "Ollama":
            url = self.ollama_url.text()
            provider = OllamaProvider(base_url=url)
        else:
            url = self.lm_studio_url.text()
            from core.llm_provider import LMStudioProvider
            provider = LMStudioProvider(base_url=url)

        models = provider.list_models()
        if models:
            # Preserve current selection (raw model name if available)
            current_raw = self.model_combo.currentData()
            if current_raw is None:
                current_raw = self.model_combo.currentText()
            # Sanitize in case it contains an eye from previous display
            current_raw = current_raw.replace("👁️", "").strip()

            # Rebuild list with display names and userData = raw model name
            self.model_combo.clear()
            for m in models:
                display = f"{m} 👁️" if provider.is_vision_model(m) else m
                self.model_combo.addItem(display, m)

            # Restore selection by userData match; fallback to text
            idx = self.model_combo.findData(current_raw)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setCurrentText(current_raw)

    def save_settings(self):
        self.settings.setValue("llm_provider", self.provider_combo.currentText())
        self.settings.setValue("ollama_url", self.ollama_url.text())
        # Save the raw model name without the eye indicator
        raw_model = self.model_combo.currentData()
        if raw_model is None:
            raw_model = self.model_combo.currentText().replace("👁️", "").strip()
        self.settings.setValue("ollama_model", raw_model)
        self.settings.setValue("lm_studio_url", self.lm_studio_url.text())
        self.settings.setValue("comfy_url", self.comfy_url.text())
        # Save default image folder (relative to project)
        folder_value = self.default_image_folder.text().strip()
        if not folder_value:
            folder_value = "assets/images"
        self.settings.setValue("default_image_folder", folder_value)
        self.accept()
