from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QDialogButtonBox, QSplitter, QWidget, QPushButton, QStackedWidget, QTextBrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
import markdown
import difflib

class DiffPanel(QWidget):
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with Toggle
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch()
        
        self.toggle_btn = QPushButton("Show Preview")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self.toggle_view)
        header_layout.addWidget(self.toggle_btn)
        
        self.layout.addLayout(header_layout)
        
        # Stack
        self.stack = QStackedWidget()
        
        # Text View
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(content if content else "")
        self.stack.addWidget(self.text_edit)
        
        # Preview View
        self.preview = QTextBrowser()
        if content:
            html = markdown.markdown(content, extensions=['fenced_code', 'tables'])
            self.preview.setHtml(html)
        # Match preview background/text to app palette for better dark-mode readability
        pal = self.preview.palette()
        self.preview.setStyleSheet(
            "QTextBrowser { background: %s; color: %s; }" % (
                pal.color(QPalette.Base).name(),
                pal.color(QPalette.Text).name(),
            )
        )
        self.stack.addWidget(self.preview)
        
        self.layout.addWidget(self.stack)

    def toggle_view(self):
        if self.toggle_btn.isChecked():
            self.toggle_btn.setText("Show Text")
            self.stack.setCurrentIndex(1)
        else:
            self.toggle_btn.setText("Show Preview")
            self.stack.setCurrentIndex(0)

class DiffDialog(QDialog):
    def __init__(self, file_path, old_content, new_content, parent=None, selection_range: tuple[int, int] | None = None, default_apply_only_selection: bool = False):
        super().__init__(parent)
        self.setWindowTitle(f"Review Changes - {file_path}")
        self.resize(1200, 700)
        self._old_text = old_content or ""
        self._new_text = new_content or ""
        self._selection_range = selection_range
        self._apply_only_selection = False
        
        layout = QVBoxLayout(self)
        
        # Info
        if old_content is None:
            layout.addWidget(QLabel(f"Creating NEW file: {file_path}"))
        else:
            layout.addWidget(QLabel(f"Modifying file: {file_path}"))
        
        # Change summary (added/removed/changed lines)
        add_count, del_count, chg_count = self._compute_diff_stats(self._old_text, self._new_text)
        summary_label = QLabel(f"Changes: +{add_count} / -{del_count} / ~{chg_count}")
        summary_label.setStyleSheet("color: #444; font-style: italic; margin-bottom: 6px;")
        layout.addWidget(summary_label)

        # Selection info and checkbox
        if self._selection_range:
            s, e = self._selection_range
            sel_label = QLabel(f"Selection: L{s}-L{e}")
            sel_label.setStyleSheet("color: #666; margin-bottom: 4px;")
            layout.addWidget(sel_label)
            from PySide6.QtWidgets import QCheckBox
            self._selection_cb = QCheckBox("Apply only within selected range")
            self._selection_cb.setChecked(bool(default_apply_only_selection))
            self._selection_cb.toggled.connect(lambda v: setattr(self, '_apply_only_selection', bool(v)))
            layout.addWidget(self._selection_cb)
        
        # Main splitter: top = side-by-side, bottom = HTML diff
        main_splitter = QSplitter(Qt.Vertical)
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Old Panel
        self.old_panel = DiffPanel("Current Content", old_content)
        content_splitter.addWidget(self.old_panel)
        
        # New Panel
        self.new_panel = DiffPanel("Proposed Content", new_content)
        content_splitter.addWidget(self.new_panel)
        
        main_splitter.addWidget(content_splitter)
        
        # Diff view (HTML table with highlights)
        diff_view = QTextBrowser()
        diff_view.setOpenExternalLinks(False)
        diff_view.setOpenLinks(False)
        pal = diff_view.palette()
        diff_view.setStyleSheet(
            "QTextBrowser { font-family: monospace; background: %s; color: %s; }" % (
                pal.color(QPalette.Base).name(),
                pal.color(QPalette.Text).name(),
            )
        )
        self._show_context = True
        self._diff_view = diff_view
        diff_html = self._build_diff_html(self._old_text, self._new_text, context=self._show_context)
        diff_view.setHtml(diff_html)
        
        # Diff controls
        controls = QHBoxLayout()
        toggle_full_btn = QPushButton("Show Full Diff")
        toggle_full_btn.setCheckable(True)
        toggle_full_btn.toggled.connect(lambda checked: self._toggle_diff_context(checked))
        controls.addWidget(toggle_full_btn)
        controls.addStretch()
        layout.addLayout(controls)
        main_splitter.addWidget(diff_view)
        
        # Relative sizes: give more space to side-by-side
        main_splitter.setSizes([800, 400])
        
        layout.addWidget(main_splitter)
        
        # Buttons
        # Use Ok button but rename it to "Apply Changes" so it emits the accepted signal correctly
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Apply Changes")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def apply_only_selection(self) -> bool:
        return bool(self._apply_only_selection)

    def _build_diff_html(self, old_text: str, new_text: str, context: bool = True) -> str:
        """Generate an HTML side-by-side diff table.
        Uses difflib.HtmlDiff for clear visual differences.
        """
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = difflib.HtmlDiff(wrapcolumn=120).make_table(
            old_lines,
            new_lines,
            fromdesc="Current",
            todesc="Proposed",
            context=context,
            numlines=2,
        )
        # Add palette-aware styling for readability (dark/light)
        pal = self.palette()
        base = pal.color(QPalette.Base).name()
        text = pal.color(QPalette.Text).name()
        header = pal.color(QPalette.AlternateBase).name()
        # Dark mode: text is light (high lightness), use dark backgrounds with light text
        # Light mode: text is dark (low lightness), use light backgrounds with dark text
        is_dark_mode = pal.color(QPalette.Text).lightness() > 128
        add = "#1a3d1a" if is_dark_mode else "#e6ffed"
        sub = "#4d1a1a" if is_dark_mode else "#ffecec"
        chg = "#4d3d0d" if is_dark_mode else "#fff5b1"
        nxt = pal.color(QPalette.Button).name()
        style = f"""
        <style>
        table.diff {{font-family: monospace; border:1px solid {header}; border-collapse:collapse; background:{base}; color:{text};}}
        .diff_header {{background:{header}; padding:4px;}}
        .diff_next {{background:{nxt};}}
        .diff_add {{background:{add}; color:{text};}}
        .diff_chg {{background:{chg}; color:{text};}}
        .diff_sub {{background:{sub}; color:{text};}}
        td {{padding:2px 4px;}}
        </style>
        """
        return style + diff

    def _compute_diff_stats(self, old_text: str, new_text: str):
        """Compute counts of added, removed, and changed lines."""
        add = del_ = chg = 0
        differ = difflib.Differ()
        for line in differ.compare(old_text.splitlines(), new_text.splitlines()):
            if line.startswith('+ '):
                add += 1
            elif line.startswith('- '):
                del_ += 1
            elif line.startswith('? '):
                chg += 1
        return add, del_, chg

    def _toggle_diff_context(self, show_full: bool):
        """Toggle between context and full diff views."""
        self._show_context = not show_full
        html = self._build_diff_html(self._old_text, self._new_text, context=self._show_context)
        self._diff_view.setHtml(html)
