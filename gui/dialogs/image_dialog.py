from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QFileDialog
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread, Signal
import requests
import os

class ImageDownloader(QThread):
    loaded = Signal(int, bytes) # index, data

    def __init__(self, urls):
        super().__init__()
        self.urls = urls

    def run(self):
        for i, url in enumerate(self.urls):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    self.loaded.emit(i, response.content)
            except:
                pass

class ImageSelectionDialog(QDialog):
    def __init__(self, results, project_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Image")
        self.resize(800, 600)
        self.results = results # list of dicts with 'image', 'title'
        self.project_path = project_path
        self.selected_indices = set()
        self.saved_paths = []
        
        self.layout = QVBoxLayout(self)
        
        # Grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        scroll.setWidget(self.grid_widget)
        self.layout.addWidget(scroll)
        
        # Selection widgets dict: index -> (label, overlay_btn)
        self.image_widgets = {}
        
        # Load thumbnails
        # We use the full image url because thumbnails often have issues or are missing in search results sometimes, 
        # but optimally we should use 'thumbnail' if available. 
        # DDG search usually returns 'thumbnail'.
        urls = [r.get('thumbnail', r.get('image')) for r in results]
        self.downloader = ImageDownloader(urls)
        self.downloader.loaded.connect(self.on_image_loaded)
        self.downloader.start()
        
        # Create placeholders
        for i in range(len(results)):
            lbl = QLabel("Loading...")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(200, 200)
            lbl.setStyleSheet("border: 1px solid gray; background-color: #eee;")
            
            # Make clickable
            # We wrap in a widget to handle clicking
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(0,0,0,0)
            vbox.addWidget(lbl)
            
            btn = QPushButton("Select/Deselect")
            btn.clicked.connect(lambda checked=False, idx=i: self.toggle_image(idx))
            vbox.addWidget(btn)
            
            self.grid_layout.addWidget(container, i // 3, i % 3)
            self.image_widgets[i] = lbl
            
        # Filename input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Save as:"))
        self.filename_input = QLineEdit("image.jpg")
        input_layout.addWidget(self.filename_input)
        
        save_btn = QPushButton("Save Selected")
        save_btn.clicked.connect(self.save_image)
        input_layout.addWidget(save_btn)
        
        self.layout.addLayout(input_layout)
        
    def on_image_loaded(self, index, data):
        if index in self.image_widgets:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.image_widgets[index].setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.image_widgets[index].setText("") # Remove text
            
    def toggle_image(self, index):
        if index in self.selected_indices:
            self.selected_indices.remove(index)
            self.image_widgets[index].setStyleSheet("border: 1px solid gray; background-color: #eee;")
        else:
            self.selected_indices.add(index)
            self.image_widgets[index].setStyleSheet("border: 3px solid #007bff; background-color: #e6f2ff;")
            
        # Update filename input logic
        if len(self.selected_indices) == 1:
            idx = list(self.selected_indices)[0]
            title = self.results[idx].get('title', 'image')
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).strip()
            safe_title = safe_title.replace(' ', '_')[:20]
            self.filename_input.setText(f"{safe_title}.jpg")
            self.filename_input.setEnabled(True)
        elif len(self.selected_indices) > 1:
            self.filename_input.setText(f"Wait... Saving {len(self.selected_indices)} images")
            self.filename_input.setEnabled(False)
        else:
            self.filename_input.setText("image.jpg")
            self.filename_input.setEnabled(True)
        
    def save_image(self):
        if not self.selected_indices:
            QMessageBox.warning(self, "Error", "Please select at least one image.")
            return
            
        saved_count = 0
        errors = 0
        
        # If single image, use valid input
        if len(self.selected_indices) == 1:
            target_filename = self.filename_input.text()
            if not target_filename: return
            # We treat this specially loop below
            pass
            
        for idx in self.selected_indices:
            try:
                if len(self.selected_indices) == 1:
                    filename = self.filename_input.text()
                else:
                    # Generate filename from title
                    title = self.results[idx].get('title', 'image')
                    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).strip()
                    safe_title = safe_title.replace(' ', '_')[:20]
                    # Ensure unique
                    base = safe_title
                    counter = 1
                    filename = f"{base}.jpg"
                    while os.path.exists(os.path.join(self.project_path, filename)):
                        filename = f"{base}_{counter}.jpg"
                        counter += 1
            
                target_path = os.path.join(self.project_path, filename)
                
                # Download
                url = self.results[idx].get('image')
                if not url: continue
                
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                with open(target_path, 'wb') as f:
                    f.write(response.content)
                
                self.saved_paths.append(target_path)
                saved_count += 1
            except Exception as e:
                errors += 1
                print(f"Error saving image {idx}: {e}")
        
        if saved_count > 0:
            if errors > 0:
                QMessageBox.warning(self, "Partial Success", f"Saved {saved_count} images. {errors} failed.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save selected images.")

    def get_saved_paths(self):
        return self.saved_paths
