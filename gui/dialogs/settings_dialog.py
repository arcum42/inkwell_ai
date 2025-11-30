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
        
        form_layout = QFormLayout()
        
        # LLM Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio"])
        current_provider = self.settings.value("llm_provider", "Ollama")
        self.provider_combo.setCurrentText(current_provider)
        form_layout.addRow("LLM Provider:", self.provider_combo)
        
        # Ollama URL
        self.ollama_url = QLineEdit()
        self.ollama_url.setText(self.settings.value("ollama_url", "http://localhost:11434"))
        form_layout.addRow("Ollama URL:", self.ollama_url)
        
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
        
        form_layout.addRow("Ollama Model:", model_layout)
        
        # LM Studio URL
        self.lm_studio_url = QLineEdit()
        self.lm_studio_url.setText(self.settings.value("lm_studio_url", "http://localhost:1234"))
        form_layout.addRow("LM Studio URL:", self.lm_studio_url)
        
        # ComfyUI URL
        self.comfy_url = QLineEdit()
        self.comfy_url.setText(self.settings.value("comfy_url", "http://127.0.0.1:8188"))
        form_layout.addRow("ComfyUI URL:", self.comfy_url)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initial population if Ollama
        if current_provider == "Ollama":
            self.refresh_models()

    def refresh_models(self):
        url = self.ollama_url.text()
        provider = OllamaProvider(base_url=url)
        models = provider.list_models()
        if models:
            current = self.model_combo.currentText()
            self.model_combo.clear()
            self.model_combo.addItems(models)
            self.model_combo.setCurrentText(current)

    def save_settings(self):
        self.settings.setValue("llm_provider", self.provider_combo.currentText())
        self.settings.setValue("ollama_url", self.ollama_url.text())
        self.settings.setValue("ollama_model", self.model_combo.currentText())
        self.settings.setValue("lm_studio_url", self.lm_studio_url.text())
        self.settings.setValue("comfy_url", self.comfy_url.text())
        self.accept()
