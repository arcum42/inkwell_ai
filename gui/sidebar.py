from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QFileSystemModel, QHeaderView, QMenu, QInputDialog, QMessageBox, QFileDialog, QStyledItemDelegate, QScrollArea, QLabel, QToolBar, QApplication, QStyle
from PySide6.QtCore import QDir, Qt, QFileInfo, Signal, QRect, QSize, QAbstractItemModel, QModelIndex
from PySide6.QtGui import QPainter, QColor, QBrush, QIcon, QAction
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

class CollapsibleHeader(QWidget):
    """A clickable header that can expand/collapse a section."""
    toggled = Signal(bool)  # emits True when expanded, False when collapsed
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.is_expanded = True
        self.title = title
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        
        self.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        self.setCursor(Qt.PointingHandCursor)
        self.setMaximumHeight(30)
        
        # Header label with expand/collapse indicator
        self.label = QLabel(f"▼ {title}")
        font = self.label.font()
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet("color: #666; padding: 2px 4px;")
        layout.addWidget(self.label)
    
    def mousePressEvent(self, event):
        """Toggle expanded state on click."""
        self.is_expanded = not self.is_expanded
        self.label.setText(f"{'▼' if self.is_expanded else '▶'} {self.title}")
        self.toggled.emit(self.is_expanded)
    
    def set_expanded(self, expanded: bool):
        """Set the expanded state without emitting signal."""
        self.is_expanded = expanded
        self.label.setText(f"{'▼' if self.is_expanded else '▶'} {self.title}")


