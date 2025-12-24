from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QDialogButtonBox, QSplitter, QWidget, QPushButton, QStackedWidget, QTextBrowser
from PySide6.QtCore import Qt
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
    def __init__(self, file_path, old_content, new_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Review Changes - {file_path}")
        self.resize(1200, 700)
        
        layout = QVBoxLayout(self)
        
        # Info
        if old_content is None:
            layout.addWidget(QLabel(f"Creating NEW file: {file_path}"))
        else:
            layout.addWidget(QLabel(f"Modifying file: {file_path}"))
        
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
        diff_view.setStyleSheet("QTextBrowser { font-family: monospace; }")
        diff_html = self._build_diff_html(old_content or "", new_content or "")
        diff_view.setHtml(diff_html)
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

    def _build_diff_html(self, old_text: str, new_text: str) -> str:
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
            context=True,
            numlines=2,
        )
        # Add minimal styling for readability
        style = """
        <style>
        table.diff {font-family: monospace; border:1px solid #ccc; border-collapse:collapse;}
        .diff_header {background:#f0f0f0; padding:4px;}
        .diff_next {background:#e8e8e8;}
        .diff_add {background:#e6ffed;}
        .diff_chg {background:#fff5b1;}
        .diff_sub {background:#ffecec;}
        td {padding:2px 4px;}
        </style>
        """
        return style + diff
