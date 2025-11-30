from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QFormLayout, QLineEdit, 
                               QScrollArea, QSplitter, QProgressBar, QMessageBox, QFileDialog, QPlainTextEdit)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from core.workflow_manager import WorkflowManager
from core.comfy_client import ComfyClient
import os

class ImageGenWorker(QThread):
    finished = Signal(list) # list of bytes
    error = Signal(str)

    def __init__(self, client, workflow):
        super().__init__()
        self.client = client
        self.workflow = workflow

    def run(self):
        try:
            images = self.client.generate_image(self.workflow)
            if images:
                self.finished.emit(images)
            else:
                self.error.emit("No images returned or generation failed.")
        except Exception as e:
            self.error.emit(str(e))

class ImageGenWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.workflow_manager = WorkflowManager()
        self.client = None # Initialized on generate
        
        self.layout = QVBoxLayout(self)
        
        # Top: Controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Workflow:"))
        self.workflow_combo = QComboBox()
        self.workflow_combo.addItems(self.workflow_manager.get_workflow_names())
        self.workflow_combo.currentTextChanged.connect(self.on_workflow_changed)
        controls_layout.addWidget(self.workflow_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_workflows)
        controls_layout.addWidget(self.refresh_btn)
        
        self.layout.addLayout(controls_layout)
        
        # Splitter: Form vs Preview
        splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(splitter)
        
        # Left: Dynamic Form
        form_container = QWidget()
        self.form_layout = QFormLayout(form_container)
        
        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)
        splitter.addWidget(scroll)
        
        # Right: Preview
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        
        self.image_label = QLabel("No Image Generated")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px dashed #666;")
        self.image_label.setMinimumSize(400, 400)
        preview_layout.addWidget(self.image_label)
        
        self.save_btn = QPushButton("Save to Project")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_image)
        preview_layout.addWidget(self.save_btn)
        
        splitter.addWidget(preview_container)
        splitter.setSizes([300, 600])
        
        # Bottom: Generate
        self.progress = QProgressBar()
        self.progress.hide()
        self.layout.addWidget(self.progress)
        
        self.generate_btn = QPushButton("Generate Image")
        self.generate_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        self.generate_btn.clicked.connect(self.generate)
        self.layout.addWidget(self.generate_btn)
        
        self.inputs = {} # placeholder -> widget
        self.current_image_data = None
        
        # Initial load
        if self.workflow_combo.count() > 0:
            self.on_workflow_changed(self.workflow_combo.currentText())
            
        self.project_path = ""

    def set_project_path(self, path):
        self.project_path = path

    def refresh_workflows(self):
        self.workflow_manager.reload_workflows()
        self.workflow_combo.clear()
        self.workflow_combo.addItems(self.workflow_manager.get_workflow_names())

    # ... (existing methods) ...

    def save_image(self):
        if not self.current_image_data:
            return
            
        # Ask where to save
        # Default to project assets if possible
        start_dir = self.project_path if self.project_path else os.getcwd()
        
        # Create assets/images folder if it exists in project
        if self.project_path:
            assets_dir = os.path.join(self.project_path, "assets")
            if os.path.exists(assets_dir):
                start_dir = assets_dir
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", os.path.join(start_dir, "generated.png"), "Images (*.png *.jpg)")
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(self.current_image_data)
                QMessageBox.information(self, "Success", f"Saved to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def on_workflow_changed(self, name):
        # Clear form
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.inputs = {}
        
        if not name:
            return

        placeholders = self.workflow_manager.get_placeholders(name)
        for p in placeholders:
            label = QLabel(p)
            
            if "PROMPT" in p:
                inp = QPlainTextEdit()
                inp.setMinimumHeight(100)
            else:
                inp = QLineEdit()
                
            self.form_layout.addRow(label, inp)
            self.inputs[p] = inp

    def generate(self):
        name = self.workflow_combo.currentText()
        if not name:
            return
            
        # Collect inputs
        values = {}
        for p, inp in self.inputs.items():
            if isinstance(inp, QPlainTextEdit):
                values[p] = inp.toPlainText()
            else:
                values[p] = inp.text()
            
        # Process workflow
        workflow = self.workflow_manager.process_workflow(name, values)
        if not workflow:
            QMessageBox.warning(self, "Error", "Failed to process workflow.")
            return

        # Init client
        url = self.settings.value("comfy_url", "http://127.0.0.1:8188")
        self.client = ComfyClient(base_url=url)
        
        # Start Worker
        self.progress.setRange(0, 0) # Indeterminate
        self.progress.show()
        self.generate_btn.setEnabled(False)
        self.image_label.setText("Generating...")
        
        self.worker = ImageGenWorker(self.client, workflow)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.start()

    def on_generation_finished(self, images):
        self.progress.hide()
        self.generate_btn.setEnabled(True)
        
        if images:
            self.current_image_data = images[0] # Just show first for now
            
            # Display
            pixmap = QPixmap()
            pixmap.loadFromData(self.current_image_data)
            self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.save_btn.setEnabled(True)
        else:
            self.image_label.setText("No images returned.")

    def on_generation_error(self, error):
        self.progress.hide()
        self.generate_btn.setEnabled(True)
        self.image_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Generation Error", error)

    def generate_from_agent(self, prompt, workflow_name=None):
        """Called by the agentic AI to generate images programmatically."""
        # 1. Select Workflow
        if workflow_name:
            index = self.workflow_combo.findText(workflow_name)
            if index >= 0:
                self.workflow_combo.setCurrentIndex(index)
            else:
                print(f"Warning: Workflow '{workflow_name}' not found. Using current.")
        
        # 2. Fill Prompt
        # Find the input widget corresponding to %PROMPT%
        prompt_key = None
        for key in self.inputs:
            if "PROMPT" in key:
                prompt_key = key
                break
        
        if prompt_key:
            widget = self.inputs[prompt_key]
            if isinstance(widget, QPlainTextEdit):
                widget.setPlainText(prompt)
            else:
                widget.setText(prompt)
        else:
            print("Warning: No %PROMPT% field found in current workflow.")
            
        # 3. Generate
        self.generate()

    def save_image(self):
        if not self.current_image_data:
            return
            
        # Ask where to save
        # Default to project assets if possible
        start_dir = self.project_path if self.project_path else os.getcwd()
        
        # Create assets/images folder if it exists in project
        if self.project_path:
            assets_dir = os.path.join(self.project_path, "assets")
            if not os.path.exists(assets_dir):
                 # Optional: create it? Let's just default to project root if assets doesn't exist
                 pass
            else:
                start_dir = assets_dir
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", os.path.join(start_dir, "generated.png"), "Images (*.png *.jpg)")
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(self.current_image_data)
                QMessageBox.information(self, "Success", f"Saved to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")
