from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QFileSystemModel, QHeaderView, QMenu, QInputDialog, QMessageBox
from PySide6.QtCore import QDir, Qt, QFileInfo
import os

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.model = QFileSystemModel()
        # Don't set root path immediately to avoid showing system root
        # self.model.setRootPath(QDir.rootPath())
        
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        # self.tree.setRootIndex(self.model.index(QDir.rootPath()))
        
        # Hide extra columns (Size, Type, Date Modified) - keep only Name
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setHeaderHidden(True)
        
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        
        self.layout.addWidget(self.tree)

    def set_root_path(self, path):
        """Updates the tree view to show the specified path."""
        self.model.setRootPath(path)
        self.tree.setRootIndex(self.model.index(path))

    def open_context_menu(self, position):
        index = self.tree.indexAt(position)
        
        menu = QMenu()
        new_file_action = menu.addAction("New File")
        new_folder_action = menu.addAction("New Folder")
        menu.addSeparator()
        
        # Only show delete if we clicked on a valid item
        if index.isValid():
            delete_action = menu.addAction("Delete")
        else:
            delete_action = None
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == new_file_action:
            self.create_new_file(index)
        elif action == new_folder_action:
            self.create_new_folder(index)
        elif delete_action and action == delete_action:
            self.delete_item(index)

    def get_target_dir(self, index):
        if not index.isValid():
            return self.model.rootPath()
        if self.model.isDir(index):
            return self.model.filePath(index)
        else:
            return os.path.dirname(self.model.filePath(index))

    def create_new_file(self, index):
        target_dir = self.get_target_dir(index)
        name, ok = QInputDialog.getText(self, "New File", "Filename:")
        if ok and name:
            path = os.path.join(target_dir, name)
            try:
                with open(path, 'w') as f:
                    pass
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create file: {e}")

    def create_new_folder(self, index):
        target_dir = self.get_target_dir(index)
        name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and name:
            path = os.path.join(target_dir, name)
            try:
                os.mkdir(path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create folder: {e}")

    def delete_item(self, index):
        path = self.model.filePath(index)
        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {os.path.basename(path)}?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                if self.model.isDir(index):
                    # QFileSystemModel doesn't have recursive delete built-in easily accessible via model
                    # Use QDir or os
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete: {e}")

