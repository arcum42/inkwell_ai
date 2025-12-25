"""Image viewer widget."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

class ImageViewerWidget(QWidget):
    """Widget for displaying images."""
    
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        scroll.setWidget(self.image_label)
        
        self.load_image()
        
    def load_image(self):
        pixmap = QPixmap(self.file_path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("Failed to load image")