class ProjectSection(QWidget):
    """A collapsible section containing a project's file tree with header."""
    file_renamed = Signal(str, str)  # old_path, new_path
    file_moved = Signal(str, str)    # old_path, new_path
    file_double_clicked = Signal(str)  # file_path
    
    def __init__(self, project_name: str, root_path: str, parent_sidebar=None, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.root_path = root_path
        self.parent_sidebar = parent_sidebar
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create collapsible header
        self.header = CollapsibleHeader(project_name)
        self.header.toggled.connect(self._on_toggle_expanded)
        self.layout.addWidget(self.header)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet("QToolBar { border: none; border-bottom: 1px solid #ddd; padding: 2px; }")
        
        # Get standard icons from application style
        style = QApplication.instance().style()
        
        # New File
        new_file_act = QAction(style.standardIcon(QStyle.SP_FileIcon), "New File", self)
        new_file_act.setStatusTip("Create a new file")
        new_file_act.triggered.connect(lambda: self.create_new_file())
        self.toolbar.addAction(new_file_act)
        
        # New Folder
        new_folder_act = QAction(style.standardIcon(QStyle.SP_DirIcon), "New Folder", self)
        new_folder_act.setStatusTip("Create a new folder")
        new_folder_act.triggered.connect(lambda: self.create_new_folder())
        self.toolbar.addAction(new_folder_act)
        
        self.toolbar.addSeparator()
        
        # Rename
        rename_act = QAction(QIcon.fromTheme("edit-rename"), "Rename", self)
        if rename_act.icon().isNull():
            rename_act.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        rename_act.setStatusTip("Rename selected file/folder")
        rename_act.triggered.connect(lambda: self._on_toolbar_rename())
        self.toolbar.addAction(rename_act)
        
        # Delete
        delete_act = QAction(QIcon.fromTheme("edit-delete"), "Delete", self)
        if delete_act.icon().isNull():
            delete_act.setIcon(style.standardIcon(QStyle.SP_TrashIcon))
        delete_act.setStatusTip("Delete selected file/folder")
        delete_act.triggered.connect(lambda: self._on_toolbar_delete())
        self.toolbar.addAction(delete_act)
        
        self.layout.addWidget(self.toolbar)
        
        # Create model and tree for this project
        self.model = QFileSystemModel()
        self.tree = ProjectTreeView()
        self.tree.setModel(self.model)
        
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
        
        # Relay signals
        self.tree.moved.connect(lambda old, new: self.file_moved.emit(old, new))
        self.tree.doubleClicked.connect(self._on_tree_double_clicked)
        
        # Add tree with stretch
        self.layout.addWidget(self.tree, 1)
        
        # Set the root path
        self.set_root_path(root_path)
    
    def _on_toggle_expanded(self, is_expanded: bool):
        """Handle expand/collapse toggle."""
        self.tree.setVisible(is_expanded)
        # Adjust stretch factor so collapsed sections don't reserve space
        self.layout.setStretchFactor(self.tree, 1 if is_expanded else 0)
        # Notify parent to update layout stretch
        self.toggled = Signal(bool)
        # Emit custom signal that parent sidebar can catch
        if hasattr(self, 'parent_sidebar'):
            self.parent_sidebar._on_section_toggled(self, is_expanded)
    
    def _on_toolbar_rename(self):
        """Rename the currently selected item."""
        index = self.tree.currentIndex()
        if index.isValid():
            self.rename_item(index)
    
    def _on_toolbar_delete(self):
        """Delete the currently selected item."""
        index = self.tree.currentIndex()
        if index.isValid():
            self.delete_item(index)
    
    def _on_tree_double_clicked(self, index):
        """Relay double-click to parent with full file path."""
        if index.isValid():
            file_path = self.model.filePath(index)
            self.file_double_clicked.emit(file_path)
    
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

    def create_new_file(self, index=None):
        # If called from toolbar without index, use root path
        if index is None:
            target_dir = self.root_path
        else:
            target_dir = self.get_target_dir(index)
        name, ok = QInputDialog.getText(self, "New File", "Filename:")
        if ok and name:
            path = os.path.join(target_dir, name)
            try:
                with open(path, 'w') as f:
                    pass
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create file: {e}")

    def create_new_folder(self, index=None):
        # If called from toolbar without index, use root path
        if index is None:
            target_dir = self.root_path
        else:
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


class Sidebar(QWidget):
    """Main sidebar with collapsible file tree sections: Project and Assets."""
    file_renamed = Signal(str, str)  # old_path, new_path
    file_moved = Signal(str, str)    # old_path, new_path
    file_double_clicked = Signal(str)  # file_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Store project sections
        self.project_sections = {}  # section_name -> ProjectSection
        
        # Add stretch at the end to push sections to the top
        self.layout.addStretch()
    
    def add_project(self, project_name: str, root_path: str):
        """Add a collapsible project section to the sidebar.
        
        Args:
            project_name: Name of the section (e.g., "Project", "Inkwell Assets")
            root_path: Root path of the folder
        """
        if not os.path.isdir(root_path):
            print(f"Warning: {project_name} folder not found at {root_path}")
            return
        
        # Remove the stretch temporarily
        self.layout.removeItem(self.layout.itemAt(self.layout.count() - 1))
        
        # Format the display name
        if project_name == "Project":
            # Show "Project: folder_name"
            folder_name = os.path.basename(root_path.rstrip('/\\'))
            display_name = f"Project: {folder_name}"
        elif project_name == "Assets":
            # Use "Inkwell Assets" instead
            display_name = "Inkwell Assets"
        else:
            display_name = project_name
        
        # Create and add project section (with built-in collapsible header)
        section = ProjectSection(display_name, root_path, parent_sidebar=self)
        section.file_renamed.connect(self.file_renamed.emit)
        section.file_moved.connect(self.file_moved.emit)
        section.file_double_clicked.connect(self.file_double_clicked.emit)
        
        # Add section with stretch=1 so expanded sections grow to fill space
        self.layout.addWidget(section, 1)
        
        # Add stretch back at the end to keep sections at the top when both collapsed
        self.layout.addStretch()
        
        self.project_sections[project_name] = section
    
    def _on_section_toggled(self, section: 'ProjectSection', is_expanded: bool):
        """Handle a section being expanded or collapsed."""
        # Update the section's stretch factor based on expansion state
        self.layout.setStretchFactor(section, 1 if is_expanded else 0)
    
    def remove_project(self, project_name: str):
        """Remove a project section from the sidebar."""
        if project_name in self.project_sections:
            section = self.project_sections.pop(project_name)
            # Find and remove the section and its header from the layout
            for i in range(self.layout.count() - 1, -1, -1):
                widget = self.layout.itemAt(i).widget()
                if widget == section:
                    self.layout.removeWidget(section)
                    section.deleteLater()
                    # Also remove header (the item before it if it's a label)
                    if i > 0:
                        prev_widget = self.layout.itemAt(i - 1).widget()
                        if isinstance(prev_widget, QLabel) and prev_widget.text() == project_name:
                            self.layout.removeWidget(prev_widget)
                            prev_widget.deleteLater()
                    break
    
    def get_project_section(self, project_name: str):
        """Get a project section by name."""
        return self.project_sections.get(project_name)
    
    def set_rag_engine(self, rag_engine, project_name: str = "Project"):
        """Set the RAG engine for a specific project section."""
        if project_name in self.project_sections:
            self.project_sections[project_name].set_rag_engine(rag_engine)
    
    def update_file_status(self, project_name: str = "Project"):
        """Force repaint to update file status indicators."""
        if project_name in self.project_sections:
            self.project_sections[project_name].update_file_status()

    def set_root_path(self, path):
        """Updates the tree view to show the specified path (backward compatibility)."""
        if "Project" in self.project_sections:
            self.project_sections["Project"].set_root_path(path)
    
    @property
    def model(self):
        """Backward compatibility: return main project model."""
        if "Project" in self.project_sections:
            return self.project_sections["Project"].model
        return None
    
    @property
    def tree(self):
        """Backward compatibility: return main project tree."""
        if "Project" in self.project_sections:
            return self.project_sections["Project"].tree
        return None
    
    # Backward compatibility methods
    def create_new_file(self, index):
        """Delegate to Project section."""
        if "Project" in self.project_sections:
            self.project_sections["Project"].create_new_file(index)
    
    def create_new_folder(self, index):
        """Delegate to Project section."""
        if "Project" in self.project_sections:
            self.project_sections["Project"].create_new_folder(index)
    
    def rename_item(self, index):
        """Delegate to Project section."""
        if "Project" in self.project_sections:
            self.project_sections["Project"].rename_item(index)
    
    def move_item(self, index):
        """Delegate to Project section."""
        if "Project" in self.project_sections:
            self.project_sections["Project"].move_item(index)

