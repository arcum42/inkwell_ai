from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QFileSystemModel, QHeaderView, QMenu, QInputDialog, QMessageBox, QFileDialog, QStyledItemDelegate
from PySide6.QtCore import QDir, Qt, QFileInfo, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QBrush
import os
import shutil


class IndexStatusDelegate(QStyledItemDelegate):
    """Custom delegate to draw index status indicators next to files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rag_engine = None
    
    def set_rag_engine(self, rag_engine):
        self.rag_engine = rag_engine
    
    def paint(self, painter, option, index):
        # Draw the default item
        super().paint(painter, option, index)
        
        # Only draw status for files, not directories
        model = index.model()
        if model.isDir(index):
            return
        
        file_path = model.filePath(index)
        if not file_path.endswith(('.md', '.txt')):
            return
        
        # Get status from RAG engine
        if not self.rag_engine:
            return
        
        status = self.rag_engine.get_file_index_status(file_path)
        if not status:
            return
        
        # Choose color based on status
        if status == 'indexed':
            color = QColor(0, 200, 0)  # Green
        elif status == 'needs_reindex':
            color = QColor(255, 165, 0)  # Orange
        else:  # not_indexed
            color = QColor(200, 0, 0)  # Red
        
        # Draw a small dot on the right side
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        
        # Position dot on the right edge
        dot_size = 6
        dot_x = option.rect.right() - dot_size - 4
        dot_y = option.rect.center().y() - (dot_size // 2)
        painter.drawEllipse(dot_x, dot_y, dot_size, dot_size)
        painter.restore()


class ProjectTreeView(QTreeView):
    moved = Signal(str, str)  # old_path, new_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        # Determine destination folder from drop position
        dest_index = self.indexAt(event.position().toPoint()) if hasattr(event, 'position') else self.indexAt(event.pos())
        model = self.model()
        if dest_index and dest_index.isValid():
            if model.isDir(dest_index):
                dest_folder = model.filePath(dest_index)
            else:
                dest_folder = os.path.dirname(model.filePath(dest_index))
        else:
            dest_folder = model.rootPath()

        # Extract source paths from mime data
        md = event.mimeData()
        urls = md.urls() if md and md.hasUrls() else []
        if not urls:
            event.ignore()
            return

        root_path = model.rootPath()

        # Validate destination is inside project
        try:
            if os.path.commonpath([dest_folder, root_path]) != root_path:
                QMessageBox.warning(self, "Invalid Drop", "Destination must be inside the project.")
                event.ignore()
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Drop", "Destination must be inside the project.")
            event.ignore()
            return

        moved_any = False
        for url in urls:
            src_path = url.toLocalFile()
            if not src_path:
                continue
            # Ensure source is inside project
            try:
                if os.path.commonpath([src_path, root_path]) != root_path:
                    continue
            except ValueError:
                continue
            # Build target path
            new_path = os.path.join(dest_folder, os.path.basename(src_path))
            if new_path == src_path:
                continue
            if os.path.exists(new_path):
                QMessageBox.warning(self, "Exists", f"{os.path.basename(new_path)} already exists at destination.")
                continue
            try:
                shutil.move(src_path, new_path)
                self.moved.emit(src_path, new_path)
                moved_any = True
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not move: {e}")

        if moved_any:
            event.acceptProposedAction()
        else:
            event.ignore()

class Sidebar(QWidget):
    file_renamed = Signal(str, str)  # old_path, new_path
    file_moved = Signal(str, str)    # old_path, new_path
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.model = QFileSystemModel()
        # Don't set root path immediately to avoid showing system root
        # self.model.setRootPath(QDir.rootPath())
        
        self.tree = ProjectTreeView()
        self.tree.setModel(self.model)
        # self.tree.setRootIndex(self.model.index(QDir.rootPath()))
        
        # Set up custom delegate for index status indicators
        self.delegate = IndexStatusDelegate(self.tree)
        self.tree.setItemDelegate(self.delegate)
        
        # Hide extra columns (Size, Type, Date Modified) - keep only Name
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setHeaderHidden(True)
        
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        
        # Allow model writes (rename via model etc.)
        self.model.setReadOnly(False)
        # Relay DnD moves to sidebar signal
        self.tree.moved.connect(lambda old, new: self.file_moved.emit(old, new))

        self.layout.addWidget(self.tree)
    
    def set_rag_engine(self, rag_engine):
        """Set the RAG engine for the delegate to check index status."""
        self.delegate.set_rag_engine(rag_engine)
    
    def update_file_status(self):
        """Force repaint to update file status indicators."""
        self.tree.viewport().update()

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
            rename_action = menu.addAction("Rename")
            move_action = menu.addAction("Move To…")
            delete_action = menu.addAction("Delete")
        else:
            rename_action = None
            move_action = None
            delete_action = None
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == new_file_action:
            self.create_new_file(index)
        elif action == new_folder_action:
            self.create_new_folder(index)
        elif rename_action and action == rename_action:
            self.rename_item(index)
        elif move_action and action == move_action:
            self.move_item(index)
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

    def rename_item(self, index):
        if not index.isValid():
            return
        old_path = self.model.filePath(index)
        dir_path = os.path.dirname(old_path)
        base = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=base)
        if not ok or not new_name:
            return
        new_name = new_name.strip()
        new_path = os.path.join(dir_path, new_name)
        if new_path == old_path:
            return
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Exists", "A file or folder with that name already exists.")
            return
        try:
            os.rename(old_path, new_path)
            self.file_renamed.emit(old_path, new_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not rename: {e}")

    def move_item(self, index):
        if not index.isValid():
            return
        old_path = self.model.filePath(index)
        root_path = self.model.rootPath()
        # Choose destination folder within project
        dest_folder = QFileDialog.getExistingDirectory(
            self,
            "Select destination folder",
            root_path,
            QFileDialog.ShowDirsOnly
        )
        if not dest_folder:
            return
        # Ensure destination is inside project
        try:
            if os.path.commonpath([dest_folder, root_path]) != root_path:
                QMessageBox.warning(self, "Invalid Folder", "Please choose a folder within the project.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Folder", "Please choose a valid folder within the project.")
            return
        # Build new path
        new_path = os.path.join(dest_folder, os.path.basename(old_path))
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Exists", "A file or folder with that name already exists at destination.")
            return
        try:
            shutil.move(old_path, new_path)
            self.file_moved.emit(old_path, new_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not move: {e}")

