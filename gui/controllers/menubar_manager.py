"""Menu bar and toolbar manager for MainWindow."""

from PySide6.QtWidgets import QMenuBar, QToolBar, QStyle
from PySide6.QtGui import QAction, QIcon, QKeySequence


class MenuBarManager:
    """Manages menu bar and toolbars for the main window."""
    
    def __init__(self, main_window):
        """Initialize menu bar manager.
        
        Args:
            main_window: The MainWindow instance
        """
        self.window = main_window
        self.menu_bar = main_window.menuBar()
        
    def create_menus(self):
        """Create all application menus."""
        self._create_file_menu()
        self._create_edit_menu()
        self._create_tools_menu()
        self._create_settings_menu()
        self._create_debug_menu()
        self._create_view_menu()
        
    def _create_file_menu(self):
        """Create File menu."""
        file_menu = self.menu_bar.addMenu("File")
        
        open_action = QAction("Open Project Folder", self.window)
        open_action.triggered.connect(self.window.open_project_dialog)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self.window)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.window.save_current_file)
        file_menu.addAction(save_action)
        
        close_project_action = QAction("Close Project", self.window)
        close_project_action.triggered.connect(self.window.close_project)
        file_menu.addAction(close_project_action)
        
        exit_action = QAction("Exit", self.window)
        exit_action.triggered.connect(self.window.close)
        file_menu.addAction(exit_action)
        
    def _create_edit_menu(self):
        """Create Edit menu."""
        edit_menu = self.menu_bar.addMenu("Edit")
        
        undo_action = QAction("Undo", self.window)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.window.editor.undo())
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self.window)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.window.editor.redo())
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction("Cut", self.window)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.window.editor.cut())
        edit_menu.addAction(cut_action)
        
        copy_action = QAction("Copy", self.window)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.window.editor.copy())
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("Paste", self.window)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.window.editor.paste())
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("Find & Replace...", self.window)
        find_action.setShortcut("Ctrl+H")
        find_action.triggered.connect(lambda: self.window.editor.show_search())
        edit_menu.addAction(find_action)
        
    def _create_tools_menu(self):
        """Create Tools menu with dialog-enabled tools."""
        from core.tools.registry import get_registry
        
        tools_menu = self.menu_bar.addMenu("Tools")
        self.tools_menu = tools_menu  # Store reference for later updates
        
        # Get all tools and filter for those with dialogs
        registry = get_registry()
        dialog_tools = []
        
        for tool in registry.get_all_tools():
            if tool and hasattr(tool, 'has_dialog') and tool.has_dialog():
                dialog_tools.append((tool.name, tool))
        
        # If no dialog tools, show a placeholder
        if not dialog_tools:
            placeholder = QAction("(No tools available)", self.window)
            placeholder.setEnabled(False)
            tools_menu.addAction(placeholder)
        else:
            # Add actions for each dialog-enabled tool
            for tool_name, tool in sorted(dialog_tools):
                action = QAction(tool_name, self.window)
                action.triggered.connect(lambda checked=False, t=tool: self.window.on_tool_dialog_triggered(t))
                tools_menu.addAction(action)
        
    def _create_settings_menu(self):
        """Create Settings menu."""
        settings_menu = self.menu_bar.addMenu("Settings")
        settings_action = QAction("Preferences...", self.window)
        settings_action.triggered.connect(self.window.open_settings_dialog)
        settings_menu.addAction(settings_action)

        model_mgr_action = QAction("Model Manager...", self.window)
        model_mgr_action.triggered.connect(self.window.open_model_manager)
        settings_menu.addAction(model_mgr_action)
        
        settings_menu.addSeparator()
        
        # Spell-checking toggle
        spell_check_action = QAction("Enable Spell Checking", self.window)
        spell_check_action.setCheckable(True)
        spell_check_action.setChecked(self.window.spell_checker.is_enabled())
        spell_check_action.triggered.connect(self._toggle_spell_checking)
        settings_menu.addAction(spell_check_action)
        
        # Manage custom dictionary
        dictionary_action = QAction("Manage Custom Dictionary...", self.window)
        dictionary_action.triggered.connect(self._open_dictionary_manager)
        settings_menu.addAction(dictionary_action)
    
    def _toggle_spell_checking(self, checked):
        """Toggle spell-checking on/off."""
        self.window.spell_checker.set_enabled(checked)
        self.window.settings.setValue("spell_check_enabled", checked)
    
    def _open_dictionary_manager(self):
        """Open custom dictionary management dialog."""
        # Import here to avoid circular imports
        from gui.dialogs.dictionary_dialog import DictionaryDialog
        
        dialog = DictionaryDialog(self.window.spell_checker, self.window)
        dialog.exec()
        
    def _create_debug_menu(self):
        """Create Debug menu."""
        debug_menu = self.menu_bar.addMenu("Debug")
        export_debug_action = QAction("Export Debug Log & Chat", self.window)
        export_debug_action.triggered.connect(self.window.export_debug_log)
        debug_menu.addAction(export_debug_action)
        
    def _create_view_menu(self):
        """Create View menu."""
        view_menu = self.menu_bar.addMenu("View")
        
        image_studio_action = QAction("Image Studio", self.window)
        image_studio_action.triggered.connect(self.window.open_image_studio)
        view_menu.addAction(image_studio_action)
        
        chat_history_action = QAction("Chat History...", self.window)
        chat_history_action.triggered.connect(self.window.open_chat_history)
        view_menu.addAction(chat_history_action)
        
    def create_toolbar(self):
        """Create main toolbar."""
        toolbar = self.window.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        style = self.window.style()
        
        # Save File
        self.window.save_act = QAction(style.standardIcon(QStyle.SP_DriveFDIcon), "Save", self.window)
        self.window.save_act.setStatusTip("Save current file")
        self.window.save_act.triggered.connect(self.window.save_current_file)
        self.window.save_act.setEnabled(False)
        toolbar.addAction(self.window.save_act)
        
        toolbar.addSeparator()

        # Undo File Change
        file_undo_act = QAction(QIcon.fromTheme("edit-undo"), "Undo File Change", self.window)
        if file_undo_act.icon().isNull():
            file_undo_act.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        file_undo_act.setStatusTip("Undo last file rename/move")
        file_undo_act.setShortcut(QKeySequence("Ctrl+Alt+Z"))
        file_undo_act.triggered.connect(self.window.undo_file_change)
        toolbar.addAction(file_undo_act)

        # Redo File Change
        file_redo_act = QAction(QIcon.fromTheme("edit-redo"), "Redo File Change", self.window)
        if file_redo_act.icon().isNull():
            file_redo_act.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        file_redo_act.setStatusTip("Redo last undone file rename/move")
        file_redo_act.setShortcut(QKeySequence("Ctrl+Alt+Y"))
        file_redo_act.triggered.connect(self.window.redo_file_change)
        toolbar.addAction(file_redo_act)
        
        # Open Project
        open_act = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "Open Project", self.window)
        open_act.setStatusTip("Open a project folder")
        open_act.triggered.connect(self.window.open_project_dialog)
        toolbar.addAction(open_act)
        
        # Close Project
        close_act = QAction(style.standardIcon(QStyle.SP_DialogCloseButton), "Close Project", self.window)
        close_act.setStatusTip("Close current project")
        close_act.triggered.connect(self.window.close_project)
        toolbar.addAction(close_act)
        
        toolbar.addSeparator()
        
        # Cut
        cut_act = QAction(QIcon.fromTheme("edit-cut"), "Cut", self.window)
        cut_act.triggered.connect(lambda: self.window.editor.cut())
        toolbar.addAction(cut_act)
        
        # Copy
        copy_act = QAction(QIcon.fromTheme("edit-copy"), "Copy", self.window)
        copy_act.triggered.connect(lambda: self.window.editor.copy())
        toolbar.addAction(copy_act)
        
        # Paste
        paste_act = QAction(QIcon.fromTheme("edit-paste"), "Paste", self.window)
        paste_act.triggered.connect(lambda: self.window.editor.paste())
        toolbar.addAction(paste_act)
        
        toolbar.addSeparator()
        
        # Undo
        undo_act = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Undo", self.window)
        undo_act.triggered.connect(lambda: self.window.editor.undo())
        toolbar.addAction(undo_act)
        
        # Redo
        redo_act = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Redo", self.window)
        redo_act.triggered.connect(lambda: self.window.editor.redo())
        toolbar.addAction(redo_act)
        
        toolbar.addSeparator()
        
        # Image Studio
        img_act = QAction(style.standardIcon(QStyle.SP_DesktopIcon), "Image Studio", self.window)
        img_act.setStatusTip("Open Image Studio")
        img_act.triggered.connect(self.window.open_image_studio)
        toolbar.addAction(img_act)
        
        # Settings
        settings_act = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "Settings", self.window)
        settings_act.triggered.connect(self.window.open_settings_dialog)
        toolbar.addAction(settings_act)
        
        self.window.toolbar = toolbar
        
    def create_format_toolbar(self):
        """Create formatting toolbar."""
        self.window.addToolBarBreak()  # Start new row
        format_toolbar = self.window.addToolBar("Formatting")
        format_toolbar.setMovable(False)
        
        # Bold
        bold_act = QAction(QIcon.fromTheme("format-text-bold"), "Bold", self.window)
        bold_act.triggered.connect(lambda: self.window.editor.format_bold())
        format_toolbar.addAction(bold_act)
        
        # Italic
        italic_act = QAction(QIcon.fromTheme("format-text-italic"), "Italic", self.window)
        italic_act.triggered.connect(lambda: self.window.editor.format_italic())
        format_toolbar.addAction(italic_act)
        
        # Code Block
        code_act = QAction(QIcon.fromTheme("format-text-code"), "Code Block", self.window) 
        if code_act.icon().isNull():
            code_act.setText("Code Block")
        code_act.triggered.connect(lambda: self.window.editor.format_code_block())
        format_toolbar.addAction(code_act)
        
        # Quote
        quote_act = QAction(QIcon.fromTheme("format-text-blockquote"), "Quote", self.window)
        if quote_act.icon().isNull():
            quote_act.setText("Quote")
        quote_act.triggered.connect(lambda: self.window.editor.format_quote())
        format_toolbar.addAction(quote_act)
        
        format_toolbar.addSeparator()
        
        # Headers
        h1_act = QAction("H1", self.window)
        h1_act.triggered.connect(lambda: self.window.editor.format_h1())
        format_toolbar.addAction(h1_act)
        
        h2_act = QAction("H2", self.window)
        h2_act.triggered.connect(lambda: self.window.editor.format_h2())
        format_toolbar.addAction(h2_act)
        
        h3_act = QAction("H3", self.window)
        h3_act.triggered.connect(lambda: self.window.editor.format_h3())
        format_toolbar.addAction(h3_act)
        
        format_toolbar.addSeparator()
        
        # Link
        link_act = QAction(QIcon.fromTheme("insert-link"), "Link", self.window)
        link_act.triggered.connect(lambda: self.window.editor.insert_link())
        format_toolbar.addAction(link_act)
        
        # Image
        image_act = QAction(QIcon.fromTheme("insert-image"), "Image", self.window)
        image_act.triggered.connect(lambda: self.window.editor.insert_image())
        format_toolbar.addAction(image_act)
        
        self.window.format_toolbar = format_toolbar
