from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFileDialog, QMenuBar, QMenu, QStackedWidget, QMessageBox, QStyle, QInputDialog, QProgressDialog, QProgressBar
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtCore import Qt, QThread, Signal, QCoreApplication, QSettings

from gui.sidebar import Sidebar
from core.project import ProjectManager
from core.llm_provider import OllamaProvider, LMStudioProvider
from core.rag_engine import RAGEngine

from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.diff_dialog import DiffDialog
from gui.dialogs.image_dialog import ImageSelectionDialog
from gui.editor import EditorWidget, DocumentWidget, ImageViewerWidget
from gui.chat import ChatWidget
from gui.welcome import WelcomeWidget
from gui.image_gen import ImageGenWidget

from gui.controllers import MenuBarManager, ProjectController, EditorController, ChatController

from gui.workers import ChatWorker, BatchWorker, ToolWorker, IndexWorker
import re
import os
import hashlib
import difflib
import shutil
from core.tools import register_default_tools
from core.tools.registry import register_by_names


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic.
    Approximates: ~1 token per 4 characters on average.
    This is a rough estimate that works for most models."""
    if not text:
        return 0
    # More sophisticated: count words and adjust for punctuation
    words = len(text.split())
    chars = len(text)
    # Average of 4 chars per token
    return max(words // 2, chars // 4)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inkwell AI")
        self.resize(1200, 800)
        
        # Core state
        self.project_manager = ProjectManager()
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.rag_engine = None
        self._last_token_usage = None
        
        # Central Stack (Welcome vs Main Interface)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # 1. Welcome Screen
        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.open_clicked.connect(self.open_project_dialog)
        self.welcome_widget.recent_clicked.connect(self.open_project)
        self.stack.addWidget(self.welcome_widget)
        
        # 2. Main Interface
        self.main_interface = QWidget()
        main_layout = QHBoxLayout(self.main_interface)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for Sidebar vs Main Content
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.tree.doubleClicked.connect(self.on_file_double_clicked)
        self.main_splitter.addWidget(self.sidebar)
        
        # Content Splitter (Editor vs Chat)
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.content_splitter)
        
        # Editor Area
        self.editor = EditorWidget()
        self.editor.batch_edit_requested.connect(self.handle_batch_edit)
        self.editor.tab_closed.connect(self.save_project_state)
        self.content_splitter.addWidget(self.editor)
        
        # Image Studio
        self.image_gen = ImageGenWidget(self.settings)
        
        # Chat Interface
        self.chat = ChatWidget()
        self.chat.provider_changed.connect(self.on_provider_changed)
        self.chat.model_changed.connect(self.on_model_changed)
        self.chat.refresh_models_requested.connect(self.on_refresh_models)
        self.chat.message_copied.connect(self.on_message_copied)
        self.content_splitter.addWidget(self.chat)

        # Initialize controllers (after widgets are created)
        self.editor_controller = EditorController(self)
        self.project_controller = ProjectController(self)
        self.chat_controller = ChatController(self)
        self.menu_manager = MenuBarManager(self)
        
        # Create menus and toolbars via MenuBarManager
        self.menu_manager.create_menus()
        self.menu_manager.create_toolbar()
        self.menu_manager.create_format_toolbar()
        
        # Connect controller signals
        self.sidebar.file_renamed.connect(self.editor_controller.on_file_renamed)
        self.sidebar.file_moved.connect(self.editor_controller.on_file_moved)
        self.editor.modification_changed.connect(self.editor_controller.update_save_button_state)
        
        self.chat.message_sent.connect(self.chat_controller.handle_chat_message)
        self.chat.link_clicked.connect(self.chat_controller.handle_chat_link)
        self.chat.save_chat_requested.connect(self.handle_save_chat)
        self.chat.copy_to_file_requested.connect(self.handle_copy_chat_to_file)
        self.chat.message_deleted.connect(self.chat_controller.handle_message_deleted)
        self.chat.message_edited.connect(self.chat_controller.handle_message_edited)
        self.chat.regenerate_requested.connect(self.chat_controller.handle_regenerate)
        self.chat.continue_requested.connect(self.chat_controller.handle_continue)
        self.chat.new_chat_requested.connect(self.chat_controller.handle_new_chat)
        self.chat.context_level_changed.connect(self.chat_controller.on_context_level_changed)

        # Initialize model controls
        self.update_model_controls()
        
        # Set initial sizes
        self.main_splitter.setSizes([240, 960])
        self.content_splitter.setSizes([700, 260])
        
        self.stack.addWidget(self.main_interface)
        
        # Start at Welcome
        self.stack.setCurrentWidget(self.welcome_widget)
        
        # Token dashboard in status bar
        self.token_status = QLabel("Tokens: --/-- | Cache: -- | Index: idle")
        self.statusBar().addPermanentWidget(self.token_status)
        
        # Load Recent Projects for Welcome Screen
        self.project_controller.update_welcome_screen()

        # Auto-open last project
        last_project = self.settings.value("last_project")
        if last_project and os.path.exists(last_project):
            self.project_controller.open_project(last_project)

    # ========== Delegation Methods (Controller Wrappers) ==========
    # These methods delegate to controllers for backward compatibility
    
    # Project operations -> ProjectController
    def open_project_dialog(self):
        """Delegate to ProjectController."""
        self.project_controller.open_project_dialog()
    
    def open_project(self, path):
        """Delegate to ProjectController."""
        self.project_controller.open_project(path)
    
    def close_project(self):
        """Delegate to ProjectController."""
        self.project_controller.close_project()
    
    def save_project_state(self):
        """Delegate to ProjectController."""
        self.project_controller.save_project_state()
    
    def restore_project_state(self):
        """Delegate to ProjectController."""
        self.project_controller.restore_project_state()
    
    # File operations -> EditorController
    def on_file_double_clicked(self, index):
        """Delegate to EditorController."""
        self.editor_controller.on_file_double_clicked(index)
    
    def save_current_file(self):
        """Delegate to EditorController."""
        self.editor_controller.save_current_file()
    
    def undo_file_change(self):
        """Delegate to EditorController."""
        self.editor_controller.undo_file_change()
    
    def redo_file_change(self):
        """Delegate to EditorController."""
        self.editor_controller.redo_file_change()
    
    # Chat operations -> ChatController (commented out as most are already connected to controller)
    def open_chat_history(self):
        """Delegate to ChatController."""
        self.chat_controller.open_chat_history()

    def update_welcome_screen(self):
        """Delegate to ProjectController."""
        self.project_controller.update_welcome_screen()

    def update_model_controls(self):
        """Update model controls with current settings and available models."""
        try:
            provider_name = self.settings.value("llm_provider", "Ollama")
            provider = self.get_llm_provider()
            
            # Get available models
            models = provider.list_models()
            
            # Determine which models support vision
            vision_models = [m for m in models if provider.is_vision_model(m)]
            
            # Get current model based on provider
            if provider_name == "Ollama":
                current_model = self.settings.value("ollama_model", "llama3")
            else:
                current_model = self.settings.value("lm_studio_model", "default")
            
            # Update UI with vision model indicators
            self.chat.update_model_info(provider_name, current_model, models, vision_models)
        except Exception as e:
            print(f"DEBUG: Failed to update model controls: {e}")
            # Set defaults
            self.chat.update_model_info("Ollama", "llama3", ["llama3"], [])
    
    def on_provider_changed(self, provider_name):
        """Handle provider selection change."""
        self.settings.setValue("llm_provider", provider_name)
        self.update_model_controls()
    
    def on_model_changed(self, model_name):
        """Handle model selection change."""
        # Get the raw model name (strip vision indicator if present)
        raw_model = self.chat.model_combo.currentData()
        if raw_model is None:
            # Fallback: strip indicator from display text
            raw_model = self.chat.model_combo.currentText().replace("👁️", "").strip()
        
        if not raw_model:
            return
        
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            self.settings.setValue("ollama_model", raw_model)
        else:
            self.settings.setValue("lm_studio_model", raw_model)
    
    def on_refresh_models(self):
        """Refresh available models from provider."""
        self.update_model_controls()
    
    def on_context_level_changed(self, level):
        """Handle context level change."""
        self.context_level = level

    def get_llm_provider(self):
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            url = self.settings.value("ollama_url", "http://localhost:11434")
            return OllamaProvider(base_url=url)
        else:
            url = self.settings.value("lm_studio_url", "http://localhost:1234")
            return LMStudioProvider(base_url=url)

    def is_response_complete(self, response: str) -> bool:
        """Check if the response appears complete.
        Returns False if response is likely incomplete (missing closing blocks, etc.)"""
        # Check for incomplete UPDATE blocks
        update_opens = response.count(":::UPDATE")
        update_closes = response.count(":::END:::") + response.count(":::END") + response.count(":::")
        # Note: this is a heuristic; could have false positives but better safe than sorry
        
        # If there are unclosed UPDATE blocks, response is incomplete
        if update_opens > 0 and update_closes < update_opens:
            return False
        
        # Check for incomplete GENERATE_IMAGE blocks
        gen_opens = response.count(":::GENERATE_IMAGE")
        if gen_opens > 0 and update_closes < gen_opens:
            return False
        
        # If response ends abruptly with specific tokens, it's likely incomplete
        incomplete_endings = [
            "- ",
            "* ",
            "1. ",
            ": ",
            "and ",
            "or ",
            "in ",
            "the ",
        ]
        
        # Only flag if it's a very short ending
        if len(response) > 50:
            for ending in incomplete_endings:
                if response.rstrip().endswith(ending):
                    return False
        
        return True

    def _continue_response(self):
        """Automatically continue the previous response."""
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )

        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            [],
            system_prompt,
            images=None,
            enabled_tools=self.project_manager.get_enabled_tools(),
        )
        self.worker.response_received.connect(self.chat_controller.on_chat_response)
        self.worker.start()
        self._update_token_dashboard()

    def _normalize_edit_path(self, raw_path: str, active_path: str | None) -> str:
        """Make path extraction more forgiving.
        - Strip quotes/backticks/angle brackets
        - Collapse redundant slashes
        - If path seems to be just a basename, try to resolve in project
        - Fallback to active file when path is empty
        """
        path = raw_path.strip()
        # Remove enclosing quotes/backticks/angle brackets
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        if (path.startswith('<') and path.endswith('>')) or (path.startswith('`') and path.endswith('`')):
            path = path[1:-1]
        # Normalize slashes but DO NOT strip leading '/'
        path = path.replace('\\', '/')
        # Remove a single leading './' if present
        if path.startswith('./'):
            path = path[2:]
        # Drop any accidental line markers or closers appended to the path
        if '\n' in path:
            path = path.splitlines()[0].strip()
        # If a line marker like " L12:" got attached, cut it off
        import re as _re
        path = _re.split(r"\s+L\d+:", path)[0].strip()
        # Remove stray block terminators if present
        for marker in (":::END:::", ":::END", ":::"):
            if marker in path:
                path = path.split(marker)[0].strip()
        # Collapse duplicate slashes (preserving a single leading '/')
        while '//' in path:
            path = path.replace('//', '/')
        path = path.strip()
        # If empty, fallback to active file if available
        if not path and active_path:
            return active_path
        # If it's an absolute path within project, convert to relative
        if self.project_manager.root_path and os.path.isabs(path):
            try:
                rel = os.path.relpath(path, self.project_manager.root_path)
                if not rel.startswith('..'):
                    path = rel
            except Exception:
                pass
        # If no directories (basename only), try to resolve in project
        if '/' not in path and self.project_manager.root_path:
            candidates = []
            for root, dirs, files in os.walk(self.project_manager.root_path):
                for f in files:
                    if f == path:
                        candidates.append(os.path.relpath(os.path.join(root, f), self.project_manager.root_path))
            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1 and active_path:
                # Prefer same directory as active file when possible
                active_dir = os.path.dirname(active_path)
                for c in candidates:
                    if os.path.dirname(c) == active_dir:
                        return c
                # Fallback to closest match by dir length
                candidates.sort(key=lambda p: len(os.path.dirname(p)))
                return candidates[0]
        # Fuzzy correction: if path not found, try close matches against project files
        if self.project_manager.root_path:
            target = path.split('/')[-1]
            index = []
            for root, dirs, files in os.walk(self.project_manager.root_path):
                for f in files:
                    index.append(os.path.relpath(os.path.join(root, f), self.project_manager.root_path))
            basenames = [os.path.basename(p) for p in index]
            matches = difflib.get_close_matches(target, basenames, n=1, cutoff=0.8)
            if matches:
                m = matches[0]
                # Pick the path whose basename equals the match
                for p in index:
                    if os.path.basename(p) == m:
                        return p
        return path

    def _apply_patch_block(self, file_path: str, patch_body: str) -> tuple[bool, str | None]:
        """Apply a PATCH block to a file's current content and return new content.

        PATCH lines format: L42: old => new
        Only single-line replacements are supported. If the old text is not found on the line,
        the entire line is replaced with the new text.
        Also supports range replacements: L10-L15: followed by either inline text or a fenced
        block (```...```) containing the replacement lines.
        """
        print(f"DEBUG: _apply_patch_block called for {file_path}, body length: {len(patch_body)}, first 100 chars: {patch_body[:100]!r}")
        
        try:
            current = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for patch {file_path}: {e}")
            return False, None

        if current is None:
            print(f"DEBUG: No content to patch for {file_path}")
            return False, None

        lines = current.split("\n")
        original_had_trailing_newline = current.endswith("\n")
        applied_any = False

        # Prefer range replacements over inline segments if any range marker exists
        has_range_marker = re.search(r"L\d+\s*-\s*L\d+:", patch_body) is not None
        # Support inline bodies without newlines: split using L\d+: markers
        inline_segments = [] if has_range_marker else list(
            re.finditer(r"L(\d+):\s*(.*?)(?=\s+L\d+:|\s+L\d+\s*-\s*L\d+:|$)", patch_body, flags=re.DOTALL)
        )
        if inline_segments:
            for seg in inline_segments:
                line_no = int(seg.group(1))
                new_text = seg.group(2).strip()
                if line_no < 1 or line_no > len(lines):
                    print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                    continue
                lines[line_no - 1] = new_text
                applied_any = True
        else:
            raw_lines = patch_body.splitlines()
            i = 0
            while i < len(raw_lines):
                raw = raw_lines[i]
                line = raw.strip()
                i += 1
                if not line:
                    continue
                # Range replacement: Lx-Ly:
                m_range = re.match(r"L(\d+)\s*-\s*L(\d+):\s*(.*)", line)
                if m_range:
                    start_no = int(m_range.group(1))
                    end_no = int(m_range.group(2))
                    trailing = m_range.group(3).strip()
                    repl_lines: list[str] = []
                    # If inline text present after ':', use it as the first replacement line,
                    # then continue capturing subsequent lines until a directive or end.
                    if trailing:
                        repl_lines.append(trailing)
                    # If next line starts a fenced block, capture until closing fence
                    if i < len(raw_lines) and raw_lines[i].strip().startswith("```"):
                        i += 1
                        while i < len(raw_lines) and not raw_lines[i].strip().startswith("```"):
                            repl_lines.append(raw_lines[i])
                            i += 1
                        # Skip closing fence if present
                        if i < len(raw_lines) and raw_lines[i].strip().startswith("```"):
                            i += 1
                    else:
                        # Otherwise, capture until next directive or end
                        while i < len(raw_lines):
                            peek = raw_lines[i]
                            if re.match(r"\s*L\d+:", peek) or re.match(r"\s*L\d+\s*-\s*L\d+:", peek):
                                break
                            repl_lines.append(peek)
                            i += 1
                    # Safety: strip any stray leading/trailing fences inside captured lines
                    if repl_lines:
                        if repl_lines[0].strip().startswith("```"):
                            repl_lines = repl_lines[1:]
                        if repl_lines and repl_lines[-1].strip().startswith("```"):
                            repl_lines = repl_lines[:-1]
                    # Apply replacement to target range
                    s_idx = max(1, start_no)
                    e_idx = min(len(lines), end_no)
                    if s_idx > e_idx:
                        print(f"DEBUG: Invalid range L{start_no}-L{end_no} for {file_path}")
                        continue
                    print(f"DEBUG: Applying PATCH range L{start_no}-L{end_no}: replacing {e_idx - s_idx + 1} lines with {len(repl_lines)} lines")
                    # Replace slice with repl_lines
                    before = lines[:s_idx - 1]
                    after = lines[e_idx:]
                    lines = before + repl_lines + after
                    applied_any = True
                    continue
                # With old=>new or old->new
                m = re.match(r"L(\d+):\s*(.+?)\s*(?:=>|->)\s*(.+)", line)
                if m:
                    line_no = int(m.group(1))
                    old_text = m.group(2)
                    new_text = m.group(3)
                    if line_no < 1 or line_no > len(lines):
                        print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                        continue
                    current_line = lines[line_no - 1]
                    if old_text in current_line:
                        lines[line_no - 1] = current_line.replace(old_text, new_text, 1)
                    else:
                        lines[line_no - 1] = new_text
                    applied_any = True
                    continue
                # Without old text: set entire line
                m2 = re.match(r"L(\d+):\s*(.+)", line)
                if m2:
                    line_no = int(m2.group(1))
                    new_text = m2.group(2).strip()
                    if line_no < 1 or line_no > len(lines):
                        print(f"DEBUG: Patch line out of range L{line_no} for {file_path}")
                        continue
                    lines[line_no - 1] = new_text
                    applied_any = True
                else:
                    print(f"DEBUG: Skipping unrecognized patch line: {line}")

        if not applied_any:
            return False, None

        new_content = "\n".join(lines)
        if original_had_trailing_newline and not new_content.endswith("\n"):
            new_content += "\n"
        # Debug snippet around the patched range to verify correctness
        try:
            sample_start = max(0, s_idx - 5)
            sample_end = min(len(new_content.split("\n")), e_idx + 5)
            snippet = "\n".join(new_content.split("\n")[sample_start:sample_end])
            print(f"DEBUG: Patched snippet around L{s_idx}-L{e_idx}:\n{snippet}")
        except Exception:
            pass
        return True, new_content

    def _apply_unified_diff(self, file_path: str, diff_text: str) -> tuple[bool, str | None]:
        """Apply a unified diff (fenced ```diff block) to a file's content.

        Supports multiple hunks with lines starting by ' ', '+', '-'.
        Reconstructs new content based on original file and diff hunks.
        """
        try:
            original = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for unified diff {file_path}: {e}")
            return False, None

        if original is None:
            print(f"DEBUG: No content to patch for unified diff {file_path}")
            return False, None

        orig_lines = original.split("\n")
        new_lines: list[str] = []
        orig_idx = 0  # pointer into original lines

        lines = diff_text.splitlines()

        # Skip headers (---, +++)
        i = 0
        while i < len(lines) and (lines[i].startswith('--- ') or lines[i].startswith('+++ ')):
            i += 1

        hunk_header_re = re.compile(r"@@\s*-([0-9]+)(?:,([0-9]+))?\s*\+([0-9]+)(?:,([0-9]+))?\s*@@")
        any_applied = False

        while i < len(lines):
            if not lines[i].startswith('@@'):
                # Not a hunk header, skip
                i += 1
                continue

            m = hunk_header_re.match(lines[i])
            i += 1
            if not m:
                continue
            # Parse original and new ranges (we mainly use original start for copying unaffected parts)
            orig_start = int(m.group(1))
            # Copy unchanged chunk before this hunk
            target_orig_pos = max(0, orig_start - 1)
            if target_orig_pos > orig_idx:
                new_lines.extend(orig_lines[orig_idx:target_orig_pos])
                orig_idx = target_orig_pos

            # Process hunk body until next hunk header or end
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- ') and not lines[i].startswith('+++ '):
                line = lines[i]
                i += 1
                if not line:
                    # Preserve blank lines when context or addition
                    # Treat as context if no prefix
                    new_lines.append('')
                    continue
                prefix = line[0]
                content = line[1:] if len(line) > 1 else ''
                if prefix == ' ':
                    # Context line: copy from original when available, fallback to provided content
                    if orig_idx < len(orig_lines):
                        new_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                    else:
                        new_lines.append(content)
                elif prefix == '-':
                    # Removal: advance original pointer (skip)
                    if orig_idx < len(orig_lines):
                        orig_idx += 1
                elif prefix == '+':
                    # Addition: add content
                    new_lines.append(content)
                else:
                    # Unknown marker; default to context behavior
                    if orig_idx < len(orig_lines):
                        new_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                    else:
                        new_lines.append(line)
            any_applied = True

        # Append remaining original content after last hunk
        if orig_idx < len(orig_lines):
            new_lines.extend(orig_lines[orig_idx:])

        if not any_applied:
            return False, None

        new_content = "\n".join(new_lines)
        # Preserve trailing newline behavior
        if original.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
        return True, new_content

    def _merge_apply_within_range(self, old_text: str, new_text: str, start_line: int, end_line: int) -> str:
        """Merge changes by applying only the selected line range from new_text.

        Lines are 1-based. If range exceeds bounds, it is clamped.
        """
        old_lines = old_text.split("\n")
        new_lines = new_text.split("\n")
        n = max(len(old_lines), len(new_lines))
        # Clamp
        s = max(1, start_line)
        e = min(n, end_line)
        if s > e:
            return new_text  # nothing sensible, fallback to new_text
        # Build merged
        pre = old_lines[:s-1]
        mid = new_lines[s-1:e]
        post = old_lines[e:]
        merged = "\n".join(pre + mid + post)
        # Preserve trailing newline if old had one
        if old_text.endswith("\n") and not merged.endswith("\n"):
            merged += "\n"
        return merged

    def _find_unfenced_unified_diff_blocks(self, text: str) -> list[tuple[str, str]]:
        """Extract unfenced unified diff blocks and their target paths.

        Returns a list of tuples (diff_text, target_path).
        A block starts with '--- ' followed by '+++ ' and continues while lines
        start with '@@', '+', '-', ' ', or are blank, until the next '--- ' header
        or a non-diff line.
        """
        blocks: list[tuple[str, str]] = []
        lines = text.splitlines(keepends=True)
        i = 0

        def header_path(line: str) -> str:
            p = line[4:].strip() if len(line) > 4 else ''
            if p.startswith('a/') or p.startswith('b/'):
                p = p[2:]
            return p

        while i < len(lines):
            if not lines[i].startswith('--- '):
                i += 1
                continue
            start = i
            i += 1
            if i >= len(lines) or not lines[i].startswith('+++ '):
                # Not a valid diff header pair
                continue
            plus_header = lines[i]
            i += 1

            # Consume hunk bodies
            while i < len(lines):
                l = lines[i]
                if l.startswith('--- '):
                    # Next diff block header encountered
                    break
                if l.startswith('@@') or (l and l[0] in ('+', '-', ' ')) or l.strip() == '':
                    i += 1
                    continue
                # Non-diff line marks end of block
                break

            end = i
            diff_text = ''.join(lines[start:end])
            target_path = header_path(plus_header)
            blocks.append((diff_text, target_path))
        return blocks

    def _strip_unknown_edit_links(self, html: str) -> str:
        """Remove or unwrap any edit: links that are not backed by pending edits."""
        def _replace(match):
            edit_id = match.group(1)
            link_text = match.group(2) or ""
            if edit_id in self.chat_controller.pending_edits:
                return match.group(0)
            print(f"DEBUG: Dropping stale edit link: {edit_id}")
            return link_text

        pattern = r"<a\s+[^>]*href=[\"']edit:([^\"']+)[\"'][^>]*>(.*?)</a>"
        return re.sub(pattern, _replace, html, flags=re.IGNORECASE | re.DOTALL)

    def update_save_button_state(self, modified):
        self.save_act.setEnabled(modified)

    def save_current_file(self):
        path, content = self.editor.get_current_file()
        if path and content is not None:
            try:
                if self.project_manager.save_file(path, content):
                    self.statusBar().showMessage(f"Saved {path}", 2000)
                    self.editor.mark_current_saved() # Reset modified state
                    # Update RAG index for this file
                    if self.rag_engine:
                        self.rag_engine.index_file(path, content)
                        self._update_token_dashboard()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to save {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file: {e}")
        else:
            # Maybe Save As?
            pass

    def open_project_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder_path:
            self.open_project(folder_path)

    def open_project(self, folder_path):
        if self.project_manager.open_project(folder_path):
            # Configure tool registry based on project settings
            try:
                enabled = self.project_manager.get_enabled_tools()
                if enabled is None:
                    register_default_tools()
                else:
                    register_by_names(enabled)
            except Exception:
                pass
            self.sidebar.set_root_path(folder_path)
            self.setWindowTitle(f"Inkwell AI - {folder_path}")
            self.stack.setCurrentWidget(self.main_interface)
            
            # Update Image Gen
            self.image_gen.set_project_path(folder_path)
            
            # Update Editor
            self.editor.set_project_path(folder_path)
            
            # Save to settings
            self.settings.setValue("last_project", folder_path)
            
            # Update Recent Projects
            recent = self.settings.value("recent_projects", [])
            if not isinstance(recent, list): recent = []
            
            if folder_path in recent:
                recent.remove(folder_path)
            recent.insert(0, folder_path)
            recent = recent[:5] # Keep top 5
            self.settings.setValue("recent_projects", recent)
            
            # Initialize RAG
            self.rag_engine = RAGEngine(folder_path)
            
            # Connect RAG engine to sidebar for status indicators
            if hasattr(self, 'sidebar'):
                self.sidebar.set_rag_engine(self.rag_engine)
            
            # Start indexer worker with cancel support
            self.index_worker = IndexWorker(self.rag_engine)
            self.index_worker.progress.connect(self.on_index_progress)
            self.index_worker.finished.connect(self.on_index_finished)
            self.index_worker.start()
            self.index_progress_state = (0, 0, "")
            self._update_token_dashboard()
            
            # Show progress bar
            self.indexing_progress = QProgressBar()
            self.indexing_progress.setTextVisible(True)
            self.indexing_progress.setFormat("Indexing: %p% (%v/%m)")
            self.statusBar().addWidget(self.indexing_progress)
            
            # Restore Tabs
            self.restore_project_state(folder_path)

    def save_project_state(self):
        if not self.project_manager.root_path:
            return
            
        project_path = self.project_manager.root_path
        
        # Use hash of path for key to avoid issues with special chars
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Get open files
        open_files = []
        for i in range(self.editor.tabs.count()):
            widget = self.editor.tabs.widget(i)
            if isinstance(widget, DocumentWidget) or isinstance(widget, ImageViewerWidget):
                path = widget.property("file_path")
                if path and os.path.exists(path) and not os.path.isdir(path):
                    open_files.append(path)
        
        # Check Image Studio
        # We need to check if any of the tabs is the image_gen widget
        image_studio_open = False
        for i in range(self.editor.tabs.count()):
            if self.editor.tabs.widget(i) == self.image_gen:
                image_studio_open = True
                break
        
        self.settings.setValue(f"state/{key}/open_files", open_files)
        self.settings.setValue(f"state/{key}/image_studio_open", image_studio_open)
        self.settings.sync() # Force write to disk

    def restore_project_state(self, project_path):
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Restore files
        open_files = self.settings.value(f"state/{key}/open_files", [])
        
        # Ensure it's a list (QSettings might return a string if only one item)
        if open_files and not isinstance(open_files, list):
            open_files = [open_files]
            
        if open_files:
            for path in open_files:
                if os.path.exists(path) and not os.path.isdir(path):
                    # Check extension to decide how to open
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self.editor.open_file(path, None)
                    else:
                        content = self.project_manager.read_file(path)
                        if content is not None:
                            self.editor.open_file(path, content)
        
        # Restore Image Studio
        image_studio_open = self.settings.value(f"state/{key}/image_studio_open", False, type=bool)
        if image_studio_open:
            self.open_image_studio()
    
    def on_index_progress(self, current, total, file_path):
        """Update progress bar during indexing."""
        if hasattr(self, 'indexing_progress'):
            self.indexing_progress.setMaximum(total)
            self.indexing_progress.setValue(current)
            # Update sidebar to show indexed file status
            if self.rag_engine and hasattr(self, 'sidebar'):
                self.sidebar.update_file_status()
        self.index_progress_state = (current, total, file_path)
        self._update_token_dashboard()
    
    def on_index_finished(self):
        """Clean up after indexing completes."""
        if hasattr(self, 'indexing_progress'):
            self.statusBar().removeWidget(self.indexing_progress)
            self.indexing_progress.deleteLater()
            del self.indexing_progress
        # Final update of file statuses
        if hasattr(self, 'sidebar'):
            self.sidebar.update_file_status()
        self.index_progress_state = None
        self._update_token_dashboard()
        print("Indexing complete")

    def closeEvent(self, event):
        """Handle application close event."""
        self.project_controller.shutdown_on_close()
        # Force hard exit to avoid destructor issues
        import os
        os._exit(0)

    def close_project(self):
        # Save state, cleanup, and clear last_project setting
        self._shutdown_project_session(clear_last_project=True)
        
        # Switch to Welcome
        self.stack.setCurrentWidget(self.welcome_widget)

    def _shutdown_project_session(self, clear_last_project=False):
        """Common logic for closing a project session."""
        # Save state before closing
        self.save_project_state()
        
        # Clear state
        self.project_manager.root_path = None
        self.sidebar.model.setRootPath("")
        self.setWindowTitle("Inkwell AI")
        
        # Close all tabs
        self.editor.tabs.clear()
        self.editor.open_files.clear()
        
        # Clear chat
        self.save_current_chat_session()  # Save before clearing
        self.chat.clear_chat()
        self.chat_history = []
        self._raw_ai_responses = []  # Clear raw responses tracking
        
        # Cancel RAG indexing worker immediately
        try:
            if hasattr(self, 'index_worker') and self.index_worker is not None:
                self.index_worker.cancel()
                self.index_worker = None
        except Exception:
            pass
        self.rag_engine = None
        
        # Clear last project setting if requested (e.g. user explicitly closed project)
        if clear_last_project:
            self.settings.setValue("last_project", "")
        
        # Update Welcome Screen
        self.update_welcome_screen()
        self._update_token_dashboard(0)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Re-register tools based on updated project settings
            try:
                enabled = self.project_manager.get_enabled_tools()
                if enabled is None:
                    register_default_tools()
                else:
                    register_by_names(enabled)
            except Exception:
                pass
            # After settings are saved, refresh model controls
            self.update_model_controls()

    def open_image_studio(self):
        # Check if already open
        index = self.editor.tabs.indexOf(self.image_gen)
        if index >= 0:
            self.editor.tabs.setCurrentIndex(index)
        else:
            self.editor.add_tab(self.image_gen, "Image Studio")

    def on_file_double_clicked(self, index):
        file_path = self.sidebar.model.filePath(index)
        if not self.sidebar.model.isDir(index):
            # Check if already open to avoid overwriting unsaved changes
            if file_path in self.editor.open_files:
                self.editor.open_file(file_path, None) # Content ignored if open
            else:
                # Check extension
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    self.editor.open_file(file_path, None)
                else:
                    content = self.project_manager.read_file(file_path)
                    if content is not None:
                        self.editor.open_file(file_path, content)

    def handle_batch_edit(self, path, content):
        instruction, ok = QInputDialog.getText(self, "Batch Edit", "Enter instruction for processing (e.g. 'Fix typos'):")
        if ok and instruction:
            # Create progress dialog
            self.progress = QProgressDialog("Processing chunks...", "Cancel", 0, 100, self)
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            provider = self.get_llm_provider()
            model = self.settings.value("ollama_model", "llama3")
            
            self.batch_worker = BatchWorker(provider, model, content, instruction)
            self.batch_worker.progress_updated.connect(self.on_batch_progress)
            self.batch_worker.finished.connect(lambda result: self.on_batch_finished(path, result))
            self.batch_worker.error_occurred.connect(self.on_batch_error)
            
            self.progress.canceled.connect(self.batch_worker.cancel)
            self.batch_worker.start()

    def on_batch_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.progress.setLabelText(f"Processing chunk {current} of {total}...")

    def on_batch_finished(self, path, result):
        self.progress.close()
        if result:
            # check files open
            if path in self.editor.open_files:
                doc_widget = self.editor.open_files[path]
                doc_widget.replace_content_undoable(result)
                QMessageBox.information(self, "Batch Complete", "Batch processing finished. Changes applied to buffer.")
            else:
                 QMessageBox.warning(self, "Error", "File closed during processing.")
    
    def on_batch_error(self, error):
        self.progress.close()
        QMessageBox.critical(self, "Batch Error", f"An error occurred: {error}")

    def on_tool_finished(self, result_text, extra_data):
        self.chat.remove_thinking()
        
        if extra_data: # Image Results
            # Fix AttributeError: use self.project_manager.root_path instead of self.project_path
            dialog = ImageSelectionDialog(extra_data, self.project_manager.root_path, self)
            if dialog.exec():
                saved_paths = dialog.get_saved_paths()
                if saved_paths:
                    msg_lines = []
                    for p in saved_paths:
                        name = os.path.basename(p)
                        self.chat.append_message("System", f"Image saved to: {name}")
                        msg_lines.append(f"User selected and saved image to {name}")
                    
                    # Notify agent but DO NOT continue chat loop automatically
                    # This prevents the AI from asking "Do you want another?" -> Tool -> Dialog loop
                    result_msg = "\n".join(msg_lines)
                    self.chat_history.append({"role": "user", "content": f"Tool Output: {result_msg}"})
                    self.chat.append_message("System", "Task completed.")
            else:
                 self.chat.append_message("System", "Image selection cancelled.")
                 self.chat_history.append({"role": "user", "content": "Tool Output: User cancelled image selection."})
        else:
            # Text result
            # We append it to chat as a system/tool message but don't show it to user necessarily? 
            # Or show it? Usually showing "Tool Output" is good.
            # self.chat.append_message("Tool", result_text[:500] + "..." if len(result_text) > 500 else result_text)
            
            # Feed back to LLM
            self.continue_chat_with_tool_result(result_text)

    def continue_chat_with_tool_result(self, result):
        # We need to send this result back to the LLM as if it were a system observation
        # or just context, to continue the generation.
        # Simple approach: append to history and trigger chat again.
        
        # We don't necessarily want this in the visible user chat history if it's long data.
        # But for simplicity, we treat it as a "System" message in the context.
        # self.chat_history is a list of dicts.
        
        # Context to LLM:
        prompt = f"Tool Output: {result}\n\nContinue responding to the user."
        
        # Trigger chat
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        
        # We need to construct context including this new info
        # We can append it to the last message contextually
        context = [] # We rely on history mostly
        
        # Add to history structure but maybe NOT UI if we want to keep it clean?
        # Let's add to UI for transparency
        if len(result) < 200:
            self.chat.append_message("Tool", result)
        else:
            self.chat.append_message("Tool", f"Result data ({len(result)} chars)...")

        # Manually append to self.chat_history so worker picks it up?
        # ChatWorker uses self.chat_history.
        # But ChatWorker expects {"role":, "content":}
        # Using "user" role often works better for forcing the model to pay attention to the new "data provided"
        self.chat_history.append({"role": "user", "content": f"Tool Output: {result}"})
        
        self.chat.show_thinking()
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )
        
        # Inject Project Structure
        if self.project_manager.root_path:
            structure = self.project_manager.get_project_structure()
            # We truncate if it's too huge, but assuming it fits for now
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            
        # Add active file context again? ChatWorker does it.
        
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            enabled_tools=self.project_manager.get_enabled_tools(),
        )
        self.worker.response_received.connect(self.chat_controller.on_chat_response)
        self.worker.start()

    def handle_save_chat(self, chat_content):
        """Save chat contents as a new file in the project."""
        if not self.project_manager.get_root_path():
            QMessageBox.warning(self, "No Project", "Please open a project first to save chat.")
            return
        
        root_path = self.project_manager.get_root_path()
        
        # Open folder selection dialog
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save chat",
            root_path,
            QFileDialog.ShowDirsOnly
        )
        
        if not folder:
            return
        
        # Verify folder is within project
        if not os.path.commonpath([folder, root_path]) == root_path:
            QMessageBox.warning(self, "Invalid Folder", "Please select a folder within the project.")
            return
        
        # Ask user for filename
        filename, ok = QInputDialog.getText(
            self, "Save Chat", "Enter filename (without extension):",
            text="chat_export"
        )
        
        if ok and filename:
            # Ensure it doesn't have extension already
            if '.' in filename:
                filename = filename.split('.')[0]
            
            # Use relative path from root for save_file
            relative_folder = os.path.relpath(folder, root_path)
            if relative_folder == '.':
                relative_path = f"{filename}.md"
            else:
                relative_path = os.path.join(relative_folder, f"{filename}.md")
            
            full_path = os.path.join(root_path, relative_path)
            
            # Check if file exists
            if os.path.exists(full_path):
                reply = QMessageBox.question(
                    self, "File Exists",
                    f"{filename}.md already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            try:
                self.project_manager.save_file(relative_path, chat_content)
                QMessageBox.information(self, "Success", f"Chat saved to {relative_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save chat: {e}")

    def handle_copy_chat_to_file(self, chat_content):
        """Copy chat contents to the currently open file."""
        if not self.editor.open_files:
            QMessageBox.warning(self, "No File Open", "Please open a file first to copy chat contents.")
            return
        
        current_path, current_content = self.editor.get_current_file()
        
        if not current_path:
            QMessageBox.warning(self, "No File Open", "Please open a file first to copy chat contents.")
            return
        
        # Ask user how to append
        reply = QMessageBox.question(
            self, "Append Chat",
            f"Append chat to {current_path}?\n\nYes = Append to end\nNo = Replace contents",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return
        
        if reply == QMessageBox.Yes:
            # Append to end
            new_content = (current_content if current_content else "") + "\n\n" + chat_content
        else:
            # Replace contents
            new_content = chat_content
        
        # Apply to buffer (Undoable)
        doc_widget = self.editor.open_files[current_path]
        doc_widget.replace_content_undoable(new_content)
        self.statusBar().showMessage(f"Chat copied to {current_path} (not saved yet)", 3000)
    
    def handle_message_deleted(self, msg_index):
        """Handle deletion of a chat message."""
        if msg_index < len(self.chat_history):
            # Remove from history
            del self.chat_history[msg_index]
            
            # Remove from chat display
            del self.chat.messages[msg_index]
            self.chat.rebuild_chat_display()
            
            self.statusBar().showMessage("Message deleted", 2000)
    
    def handle_message_edited(self, msg_index, new_content):
        """Handle editing of a chat message."""
        if msg_index < len(self.chat_history):
            # Update history with new content
            self.chat_history[msg_index]['content'] = new_content
            
            self.statusBar().showMessage("Message edited", 2000)
    
    def handle_regenerate(self):
        """Regenerate the last AI response."""
        if not self.chat_history:
            return
        
        # Find the last assistant message and last user message before it
        last_assistant_idx = None
        last_user_idx = None
        
        for i in range(len(self.chat_history) - 1, -1, -1):
            if self.chat_history[i]['role'] == 'assistant' and last_assistant_idx is None:
                last_assistant_idx = i
            elif self.chat_history[i]['role'] == 'user' and last_assistant_idx is not None and last_user_idx is None:
                last_user_idx = i
                break
        
        if last_assistant_idx is None:
            QMessageBox.information(self, "Nothing to Regenerate", "No AI response found to regenerate.")
            return
        
        # Remove the last assistant message
        del self.chat_history[last_assistant_idx]
        del self.chat.messages[last_assistant_idx]
        self.chat.rebuild_chat_display()
        
        # Show thinking indicator
        self.chat.show_thinking()
        
        # Resend the request
        provider = self.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        
        # Get RAG context if available
        context = None
        if self.rag_engine and last_user_idx is not None:
            query = self.chat_history[last_user_idx]['content']
            print(f"DEBUG: Querying RAG for: {query}")
            context = self.rag_engine.query(query)
            print(f"DEBUG: Retrieved {len(context) if context else 0} chunks")
        
        # Build system prompt
        system_prompt = self.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are a helpful AI assistant.")
        )
        
        # Include project structure if enabled
        if self.project_manager.root_path and self.settings.value("include_project_structure", True, type=bool):
            structure = self.project_manager.get_project_structure()
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
        
        enabled_tools = self.project_manager.get_enabled_tools()
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=None,
            enabled_tools=enabled_tools,
        )
        self.worker.response_received.connect(self.chat_controller.chat_controller.on_chat_response)
        self.worker.start()
    
    def save_current_chat_session(self):
        """Save the current chat session to history."""
        if not self.chat_history:
            self.statusBar().showMessage("No chat to save", 2000)
            return
        
        # Get title from first user message
        title = "Untitled Chat"
        for msg in self.chat_history:
            if msg['role'] == 'user':
                title = msg['content'][:50]  # First 50 chars
                if len(msg['content']) > 50:
                    title += "..."
                break
        
        # Create session object
        from datetime import datetime
        session = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'title': title,
            'messages': list(self.chat_history)  # Copy the list
        }
        
        # Add to history
        chat_sessions = self.settings.value("chat_history", [])
        if not isinstance(chat_sessions, list):
            chat_sessions = []
        
        chat_sessions.append(session)
        
        # Keep only last 50 sessions to avoid bloat
        if len(chat_sessions) > 50:
            chat_sessions = chat_sessions[-50:]
        
        self.settings.setValue("chat_history", chat_sessions)
        self.statusBar().showMessage("Chat saved to history", 2000)
    
    def open_chat_history(self):
        """Open the chat history dialog."""
        from gui.dialogs.chat_history_dialog import ChatHistoryDialog
        
        dialog = ChatHistoryDialog(self.settings, self)
        dialog.message_copy_requested.connect(self.copy_message_to_current_chat)
        dialog.exec()
    
    def copy_message_to_current_chat(self, message_content):
        """Copy a message from history to current chat and send it."""
        # Add to input field but don't send automatically
        self.chat.input_field.setPlainText(message_content)
        self.chat.input_field.setFocus()

    def export_debug_log(self):
        """Export current chat session and debug info to a timestamped file."""
        from datetime import datetime
        
        if not self.project_manager.root_path:
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return
        
        # Create .debug folder if needed
        debug_dir = os.path.join(self.project_manager.root_path, '.debug')
        os.makedirs(debug_dir, exist_ok=True)
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.join(debug_dir, f"session_{timestamp}.md")
        
        # Gather session info
        provider_name = self.settings.value("llm_provider", "Ollama")
        model_name = self.settings.value("ollama_model", "llama3")
        context_level = getattr(self.chat_controller, "context_level", "visible")
        
        # Build debug content
        content = f"""# Debug Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Session Info
- **Project:** {self.project_manager.root_path}
- **Provider:** {provider_name}
- **Model:** {model_name}
- **Context Level:** {context_level}
- **Token Usage:** {self._last_token_usage or '---'}

## Chat History (Rendered with Parsed Links)

"""
        
        # Add chat messages (rendered/processed version with links)
        for sender, text in self.chat.messages:
            content += f"\n### {sender}\n\n{text}\n\n---\n"
        
        # Add raw AI responses section (before parsing, shows original PATCH/UPDATE/diff blocks)
        raw_ai_responses = getattr(self.chat_controller, "_raw_ai_responses", [])
        if raw_ai_responses:
            content += "\n\n## Raw AI Responses (Before Parsing)\n\n"
            for idx, raw_resp in enumerate(raw_ai_responses, 1):
                content += f"\n### AI Response #{idx}\n\n```\n{raw_resp}\n```\n\n---\n"
        
        # Add pending edits info
        pending_edits = getattr(self.chat_controller, "pending_edits", {})
        if pending_edits:
            content += "\n## Pending Edits\n\n"
            for edit_id, (path, new_content) in pending_edits.items():
                content += f"### {path} (ID: {edit_id})\n\n```\n{new_content[:500]}...\n```\n\n"
        
        # Write to file
        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.statusBar().showMessage(f"Debug log exported to {os.path.relpath(debug_file, self.project_manager.root_path)}", 3000)
            QMessageBox.information(self, "Export Complete", f"Debug log saved to:\n{os.path.relpath(debug_file, self.project_manager.root_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export debug log: {e}")

    def on_message_copied(self, kind: str):
        msg = "Copied to clipboard"
        if kind == "message":
            msg = "Message copied to clipboard"
        elif kind == "chat":
            msg = "Chat copied to clipboard"
        try:
            self.statusBar().showMessage(msg, 2000)
        except Exception:
            pass

    def on_file_renamed(self, old_path, new_path):
        """Update open editor tabs when a file is renamed from the sidebar."""
        try:
            self.editor.update_open_file_path(old_path, new_path)
            # Record operation and clear redo stack
            self.file_ops_history.append({"type": "rename", "old": old_path, "new": new_path})
            self.file_ops_redo.clear()
            self.statusBar().showMessage(f"Renamed: {os.path.basename(old_path)} → {os.path.basename(new_path)}", 3000)
        except Exception as e:
            # Non-critical; just log
            print(f"WARN: Failed to update editor after rename: {e}")

    def on_file_moved(self, old_path, new_path):
        """Update open editor tabs when a file is moved from the sidebar."""
        try:
            self.editor.update_open_file_path(old_path, new_path)
            # Record operation and clear redo stack
            self.file_ops_history.append({"type": "move", "old": old_path, "new": new_path})
            self.file_ops_redo.clear()
            self.statusBar().showMessage(f"Moved: {os.path.basename(old_path)} → {os.path.basename(new_path)}", 3000)
        except Exception as e:
            print(f"WARN: Failed to update editor after move: {e}")

    def _perform_move(self, src, dst):
        """Move/rename path with basic validation and conflict checking."""
        if not os.path.exists(src):
            QMessageBox.warning(self, "Not Found", f"Source does not exist: {src}")
            return False
        if os.path.exists(dst):
            reply = QMessageBox.question(
                self, "File Exists",
                f"{os.path.basename(dst)} exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return False
            # If overwriting a file with a folder or vice versa could be unsafe; rely on shutil semantics
        try:
            shutil.move(src, dst)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to move: {e}")
            return False

    def undo_file_change(self):
        """Undo the last file rename/move."""
        if not self.file_ops_history:
            self.statusBar().showMessage("No file changes to undo", 2000)
            return
        op = self.file_ops_history.pop()
        src = op["new"]
        dst = op["old"]
        if self._perform_move(src, dst):
            # Update editor tabs
            try:
                self.editor.update_open_file_path(src, dst)
            except Exception:
                pass
            # Push to redo stack
            self.file_ops_redo.append(op)
            self.statusBar().showMessage(f"Undid {op['type']}: {os.path.basename(src)} → {os.path.basename(dst)}", 3000)

    def redo_file_change(self):
        """Redo the last undone file rename/move."""
        if not self.file_ops_redo:
            self.statusBar().showMessage("No file changes to redo", 2000)
            return
        op = self.file_ops_redo.pop()
        src = op["old"]
        dst = op["new"]
        if self._perform_move(src, dst):
            # Update editor tabs
            try:
                self.editor.update_open_file_path(src, dst)
            except Exception:
                pass
            # Push back to history
            self.file_ops_history.append(op)
            self.statusBar().showMessage(f"Redid {op['type']}: {os.path.basename(src)} → {os.path.basename(dst)}", 3000)

    def _update_token_dashboard(self, token_usage=None, token_breakdown=None):
        """Stub for token usage tracking (to be implemented)."""
        # Store for potential future use
        if token_usage is not None:
            self._last_token_usage = token_usage
        # TODO: Display token usage in UI (statusbar, dedicated widget, etc.)
        pass


