"""Batch diff dialog for reviewing multiple file edits.

Allows users to:
- See all proposed edits in a single dialog
- Enable/disable individual files
- Preview diffs for each file
- Apply selected or all changes
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextBrowser,
    QDialogButtonBox, QCheckBox, QStackedWidget, QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QFont
import difflib
import markdown
import html as _html

from core.diff_engine import EditBatch, FileEdit


class FileListItem(QWidget):
    """Custom widget for file list item with checkbox and stats."""
    
    toggled = Signal(str, bool)  # (file_path, enabled)
    
    def __init__(self, edit: FileEdit, parent=None):
        super().__init__(parent)
        self.edit = edit
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(edit.enabled)
        self.checkbox.toggled.connect(lambda checked: self.toggled.emit(edit.file_path, checked))
        layout.addWidget(self.checkbox)
        
        # File path label
        self.label = QLabel(edit.file_path)
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        # Stats label
        stats = edit.get_summary()
        self.stats_label = QLabel(stats)
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.stats_label)


class DiffPanel(QWidget):
    """Panel showing current and proposed content with preview toggle."""
    
    def __init__(self, title: str, content: str, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with toggle
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch()
        
        # Only show preview toggle for markdown files
        if file_path.endswith('.md'):
            self.toggle_btn = QPushButton("Show Preview")
            self.toggle_btn.setCheckable(True)
            self.toggle_btn.clicked.connect(self.toggle_view)
            header_layout.addWidget(self.toggle_btn)
        else:
            self.toggle_btn = None
        
        layout.addLayout(header_layout)
        
        # Stack for text/preview views
        self.stack = QStackedWidget()
        
        # Text view
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(content if content else "")
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)  # Horizontal scroll
        self.stack.addWidget(self.text_edit)
        
        # Preview view (for markdown)
        self.preview = QTextBrowser()
        if content and file_path.endswith('.md'):
            html = markdown.markdown(content, extensions=['fenced_code', 'tables'])
            self.preview.setHtml(html)
        
        # Match palette for dark mode
        pal = self.preview.palette()
        self.preview.setStyleSheet(
            f"QTextBrowser {{ background: {pal.color(QPalette.Base).name()}; "
            f"color: {pal.color(QPalette.Text).name()}; }}"
        )
        self.stack.addWidget(self.preview)
        
        layout.addWidget(self.stack)
    
    def toggle_view(self):
        """Toggle between text and preview modes."""
        if self.toggle_btn and self.toggle_btn.isChecked():
            self.toggle_btn.setText("Show Text")
            self.stack.setCurrentIndex(1)
        elif self.toggle_btn:
            self.toggle_btn.setText("Show Preview")
            self.stack.setCurrentIndex(0)


class BatchDiffDialog(QDialog):
    """Dialog for reviewing multiple file edits in batch.
    
    Features:
    - Sidebar with checkbox list of all files
    - Diff viewer for selected file
    - Enable/disable individual files
    - Apply selected or all changes
    """
    
    def __init__(self, batch: EditBatch, parent=None):
        super().__init__(parent)
        self.batch = batch
        self.current_edit_index = 0
        self.wrap_lines = True  # Default: wrap enabled
        self.view_mode = 'side-by-side'  # 'side-by-side' or 'unified'
        self.current_edit = None  # Track current edit for nav
        self.hunk_positions = []  # Track changed line positions
        
        self.setWindowTitle(f"Review Changes")
        self.resize(1400, 800)
        
        self._setup_ui()
        self._populate_file_list()
        
        # Select first file if available
        if self.batch.edits:
            self.file_list.setCurrentRow(0)
            self._show_diff_for_edit(self.batch.edits[0])
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header with summary (compact)
        header_container = QWidget()
        header_container.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum))
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        files_affected = self.batch.total_files_affected()
        total_edits = len(self.batch.edits)
        
        title_label = QLabel(f"Review {total_edits} Changes to {files_affected} Files")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        # Show summary if available
        if self.batch.summary:
            summary_label = QLabel(self.batch.summary)
            summary_label.setWordWrap(True)
            summary_label.setStyleSheet("color: #666; margin-bottom: 8px;")
            header_layout.addWidget(summary_label)
        
        # Stats label
        self.stats_label = QLabel()
        self._update_stats_label()
        header_layout.addWidget(self.stats_label)
        
        layout.addWidget(header_container)
        
        # Main splitter: left sidebar + right content
        main_splitter = QSplitter(Qt.Horizontal)
        # Ensure splitter consumes remaining space
        layout.setStretchFactor = getattr(layout, 'setStretch', None)
        if layout.setStretchFactor:
            layout.setStretch(0, 0)  # header compact
            layout.setStretch(1, 1)  # splitter expands
        
        # Left sidebar: file list
        sidebar = self._create_sidebar()
        main_splitter.addWidget(sidebar)
        
        # Right side: diff viewer
        self.diff_container = QWidget()
        self.diff_layout = QVBoxLayout(self.diff_container)
        self.diff_layout.setContentsMargins(0, 0, 0, 0)
        
        # Placeholder for diff view
        self.diff_viewer_widget = QWidget()
        self.diff_layout.addWidget(self.diff_viewer_widget)
        
        main_splitter.addWidget(self.diff_container)
        
        # Set splitter sizes: 30% sidebar, 70% content
        main_splitter.setSizes([420, 980])
        
        layout.addWidget(main_splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        button_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self._select_none)
        button_layout.addWidget(self.select_none_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox()
        self.apply_selected_btn = button_box.addButton("Apply Selected", QDialogButtonBox.AcceptRole)
        self.apply_all_btn = button_box.addButton("Apply All", QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton(QDialogButtonBox.Cancel)
        
        self.apply_selected_btn.clicked.connect(self.accept)
        self.apply_all_btn.clicked.connect(self._apply_all_and_accept)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def _create_sidebar(self) -> QWidget:
        """Create the file list sidebar."""
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        files_label = QLabel("Files to Edit:")
        files_label.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        sidebar_layout.addWidget(files_label)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        sidebar_layout.addWidget(self.file_list)
        
        return sidebar
    
    def _populate_file_list(self):
        """Populate the file list with edits from batch."""
        self.file_list.clear()
        
        for edit in self.batch.edits:
            item = QListWidgetItem(self.file_list)
            item_widget = FileListItem(edit)
            item_widget.toggled.connect(self._on_file_toggled)
            
            # Set item size to fit widget
            item.setSizeHint(item_widget.sizeHint())
            
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, item_widget)
    
    def _on_file_selected(self, row: int):
        """Handle file selection in list."""
        if 0 <= row < len(self.batch.edits):
            edit = self.batch.edits[row]
            self._show_diff_for_edit(edit)
    
    def _on_file_toggled(self, file_path: str, enabled: bool):
        """Handle checkbox toggle for a file."""
        # Update edit enabled state
        for edit in self.batch.edits:
            if edit.file_path == file_path:
                edit.enabled = enabled
        
        self._update_stats_label()
    
    def _show_diff_for_edit(self, edit: FileEdit):
        """Show diff viewer for selected edit."""
        # Clear existing diff viewer
        if self.diff_viewer_widget:
            self.diff_layout.removeWidget(self.diff_viewer_widget)
            self.diff_viewer_widget.deleteLater()
        
        # Create new diff viewer
        self.diff_viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(self.diff_viewer_widget)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        # File info header
        header = QLabel(f"<b>File:</b> {edit.file_path}")
        viewer_layout.addWidget(header)
        
        # Edit type and stats
        info = QLabel(f"<b>Type:</b> {edit.edit_type.capitalize()} | <b>Changes:</b> {edit.get_summary()}")
        info.setStyleSheet("color: #666; margin-bottom: 8px;")
        viewer_layout.addWidget(info)
        
        # Show explanation if available
        if edit.metadata.get('explanation'):
            exp_label = QLabel(f"<i>{edit.metadata['explanation']}</i>")
            exp_label.setWordWrap(True)
            exp_label.setStyleSheet("color: #888; margin-bottom: 8px;")
            viewer_layout.addWidget(exp_label)
        
        # Controls row: wrap toggle, view mode, prev/next nav
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 4, 0, 4)
        
        # Wrap toggle
        self.wrap_btn = QPushButton("Wrap Lines" if self.wrap_lines else "No Wrap")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(self.wrap_lines)
        self.wrap_btn.clicked.connect(self._toggle_wrap)
        self.wrap_btn.setMaximumWidth(100)
        controls_layout.addWidget(self.wrap_btn)
        
        # View mode toggle
        self.view_mode_btn = QPushButton("Switch to Unified" if self.view_mode == 'side-by-side' else "Switch to Side-by-Side")
        self.view_mode_btn.clicked.connect(self._toggle_view_mode)
        self.view_mode_btn.setMaximumWidth(150)
        controls_layout.addWidget(self.view_mode_btn)
        
        controls_layout.addStretch()
        
        # Prev/Next navigation
        self.prev_btn = QPushButton("← Prev Change")
        self.prev_btn.clicked.connect(self._goto_prev_change)
        self.prev_btn.setMaximumWidth(120)
        controls_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next Change →")
        self.next_btn.clicked.connect(self._goto_next_change)
        self.next_btn.setMaximumWidth(120)
        controls_layout.addWidget(self.next_btn)
        
        viewer_layout.addLayout(controls_layout)
        
        # Store current edit and create view
        self.current_edit = edit
        self.diff_view = QTextBrowser()
        self.diff_view.setOpenExternalLinks(False)
        self.diff_view.setOpenLinks(False)
        pal = self.diff_view.palette()
        self.diff_view.setStyleSheet(
            f"QTextBrowser {{ font-family: monospace; "
            f"background: {pal.color(QPalette.Base).name()}; "
            f"color: {pal.color(QPalette.Text).name()}; }}"
        )
        
        # Render diff based on current mode
        self._refresh_diff_view(edit)
        viewer_layout.addWidget(self.diff_view)
        
        self.diff_layout.addWidget(self.diff_viewer_widget)
    
    def _refresh_diff_view(self, edit: FileEdit):
        """Regenerate diff HTML based on current wrap and view mode settings."""
        if self.view_mode == 'side-by-side':
            html = self._build_side_by_side_html(
                edit.old_content or "",
                edit.new_content,
                edit.file_path,
                wrap=self.wrap_lines
            )
        else:  # unified
            html = self._build_unified_html(
                edit.old_content or "",
                edit.new_content,
                edit.file_path,
                wrap=self.wrap_lines
            )
        self.diff_view.setHtml(html)
    
    def _toggle_wrap(self, checked: bool):
        """Toggle line wrapping."""
        self.wrap_lines = checked
        self.wrap_btn.setText("Wrap Lines" if checked else "No Wrap")
        if self.current_edit:
            self._refresh_diff_view(self.current_edit)
    
    def _toggle_view_mode(self):
        """Toggle between side-by-side and unified views."""
        self.view_mode = 'unified' if self.view_mode == 'side-by-side' else 'side-by-side'
        self.view_mode_btn.setText(
            "Switch to Unified" if self.view_mode == 'side-by-side' else "Switch to Side-by-Side"
        )
        if self.current_edit:
            self._refresh_diff_view(self.current_edit)
    
    def _goto_prev_change(self):
        """Navigate to the previous change."""
        if not self.hunk_positions:
            return
        # Scroll up to previous hunk
        cursor = self.diff_view.textCursor()
        current_pos = cursor.position()
        for hunk_pos in reversed(self.hunk_positions):
            if hunk_pos < current_pos:
                cursor.setPosition(hunk_pos)
                self.diff_view.setTextCursor(cursor)
                self.diff_view.ensureCursorVisible()
                return
    
    def _goto_next_change(self):
        """Navigate to the next change."""
        if not self.hunk_positions:
            return
        # Scroll down to next hunk
        cursor = self.diff_view.textCursor()
        current_pos = cursor.position()
        for hunk_pos in self.hunk_positions:
            if hunk_pos > current_pos:
                cursor.setPosition(hunk_pos)
                self.diff_view.setTextCursor(cursor)
                self.diff_view.ensureCursorVisible()
                return
    
    def _build_diff_html(self, old_content: str, new_content: str, file_path: str) -> str:
        """Build HTML diff view with improved readability.
        
        Args:
            old_content: Original content
            new_content: Proposed content
            file_path: File path (for context)
            
        Returns:
            HTML string with diff
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        # Use difflib with NO wrapping (wrapcolumn=None would be ideal, but not supported)
        # Instead, use a very large wrapcolumn to effectively disable wrapping
        diff = difflib.HtmlDiff(wrapcolumn=99999).make_table(
            old_lines,
            new_lines,
            fromdesc="Current",
            todesc="Proposed",
            context=True,
            numlines=3,
        )
        
        # Add custom styling
        pal = self.palette()
        base = pal.color(QPalette.Base).name()
        text = pal.color(QPalette.Text).name()
        header = pal.color(QPalette.AlternateBase).name()
        
        # Dark mode detection
        is_dark_mode = pal.color(QPalette.Text).lightness() > 128
        
        # Colors for diff lines
        if is_dark_mode:
                add = "#0d4a0d"  # Darker green for additions
                sub = "#5c1a1a"  # Darker red for deletions
                chg = "#5c4d0d"  # Darker yellow for changes
                add_line = "#1a6b1a"  # Lighter green for full line additions
                sub_line = "#7a2424"  # Lighter red for full line deletions
        else:
                add = "#d4ffd4"  # Light green for additions
                sub = "#ffd4d4"  # Light red for deletions
                chg = "#ffffb3"  # Light yellow for changes
                add_line = "#ccffcc"  # Even lighter green for full line additions
                sub_line = "#ffcccc"  # Even lighter red for full line deletions
        
        nxt = pal.color(QPalette.Button).name()
        
        style = f"""
        <style>
        table.diff {{
            font-family: monospace;
            border: 1px solid {header};
            border-collapse: collapse;
            background: {base};
            color: {text};
            table-layout: fixed; /* fixed layout allows explicit column widths */
            width: 100%;
        }}
        /* Column widths via nth-child (4 columns: ln, text, ln, text) */
        table.diff thead tr th:nth-child(1),
        table.diff tbody tr td:nth-child(1) {{
            width: 4%;
            text-align: right;
            padding-right: 8px;
            background: {nxt};
            color: #888;
        }}
        table.diff thead tr th:nth-child(2),
        table.diff tbody tr td:nth-child(2) {{
            width: 46%;
        }}
        table.diff thead tr th:nth-child(3),
        table.diff tbody tr td:nth-child(3) {{
            width: 4%;
            text-align: right;
            padding-right: 8px;
            background: {nxt};
            color: #888;
        }}
        table.diff thead tr th:nth-child(4),
        table.diff tbody tr td:nth-child(4) {{
            width: 46%;
        }}
        .diff_header {{
            background: {header};
            padding: 4px;
            font-weight: bold;
            text-align: center;
        }}
        /* Diff cell base styles */
        table.diff td {{
            padding: 2px 6px;
            vertical-align: top;
            border-left: 1px solid {header};
            border-top: 1px solid {header};
        }}
        /* Enable wrapping for content cells */
        table.diff tbody tr td:nth-child(2),
        table.diff tbody tr td:nth-child(4) {{
            white-space: pre-wrap;    /* preserve whitespace and wrap */
            overflow-wrap: anywhere;  /* break long words/URLs */
            word-break: break-word;
        }}
        /* Character-level changes within lines */
        .diff_add {{
            background: {add};
            color: {text};
        }}
        .diff_chg {{
            background: {chg};
            color: {text};
        }}
        .diff_sub {{
            background: {sub};
            color: {text};
        }}
        /* Full line additions/deletions visibility */
        tr.diff_add td:nth-child(2),
        tr.diff_add td:nth-child(4) {{
            background: {add_line};
        }}
        tr.diff_sub td:nth-child(2),
        tr.diff_sub td:nth-child(4) {{
            background: {sub_line};
        }}
        </style>
        """
        
        return style + diff

    def _build_side_by_side_html(self, old_content: str, new_content: str, file_path: str, wrap: bool = True) -> str:
        """Build a custom side-by-side HTML diff with line numbers and highlighting.
        
        Args:
            old_content: Original content
            new_content: Proposed content
            file_path: File path
            wrap: Whether to wrap long lines
        
        Returns:
            HTML string rendering a 4-column table: ln, old, ln, new
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        opcodes = sm.get_opcodes()
        
        # Build maps of line index -> status
        old_mark = {}
        new_mark = {}
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                continue
            if tag == 'replace':
                for i in range(i1, i2):
                    old_mark[i] = 'chg'
                for j in range(j1, j2):
                    new_mark[j] = 'chg'
            elif tag == 'delete':
                for i in range(i1, i2):
                    old_mark[i] = 'sub'
            elif tag == 'insert':
                for j in range(j1, j2):
                    new_mark[j] = 'add'
        
        # Colors
        pal = self.palette()
        base = pal.color(QPalette.Base).name()
        text = pal.color(QPalette.Text).name()
        header = pal.color(QPalette.AlternateBase).name()
        is_dark_mode = pal.color(QPalette.Text).lightness() > 128
        if is_dark_mode:
            add = "#0d4a0d"
            sub = "#5c1a1a"
            chg = "#5c4d0d"
            add_line = "#1a6b1a"
            sub_line = "#7a2424"
        else:
            add = "#d4ffd4"
            sub = "#ffd4d4"
            chg = "#ffffb3"
            add_line = "#ccffcc"
            sub_line = "#ffcccc"
        
        # CSS
        style = f"""
        <style>
        table.ssdiff {{
            font-family: monospace;
            border-collapse: collapse;
            width: 100%;
            table-layout: fixed;
            background: {base};
            color: {text};
        }}
        table.ssdiff thead th {{
            background: {header};
            padding: 4px;
            font-weight: bold;
            text-align: center;
        }}
        table.ssdiff thead th:nth-child(1),
        table.ssdiff tbody td:nth-child(1) {{
            width: 4%;
            text-align: right;
            padding-right: 8px;
            color: #888;
            border-right: 1px solid {header};
        }}
        table.ssdiff thead th:nth-child(2),
        table.ssdiff tbody td:nth-child(2) {{
            width: 46%;
            white-space: {"pre-wrap" if wrap else "pre"};
            overflow-wrap: {"anywhere" if wrap else "normal"};
            word-break: {"break-word" if wrap else "normal"};
            padding: 2px 6px;
        }}
        table.ssdiff thead th:nth-child(3),
        table.ssdiff tbody td:nth-child(3) {{
            width: 4%;
            text-align: right;
            padding-right: 8px;
            color: #888;
            border-right: 1px solid {header};
        }}
        table.ssdiff thead th:nth-child(4),
        table.ssdiff tbody td:nth-child(4) {{
            width: 46%;
            white-space: {"pre-wrap" if wrap else "pre"};
            overflow-wrap: {"anywhere" if wrap else "normal"};
            word-break: {"break-word" if wrap else "normal"};
            padding: 2px 6px;
        }}
        /* Inline character-level highlights */
        .char_add {{ background: {add}; }}
        .char_sub {{ background: {sub}; text-decoration: line-through; }}
        .char_chg {{ background: {chg}; }}
        /* Full line additions/deletions visibility */
        tr.add td:nth-child(4), tr.add td:nth-child(2) {{ background: {add_line}; }}
        tr.sub td:nth-child(2), tr.sub td:nth-child(4) {{ background: {sub_line}; }}
        tr.chg td:nth-child(2), tr.chg td:nth-child(4) {{ background: {chg}; }}
        </style>
        """
        
        # Build rows
        nrows = max(len(old_lines), len(new_lines))
        rows = []
        for idx in range(nrows):
            old_ln = idx + 1 if idx < len(old_lines) else ''
            new_ln = idx + 1 if idx < len(new_lines) else ''
            old_txt = (old_lines[idx] if idx < len(old_lines) else '')
            new_txt = (new_lines[idx] if idx < len(new_lines) else '')
            # Row class reflects any change on either side
            cls = ''
            if idx < len(old_lines) and old_mark.get(idx) == 'sub':
                cls = 'sub'
            elif idx < len(new_lines) and new_mark.get(idx) == 'add':
                cls = 'add'
            elif (idx < len(old_lines) and old_mark.get(idx) == 'chg') or (idx < len(new_lines) and new_mark.get(idx) == 'chg'):
                cls = 'chg'
            # Inline character-level highlighting for changed lines
            if cls == 'chg':
                smc = difflib.SequenceMatcher(a=old_txt, b=new_txt, autojunk=False)
                old_parts = []
                new_parts = []
                for tag, i1, i2, j1, j2 in smc.get_opcodes():
                    oseg = _html.escape(old_txt[i1:i2])
                    nseg = _html.escape(new_txt[j1:j2])
                    if tag == 'equal':
                        old_parts.append(oseg)
                        new_parts.append(nseg)
                    elif tag == 'delete':
                        old_parts.append(f"<span class='char_sub'>{oseg}</span>")
                    elif tag == 'insert':
                        new_parts.append(f"<span class='char_add'>{nseg}</span>")
                    elif tag == 'replace':
                        old_parts.append(f"<span class='char_chg'>{oseg}</span>")
                        new_parts.append(f"<span class='char_chg'>{nseg}</span>")
                old_html = ''.join(old_parts)
                new_html = ''.join(new_parts)
            else:
                old_html = _html.escape(old_txt)
                new_html = _html.escape(new_txt)
                if cls == 'sub' and old_html:
                    old_html = f"<span class='char_sub'>{old_html}</span>"
                if cls == 'add' and new_html:
                    new_html = f"<span class='char_add'>{new_html}</span>"
            row = f"<tr class='{cls}'>" \
                  f"<td>{old_ln}</td>" \
                  f"<td>{old_html}</td>" \
                  f"<td>{new_ln}</td>" \
                  f"<td>{new_html}</td>" \
                  f"</tr>"
            rows.append(row)
        
        head = "<thead><tr><th>#</th><th>Current</th><th>#</th><th>Proposed</th></tr></thead>"
        body = "<tbody>" + "\n".join(rows) + "</tbody>"
        html = f"<table class='ssdiff'>{head}{body}</table>"
        
        return style + html
    
    def _update_stats_label(self):
        """Update the statistics label."""
        enabled_count = len(self.batch.get_enabled_edits())
        total_count = len(self.batch.edits)
        enabled_files = self.batch.total_enabled_files()
        
        added, deleted, changed = self.batch.get_cumulative_stats()
        
        self.stats_label.setText(
            f"{enabled_count} of {total_count} edits enabled ({enabled_files} files) | "
            f"Total changes: +{added} / -{deleted} / ~{changed}"
        )
        self.stats_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 8px;")
    
    def _select_all(self):
        """Enable all edits."""
        self.batch.enable_all()
        
        # Update checkboxes
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, FileListItem):
                widget.checkbox.setChecked(True)
        
        self._update_stats_label()
    
    def _select_none(self):
        """Disable all edits."""
        self.batch.disable_all()
        
        # Update checkboxes
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, FileListItem):
                widget.checkbox.setChecked(False)
        
        self._update_stats_label()
    
    def _apply_all_and_accept(self):
        """Enable all edits and accept."""
        self.batch.enable_all()
        self.accept()
    
    def get_enabled_edits(self) -> list[FileEdit]:
        """Get list of edits that are enabled.
        
        Returns:
            List of FileEdit objects with enabled=True
        """
        return self.batch.get_enabled_edits()
    
    def _build_unified_html(self, old_content: str, new_content: str, file_path: str, wrap: bool = True) -> str:
        """Build a unified diff view (like `diff -u` output).
        
        Args:
            old_content: Original content
            new_content: Proposed content
            file_path: File path
            wrap: Whether to wrap long lines
        
        Returns:
            HTML string with unified diff format
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"Original ({file_path})",
            tofile=f"Proposed ({file_path})",
            lineterm='',
            n=3
        ))
        
        # Color scheme
        pal = self.palette()
        base = pal.color(QPalette.Base).name()
        text = pal.color(QPalette.Text).name()
        header = pal.color(QPalette.AlternateBase).name()
        is_dark_mode = pal.color(QPalette.Text).lightness() > 128
        if is_dark_mode:
            add = "#1a6b1a"
            sub = "#7a2424"
            ctx = "#333333"
        else:
            add = "#ccffcc"
            sub = "#ffcccc"
            ctx = "#f0f0f0"
        
        ws = "pre-wrap" if wrap else "pre"
        ow = "anywhere" if wrap else "normal"
        
        style = f"""
        <style>
        .unified-diff {{
            font-family: monospace;
            white-space: {ws};
            overflow-wrap: {ow};
            word-break: break-word;
            background: {base};
            color: {text};
            padding: 8px;
            border: 1px solid {header};
            border-radius: 4px;
        }}
        .diff-header {{
            background: {header};
            padding: 4px;
            font-weight: bold;
            margin-bottom: 4px;
        }}
        .diff-add {{
            background: {add};
            color: {text};
        }}
        .diff-sub {{
            background: {sub};
            color: {text};
        }}
        .diff-ctx {{
            background: {ctx};
            color: {text};
        }}
        .diff-line {{
            display: block;
            padding: 1px 4px;
        }}
        </style>
        """
        
        html_lines = [f'<div class="unified-diff">']
        
        for line in diff:
            line_escaped = _html.escape(line)
            if line.startswith('+++') or line.startswith('---'):
                html_lines.append(f'<div class="diff-header">{line_escaped}</div>')
            elif line.startswith('+'):
                html_lines.append(f'<div class="diff-line diff-add">{line_escaped}</div>')
            elif line.startswith('-'):
                html_lines.append(f'<div class="diff-line diff-sub">{line_escaped}</div>')
            elif line.startswith('@@'):
                html_lines.append(f'<div class="diff-header">{line_escaped}</div>')
            else:
                html_lines.append(f'<div class="diff-line diff-ctx">{line_escaped}</div>')
        
        html_lines.append('</div>')
        
        return style + '\n'.join(html_lines)

