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
    def __init__(self, results, project_path, parent=None, on_next_page=None, on_prev_page=None, current_page=1, has_search_context=False):
        super().__init__(parent)
        self.setWindowTitle("Select Image")
        self.resize(800, 600)
        self.results = results # list of dicts with 'image', 'title'
        self.project_path = project_path
        self.selected_indices = set()
        self.saved_paths = []
        self.on_next_page = on_next_page
        self.on_prev_page = on_prev_page
        self.current_page = current_page
        self.has_search_context = has_search_context
        
        self.layout = QVBoxLayout(self)
        
        # Page info label (if pagination available)
        if has_search_context:
            self.page_label = QLabel(f"Page {current_page}")
            self.page_label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(self.page_label)
        
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
            
        # Filename and pagination controls
        controls_layout = QVBoxLayout()
        
        # Pagination buttons (if available)
        if has_search_context:
            pagination_layout = QHBoxLayout()
            
            prev_btn = QPushButton("← Previous Page")
            prev_btn.clicked.connect(self.on_prev_clicked)
            if current_page <= 1:
                prev_btn.setEnabled(False)
            pagination_layout.addWidget(prev_btn)
            
            pagination_layout.addStretch()
            
            next_btn = QPushButton("Next Page →")
            next_btn.clicked.connect(self.on_next_clicked)
            pagination_layout.addWidget(next_btn)
            
            controls_layout.addLayout(pagination_layout)
        
        # Filename input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Save as:"))
        self.filename_input = QLineEdit("image.jpg")
        input_layout.addWidget(self.filename_input)
        
        save_btn = QPushButton("Save Selected")
        save_btn.clicked.connect(self.save_image)
        input_layout.addWidget(save_btn)
        
        controls_layout.addLayout(input_layout)
        self.layout.addLayout(controls_layout)
        
    def on_prev_clicked(self):
        """Handle previous page button click."""
        if self.on_prev_page:
            self.reject()  # Close dialog to trigger pagination
            self.on_prev_page()
    
    def on_next_clicked(self):
        """Handle next page button click."""
        if self.on_next_page:
            self.reject()  # Close dialog to trigger pagination
            self.on_next_page()
        
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
                
                # Write tags/description to a companion .txt file
                try:
                    base, _ext = os.path.splitext(target_path)
                    txt_path = base + ".txt"
                    tags = self.results[idx].get('tags') or []
                    if isinstance(tags, list):
                        tag_str = ", ".join([t for t in tags if isinstance(t, str)])
                    else:
                        tag_str = ""
                    desc = self.results[idx].get('description') or ""
                    src = self.results[idx].get('source_url') or ""
                    uploader = self.results[idx].get('uploader') or ""
                    lines = []
                    if tag_str:
                        lines.append(f"Tags: {tag_str}")
                    if uploader:
                        lines.append(f"Uploader: {uploader}")
                    if src:
                        lines.append(f"Source: {src}")
                    if desc:
                        lines.append("")
                        lines.append("Description:")
                        lines.append(desc)
                    # Ensure there's at least tags line; write empty file otherwise
                    with open(txt_path, 'w', encoding='utf-8') as tf:
                        tf.write("\n".join(lines))
                except Exception as e:
                    # Non-fatal; image saved successfully
                    print(f"Warning: Failed to write tags file for {target_path}: {e}")

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
