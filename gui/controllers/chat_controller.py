"""Controller for chat message handling, LLM integration, and edit proposals.

This controller handles all chat-related operations including:
- Message processing and LLM communication
- Edit proposal parsing (UPDATE and PATCH blocks)
- Tool execution
- Chat history management
- Message operations (delete, edit, regenerate, continue)
"""

import os
import re
import uuid
import hashlib
import html as _html
import json
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QSettings, QTimer

from gui.workers import ChatWorker, ToolWorker
from gui.dialogs.diff_dialog import DiffDialog
from gui.dialogs.batch_diff_dialog import BatchDiffDialog
from gui.dialogs.chat_history_dialog import ChatHistoryDialog
from gui.dialogs.image_dialog import ImageSelectionDialog
from gui.editor import DocumentWidget, ImageViewerWidget
from core.diff_engine import EditBatch, FileEdit
from core.diff_parser import DiffParser
from core.path_resolver import PathResolver
from core.model_manager import ModelPreferenceStore, ModelSettings


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic.
    Approximates: ~1 token per 4 characters on average.
    """
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(words // 2, chars // 4)


class ChatController:
    """Handles all chat and LLM interaction logic."""
    
    def __init__(self, main_window):
        """Initialize chat controller.
        
        Args:
            main_window: The MainWindow instance
        """
        self.window = main_window
        self.settings = QSettings("InkwellAI", "InkwellAI")
        self.chat_history = []  # List of {"role": "user/assistant", "content": "..."}
        self.pending_edits = {}  # id -> (path, content) - legacy single edits
        self.pending_edit_batches = {}  # batch_id -> EditBatch - new batch system
        self._raw_ai_responses = []  # Track raw AI responses before parsing
        self._last_selection_info = None  # Store selection context
        self._last_token_usage = None
        self.context_level = "visible"  # Default context level
        self.chat_mode = "edit"  # Default mode: edit or ask
        self.tools_enabled = True  # Default tools enabled state
        self.worker = None
        self.tool_worker = None
        self.batch_worker = None
        self._last_progress_note = None
        self._structured_support_cache = {}
        self._current_model_settings: ModelSettings | None = None
        self._current_model_supports_structured: bool | None = None
        self._current_provider: str | None = None
        self._current_model: str | None = None
        self.manual_context_files: list[str] = []
        self._input_debounce_timer = QTimer()
        self._input_debounce_timer.setSingleShot(True)
        self._input_debounce_timer.setInterval(350)
        self._input_debounce_timer.timeout.connect(self.refresh_context_sources_view)
        
        # Pagination state for tool searches
        self._current_search_context = None  # Stores (tool, query, extra_settings)
        self._current_page = 1
        
        # Initialize diff parser and path resolver
        self._diff_parser = None
        self._path_resolver = None
        self._init_diff_system()
    
    def _init_diff_system(self):
        """Initialize the diff parsing system."""
        if self.window.project_manager.root_path:
            self._path_resolver = PathResolver(self.window.project_manager.root_path)
            self._diff_parser = DiffParser(self._path_resolver, self.window.project_manager)
            print(f"DEBUG: Diff system initialized with project root: {self.window.project_manager.root_path}")
        else:
            print("DEBUG: Cannot initialize diff system - no project root")
    
    def reinit_diff_system(self):
        """Reinitialize diff system after project change.
        
        Call this when a new project is opened.
        """
        self._init_diff_system()
    
    def _use_batch_mode(self) -> bool:
        """Check if batch diff mode is enabled.
        
        Returns:
            True if batch mode should be used
        """
        enabled = self.settings.value("use_batch_diff_dialog", True, type=bool)
        print(f"DEBUG: Batch mode enabled: {enabled}, diff_parser exists: {self._diff_parser is not None}")
        return enabled
        
    def handle_chat_message(self, message):
        """Handle incoming chat message from user.
        
        Args:
            message: User message text
        """
        # Proactively prune any stale per-message context from prior history
        # so each send reassesses and only includes the currently relevant files.
        # This prevents previously injected Context/Citations blocks from
        # lingering in earlier user messages and inflating the next request.
        self._prune_prior_context_from_history()

        print(f"DEBUG: Context level for this message: {self.context_level}")
        # Debug structured injection
        if self._maybe_handle_structured_debug(message):
            # Also display the user command in chat
            self.window.chat.append_message("User", message)
            return
        self.chat_history.append({"role": "user", "content": message})
        self._last_progress_note = None
        # Update planned context list as chat content changes
        try:
            self.refresh_context_sources_view()
        except Exception:
            pass
        
        provider = self.window.get_llm_provider()
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "LM Studio":
            provider_name = "LM Studio (API)"
            self.settings.setValue("llm_provider", provider_name)
        if provider_name == "Ollama":
            model = self.settings.value("ollama_model", "llama3")
        else:
            model = self.settings.value("lm_studio_model", "llama3")

        self._update_active_model_settings(provider_name, model)
            
        token_usage = estimate_tokens(message)
        token_breakdown = {"User message": token_usage}

        # Update chat header to reflect current model
        loaded_models = None
        try:
            models = provider.list_models()
            vision_models = [m for m in models if provider.is_vision_model(m)]
            loaded_models = provider.get_loaded_models() if hasattr(provider, "get_loaded_models") else None
            self.window.chat.update_model_info(provider_name, model, models, vision_models, loaded_models)
        except Exception:
            pass

        # Inform the user about model load status and proactively load if needed
        try:
            loaded_state = None
            if hasattr(provider, "is_model_loaded"):
                loaded_state = provider.is_model_loaded(model)

            # If we can determine it's not loaded, load it explicitly via ModelManager
            if loaded_state is False:
                # Show spinner in chat UI
                try:
                    self.window.chat.show_model_loading(model)
                except Exception:
                    pass
                self.window.chat.append_message("System", f"Model '{model}' is not loaded. Loading now…")
                try:
                    from core.model_manager import ModelManager, build_default_sources
                    sources = build_default_sources(self.settings)
                    mgr = ModelManager(sources)
                    ok, err = mgr.load_model(provider_name, model)
                    if ok:
                        # Allow provider to update internal state (~1s is enough in practice)
                        import time
                        time.sleep(1)
                        self.window.chat.append_message("System", f"Model '{model}' loaded.")
                        # Refresh model controls to update loaded indicator
                        try:
                            self.window.update_model_controls(refresh=True)
                        except Exception:
                            pass
                    else:
                        self.window.chat.append_message("System", f"Failed to load model '{model}': {err}")
                except Exception as exc:
                    self.window.chat.append_message("System", f"Error while loading model '{model}': {exc}")
                finally:
                    try:
                        self.window.chat.hide_model_loading()
                    except Exception:
                        pass
            elif loaded_state is True:
                self.window.chat.append_message("System", f"Model '{model}' is already loaded.")
            else:
                # Unknown loaded state; show currently loaded roster if available
                if loaded_models is not None:
                    roster = ", ".join(loaded_models) if loaded_models else "none"
                    self.window.chat.append_message("System", f"Loaded models: {roster}.")
        except Exception:
            pass
        
        # Retrieve context if RAG is active and context level allows
        context = []
        mentioned_files = set()
        included_files = set()  # Track all files already included in system prompt
        
        if self.context_level != "none" and self.window.rag_engine:
            print(f"DEBUG: Querying RAG for: {message}")
            context = self.window.rag_engine.query(message, n_results=3, include_metadata=True)
            print(f"DEBUG: Retrieved {len(context)} chunks")
            
            # Extract mentioned file paths (do NOT add full-file tokens; we only count chunk text later)
            rag_file_info = []
            for chunk in context:
                meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                source = meta.get("source")
                if source:
                    mentioned_files.add(source)
                    # Track included files for de-duplication of active/open tabs
                    included_files.add(source)
                    # Log approximate chunk token cost rather than full file
                    chunk_tokens = estimate_tokens(chunk.get("text", "")) if isinstance(chunk, dict) else estimate_tokens(str(chunk))
                    rag_file_info.append(f"{source} (~{chunk_tokens} chunk tokens)")
                    token_breakdown[f"RAG chunk: {source}"] = token_breakdown.get(f"RAG chunk: {source}", 0) + chunk_tokens
                    token_usage += chunk_tokens

            if rag_file_info:
                print(f"DEBUG: Files from RAG context: {', '.join(rag_file_info)}")
            
        # Get base system prompt and enhance it with edit format instructions
        self.window.chat.show_thinking()
        
        base_system_prompt = self.window.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant. Help users with their fiction, characters, worldbuilding, and storytelling.")
        )
        
        # Check if image generation is enabled
        enabled_tools = self.window.project_manager.get_enabled_tools()
        image_gen_enabled = enabled_tools is None or "GENERATE_IMAGE" in enabled_tools
        
        # Add edit format instructions only in edit mode
        system_prompt = base_system_prompt
        if self.chat_mode == "edit":
            edit_instructions = self._get_edit_instructions(image_gen_enabled)
            system_prompt += edit_instructions
        else:
            # In ask mode, explicitly instruct to not generate patches/diffs
            ask_mode_header = (
                "\n\n" + "="*60 + "\n"
                "CRITICAL: YOU ARE IN ASK MODE\n"
                "="*60 + "\n"
                "DO NOT generate file edits, patches, diffs, or any UPDATE/PATCH blocks.\n"
                "DO NOT use :::UPDATE::: or :::PATCH::: markers.\n"
                "When asked to rewrite, modify, or edit code/text:\n"
                "  - Show the revised content as plain text in your response\n"
                "  - Format it nicely with code blocks if appropriate\n"
                "  - The user will manually copy what they need\n"
                "You are a READ-ONLY assistant in this mode.\n"
                "="*60 + "\n"
            )
            system_prompt += ask_mode_header
            
        # Add Active File Context based on context level
        active_path, active_content = self.window.editor.get_current_file()

        # Include manual context files selected by user (ahead of active/other open files)
        system_prompt, token_usage, token_breakdown = self._inject_manual_context(
            system_prompt,
            token_usage,
            token_breakdown,
            included_files,
        )
        
        # Include active file if not in "none" mode, not already in RAG context, and not excluded
        if active_path and active_content and self.context_level != "none" and active_path not in included_files:
            # Skip excluded directories like .debug
            if self.window.rag_engine and self.window.rag_engine._should_exclude_file(active_path):
                print(f"DEBUG: Skipping active file {active_path} (in excluded directory)")
            else:
                tokens = estimate_tokens(active_content)
                print(f"DEBUG: Including active file in context: {active_path} ({tokens} tokens)")
                system_prompt += f"\nCurrently Open File ({active_path}):\n{active_content}\n"
                token_usage += tokens
                token_breakdown[f"Active: {active_path}"] = tokens
                included_files.add(active_path)  # Mark as included
        elif active_path and active_path in included_files:
            print(f"DEBUG: Skipping active file {active_path} (already in RAG context)")
        
        # Add other open tabs if context level is "visible_tabs", "all_open" or "full"
        if self.context_level in ("visible_tabs", "all_open", "full"):
            open_files = self._collect_open_files(active_path, system_prompt, token_usage, token_breakdown, included_files)
            if open_files:
                print(f"DEBUG: Including open tabs in context: {', '.join(open_files)}")
        
        # Check Vision Capability and collect images
        is_vision = provider.is_vision_model(model)
        attached_images, attached_image_names = self._collect_images(is_vision, message, system_prompt)
        
        if is_vision:
            system_prompt += "\n\n[System] Current model is VISION CAPABLE. You can see images provided in the context."
            if attached_image_names:
                self.window.chat.append_message("System", f"<i>Attached images: {', '.join(attached_image_names)}</i>")
        else:
            system_prompt += "\n\n[System] Current model is TEXT ONLY."

        # Inject Project Structure only for "full" context to prevent overflow
        if self.context_level == "full" and self.window.project_manager.root_path:
            structure = self.window.project_manager.get_project_structure()
            # Be conservative: cap to ~8000 chars (~2000 tokens heuristically)
            if len(structure) > 8000:
                structure = structure[:8000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            est = estimate_tokens(structure)
            token_usage += est
            token_breakdown["Project structure"] = est
            
        # Include selection info if present
        self._include_selection_info(active_path, token_usage, token_breakdown)
        
        # Add final reminder for ask mode
        if self.chat_mode == "ask":
            print("DEBUG: ASK MODE ACTIVE - Disabling edit instructions")
            system_prompt += (
                "\n\n" + "="*60 + "\n"
                "REMINDER: ASK MODE - No file modifications, no patches, no diffs.\n"
                "Provide helpful information and plain text suggestions only.\n"
                "="*60
            )
        
        # Disable tools if tools checkbox is unchecked
        if not self.tools_enabled:
            print("DEBUG: TOOLS DISABLED - Removing tools from enabled list")
            enabled_tools = set()  # Empty set disables all tools
        
        print(f"DEBUG: Enabled tools for this request: {enabled_tools}")
        print(f"DEBUG: Chat mode: {self.chat_mode}")
        print(f"DEBUG: Tools enabled: {self.tools_enabled}")
        print(f"DEBUG: Token usage total={token_usage} breakdown={token_breakdown}")
             
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=attached_images if is_vision else None,
            enabled_tools=enabled_tools,
            mode=self.chat_mode,
            structured_enabled=bool(self.settings.value("structured_enabled", False, type=bool)),
            schema_id=self._select_schema_id(enabled_tools, self.chat_mode) if self.settings.value("structured_enabled", False, type=bool) else None,
        )
        self.worker.response_thinking_start.connect(self.on_chat_thinking_start)
        self.worker.response_thinking_chunk.connect(self.on_chat_thinking_chunk)
        self.worker.response_thinking_done.connect(self.on_chat_thinking_done)
        self.worker.response_chunk.connect(self.on_chat_chunk)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.progress_update.connect(self.on_chat_progress)
        self.worker.start()

        # Keep context file list in sync in UI
        self._refresh_context_file_view()

        # Update dashboard with latest token estimate
        # RAG chunk tokens were already counted above to avoid double counting
        self.window._update_token_dashboard(token_usage, token_breakdown)

    def _prune_prior_context_from_history(self):
        """Strip any previously injected context blocks from older user messages.

        Ensures that when the user reduces context (e.g., from multiple files
        down to one), prior context text (e.g., "Context:" and "Citations:")
        does not persist in the conversation history sent to the model.

        Only affects messages before the latest user message being sent.
        """
        try:
            import re
            if not self.chat_history:
                return
            # Process all but the last entry (which is about to be augmented fresh)
            for i in range(0, len(self.chat_history) - 1):
                msg = self.chat_history[i]
                if not isinstance(msg, dict):
                    continue
                if msg.get('role') != 'user':
                    continue

                content = msg.get('content', '')
                if not content:
                    continue

                # Remove any prior Context: ... block (greedy until end or citations)
                # Matches a "Context:" header followed by any content up to the end
                # of the message or before a trailing reminder line.
                cleaned = re.sub(r"\n\nContext:\n.*?(?=$|\n\nREMINDER:)",
                                 "", content, flags=re.DOTALL)

                # Remove any prior Citations: ... block
                cleaned = re.sub(r"\n\nCitations:\n.*?(?=$|\n\nREMINDER:)",
                                 "", cleaned, flags=re.DOTALL)

                # Also remove any previously appended selection hint header to avoid
                # unintended carry-over (keeps the raw message concise).
                cleaned = re.sub(r"\n\nSelected Range in .*?: L\d+-L\d+\nSelected Text:\n```text\n.*?\n```\n.*?(?=$)",
                                 "", cleaned, flags=re.DOTALL)

                if cleaned != content:
                    self.chat_history[i]['content'] = cleaned
        except Exception as e:
            print(f"DEBUG: Failed to prune prior context from history: {e}")

    def on_chat_progress(self, status: str):
        if not status:
            return
        if status == self._last_progress_note:
            return
        self._last_progress_note = status
        self.window.chat.append_message("System", status)

    def _get_edit_instructions(self, image_gen_enabled):
        """Build edit format instructions.
        
        Uses custom instructions from settings if available, otherwise defaults.
        """
        # Check for custom instructions
        custom_instructions = self.settings.value("custom_edit_instructions", "").strip()
        if custom_instructions:
            # User has provided custom instructions, use them
            return custom_instructions
        
        # Use default instructions
        edit_instructions = (
            "\n\n## Tools and Directives\n"
            "\n"
            "When the user requests searches or image lookups, IMMEDIATELY use the appropriate tool:\n"
            "- For image searches (Derpibooru, Tantabus, E621): :::TOOL:TOOLNAME:query:::\n"
            "- For web searches: :::TOOL:SEARCH:query:::\n"
            "- For image search: :::TOOL:IMAGE:query:::\n"
            "Stop after outputting the tool command. Do not add explanations before the tool.\n"
            "\n"
            "## Edit Formats\n"
            "Use PATCH for line-level edits or range replacements:\n"
            ":::PATCH path/to/file.md\n"
            "L42: old text => new text\n"
            "L20-L23:\n"
            "New content for lines 20-23...\n"
            "Multiple lines here...\n"
            ":::END:::\n"
            "\n"
            "Use UPDATE when replacing entire file or large sections:\n"
            ":::UPDATE path/to/file.md\n"
            "Complete new file content...\n"
            ":::END:::\n"
        )
        
        if image_gen_enabled:
            edit_instructions += (
                "\n"
                "Image generation:\n"
                ":::GENERATE_IMAGE:::\n"
                "Prompt: Description...\n"
                ":::END:::\n"
            )
        
        edit_instructions += (
            "\n"
            "CRITICAL RULES:\n"
            "- ALWAYS use :::PATCH::: or :::UPDATE::: directives for file edits\n"
            "- Output ONLY the directive blocks (:::PATCH...:::END:::)\n"
            "- Do NOT wrap directives in code fences (no ```text or ```patch)\n"
            "- Do NOT output edit: links or HTML anchors\n"
            "- Do NOT include reminders or instructions in your response\n"
            "- Do NOT include footnotes or citations unless specifically requested\n"
            "- Explanations can come AFTER the directive block\n"
            "- When editing selections repeatedly, continue using :::PATCH::: format for each edit\n"
        )
        return edit_instructions
    
    def _collect_open_files(self, active_path, system_prompt, token_usage, token_breakdown, included_files=None):
        """Collect content from open tabs, skipping already-included files."""
        if included_files is None:
            included_files = set()
        
        open_files = []
        for i in range(self.window.editor.tabs.count()):
            tab_widget = self.window.editor.tabs.widget(i)
            tab_path = tab_widget.property("file_path") if hasattr(tab_widget, 'property') else None
            
            # Skip active file, already-included files, and excluded directories
            if tab_path and tab_path != active_path and tab_path not in included_files:
                # Skip excluded directories like .debug
                if self.window.rag_engine and self.window.rag_engine._should_exclude_file(tab_path):
                    print(f"DEBUG: Skipping open file {tab_path} (in excluded directory)")
                    continue
                
                try:
                    content = self.window.project_manager.read_file(tab_path)
                    if content:
                        tokens = estimate_tokens(content)
                        open_files.append(f"{tab_path} ({tokens} tokens)")
                        system_prompt += f"\nOpen File ({tab_path}):\n{content}\n"
                        token_usage += tokens
                        token_breakdown[f"Open tab: {tab_path}"] = tokens
                        included_files.add(tab_path)  # Mark as included
                except Exception:
                    pass
            elif tab_path and tab_path in included_files:
                print(f"DEBUG: Skipping open file {tab_path} (already included in context)")
        
        return open_files
    
    def _collect_images(self, is_vision, message, system_prompt):
        """Collect images from open tabs and message references."""
        attached_images = []
        attached_image_names = []
        
        if not is_vision:
            return attached_images, attached_image_names
            
        # Collect all open images from tabs
        for i in range(self.window.editor.tabs.count()):
            widget = self.window.editor.tabs.widget(i)
            if isinstance(widget, ImageViewerWidget):
                path = widget.property("file_path")
                if path and os.path.exists(path):
                    try:
                        b64 = self.window.project_manager.get_image_base64(path)
                        if b64:
                            attached_images.append(b64)
                            attached_image_names.append(os.path.basename(path))
                    except Exception as e:
                        print(f"DEBUG: Error reading open image {path}: {e}")
        
        # Also auto-detect images referenced in the message
        found_paths = self.window.project_manager.find_images_in_text(message)
        if found_paths:
            print(f"DEBUG: Found referenced images in message: {found_paths}")
            for p in found_paths:
                # Skip if already added from open tabs
                if any(b64 == self.window.project_manager.get_image_base64(p) for b64 in attached_images):
                    continue
                b64 = self.window.project_manager.get_image_base64(p)
                if b64:
                    attached_images.append(b64)
                    attached_image_names.append(os.path.basename(p))
                    
        return attached_images, attached_image_names
    
    def _include_selection_info(self, active_path, token_usage, token_breakdown):
        """Include text selection info in context."""
        try:
            current_editor = self.window.editor.get_current_editor()
            if current_editor:
                cursor = current_editor.textCursor()
                if cursor and cursor.hasSelection():
                    doc = current_editor.document()
                    start_pos = cursor.selectionStart()
                    end_pos = cursor.selectionEnd()
                    start_block = doc.findBlock(start_pos)
                    end_block = doc.findBlock(end_pos)
                    sel_start_line = start_block.blockNumber() + 1
                    sel_end_line = end_block.blockNumber() + 1
                    sel_text = cursor.selectedText().replace('\u2029', '\n')
                    # Append selection context to the last user message
                    self.chat_history[-1]['content'] += (
                        f"\n\nSelected Range in {active_path}: L{sel_start_line}-L{sel_end_line}\n"
                        f"Selected Text:\n```text\n{sel_text}\n```\n"
                        f"Prefer PATCH targeting the selected lines when possible."
                    )
                    # Store selection info for apply-time restriction
                    self._last_selection_info = {
                        'path': active_path,
                        'start_line': sel_start_line,
                        'end_line': sel_end_line,
                    }
                    # Show a small note in chat
                    self.window.chat.append_message("System", f"<i>Selection sent for {active_path}: L{sel_start_line}-L{sel_end_line}</i>")
                    token_usage += estimate_tokens(sel_text)
                    token_breakdown[f"Selection: {active_path} L{sel_start_line}-L{sel_end_line}"] = estimate_tokens(sel_text)
        except Exception as e:
            print(f"DEBUG: Failed to include selection info: {e}")

    def on_chat_chunk(self, chunk):
        """Handle streamed chunk from LLM (real-time token arrival).
        
        Args:
            chunk: String chunk/token that just arrived from the LLM
        """
        # On first chunk, initialize streaming message block
        if not self.window.chat.streaming_response:
            self.window.chat.begin_streaming_response()
        
        # Append the chunk to the chat display as it arrives
        # This shows tokens appearing in real-time without waiting for full response
        self.window.chat.append_response_chunk(chunk)

    def on_chat_thinking_start(self):
        """Show thinking indicator when model enters reasoning phase."""
        self.window.chat.begin_thinking()

    def on_chat_thinking_chunk(self, chunk):
        """Append thinking text without mixing into final answer."""
        self.window.chat.append_thinking_chunk(chunk)

    def on_chat_thinking_done(self):
        """Hide thinking indicator when reasoning phase ends."""
        self.window.chat.finish_thinking()
    
    def on_chat_response(self, response):
        """Handle response from LLM.
        
        Args:
            response: Raw response text from LLM
        """
        # Remove thinking indicator
        self.window.chat.remove_thinking()
        
        # Store raw response for debug export
        self._raw_ai_responses.append(response)
        
        print(f"DEBUG: Raw AI Response:\n{response}")

        # Structured response handling: attempt JSON parse/validate and render
        structured_enabled = bool(self.settings.value("structured_enabled", False, type=bool))
        schema_id = self.settings.value("structured_schema_id", "None")
        if structured_enabled and schema_id and schema_id != "None":
            try:
                parsed, valid, validation_error = self._parse_and_validate_structured(response, schema_id)
                if parsed is not None:
                    display = self._render_structured_payload(parsed, schema_id)
                    badge = f"<i>Structured ({schema_id}) — {'valid' if valid else 'unvalidated'}.</i>"
                    if validation_error:
                        badge = f"<i>Structured ({schema_id}) — validation failed: {_html.escape(str(validation_error))}</i>"
                    # Add to chat history and display immediately
                    self.chat_history.append({"role": "assistant", "content": display})
                    self.save_current_chat_session()
                    if self.window.chat.streaming_response:
                        self.window.chat.finish_streaming_response(display, raw_text=response)
                    else:
                        # Show a small badge system message followed by the structured content
                        self.window.chat.append_message("System", badge)
                        self.window.chat.append_message("Assistant", display, raw_text=response)
                    return
            except Exception as e:
                print(f"DEBUG: Structured handling failed, falling back to text: {e}")

        # Check for incomplete responses
        if not self.is_response_complete(response):
            print("DEBUG: Response appears incomplete, auto-continuing...")
            self.chat_history.append({"role": "assistant", "content": response})
            self.window.chat.append_message("Assistant", response, raw_text=response)
            self.window.chat.append_message("System", "<i>Response incomplete, continuing...</i>")
            self.window.chat.show_thinking()
            self._continue_response()
            return

        # Add to chat history
        self.chat_history.append({"role": "assistant", "content": response})
        
        # Save to history immediately so current conversation is viewable
        self.save_current_chat_session()
        
        # Parse and display response (this is very complex logic)
        display_response = self._parse_and_display_response(response)

        display_response, raw_for_json = self._maybe_hide_structured_json(display_response, response)
        
        # If we were streaming, replace the streamed content with parsed version
        # Otherwise, add as a new message
        if self.window.chat.streaming_response:
            self.window.chat.finish_streaming_response(display_response, raw_text=raw_for_json)
        else:
            self.window.chat.append_message("Assistant", display_response, raw_text=raw_for_json)
        # Refresh planned context list when chat updates
        try:
            self.refresh_context_sources_view()
        except Exception:
            pass
        
    def is_response_complete(self, response: str) -> bool:
        """Check if response appears complete.
        
        Args:
            response: Response text to check
            
        Returns:
            False if response is likely incomplete
        """
        # Check for incomplete UPDATE blocks
        update_opens = response.count(":::UPDATE")
        update_closes = response.count(":::END:::") + response.count(":::END") + response.count(":::")
        
        if update_opens > 0 and update_closes < update_opens:
            return False
        
        # Check for incomplete GENERATE_IMAGE blocks
        gen_opens = response.count(":::GENERATE_IMAGE")
        if gen_opens > 0 and update_closes < gen_opens:
            return False
        
        # If response ends abruptly with specific tokens
        incomplete_endings = ["- ", "* ", "1. ", ": ", "and ", "or ", "in ", "the "]
        
        if len(response) > 50:
            for ending in incomplete_endings:
                if response.rstrip().endswith(ending):
                    return False
        
        return True

    def _parse_and_display_response(self, response):
        """Parse response for edit blocks and tool commands.
        
        This is the core parsing logic extracted from on_chat_response.
        Handles UPDATE, PATCH, TOOL, and GENERATE_IMAGE blocks.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Formatted HTML response with edit links
        """
        # In ask mode, skip all patch/edit parsing and just display as-is
        if self.chat_mode == "ask":
            print("DEBUG: ASK MODE - Skipping patch parsing, returning response as plain markdown")
            return response
        
        # Check for tool execution requests first
        tool_pattern = r":::TOOL:(.*?):(.*?):::"
        tool_match = re.search(tool_pattern, response)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            query = tool_match.group(2).strip()
            print(f"DEBUG: Executing tool '{tool_name}' with query '{query}'")
            self.window.chat.append_message("System", f"<i>Running tool: {tool_name}...</i>")
            self.window.chat.show_thinking()
            
            self.tool_worker = ToolWorker(
                tool_name, query, 
                enabled_tools=self.window.project_manager.get_enabled_tools(),
                project_manager=self.window.project_manager
            )
            self.tool_worker.finished.connect(self.on_tool_finished)
            self.tool_worker.start()
            return response  # Stop further processing
        
        # Use new batch parsing system if enabled and diff parser is available
        if self._use_batch_mode() and self._diff_parser:
            return self._parse_with_batch_system(response)
        
        # Fall back to legacy parsing
        return self._parse_with_legacy_system(response)
    
    def _parse_with_batch_system(self, response: str) -> str:
        """Parse response using new DiffParser and create EditBatch.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Formatted response with batch edit link
        """
        print(f"DEBUG: _parse_with_batch_system called, diff_parser={self._diff_parser is not None}")
        
        try:
            # Get active file for context
            active_file = None
            try:
                active_file = self.window.editor.get_current_file()[0]
            except Exception:
                pass
            
            print(f"DEBUG: Parsing response (len={len(response)}) with active_file={active_file}")
            
            # Parse response into EditBatch
            batch = self._diff_parser.parse_response(response, active_file)
            
            print(f"DEBUG: Parsed batch with {len(batch.edits)} edits")
            
            if not batch.edits:
                # No edits found, return original response
                print("DEBUG: No edits found in response")
                return response
            
            # Store batch
            batch_id = batch.batch_id
            self.pending_edit_batches[batch_id] = batch
            
            # Create batch link
            files_affected = batch.total_files_affected()
            total_edits = len(batch.edits)
            
            # Remove any existing edit markers from response to avoid clutter
            clean_response = response
            for marker in [":::UPDATE", ":::PATCH", ":::END:::", "```diff"]:
                if marker in clean_response:
                    # Keep context around markers but make them less prominent
                    pass  # For now, keep original response
            
            # Append batch link
            batch_link = f'\n\n<br><b><a href="batch:{batch_id}">📝 Review {total_edits} Changes to {files_affected} Files</a></b><br>\n'
            
            print(f"DEBUG: Created batch {batch_id} with {total_edits} edits affecting {files_affected} files")
            
            return response + batch_link
            
        except Exception as e:
            print(f"ERROR: Failed to parse with batch system: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to legacy system on error
            return self._parse_with_legacy_system(response)
    
    def _parse_with_legacy_system(self, response: str) -> str:
        """Parse response using legacy individual edit system.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Formatted response with individual edit links
        """
        # Capture any edit:XYZ ids already present in the response
        provided_edit_ids = re.findall(r"edit:([0-9a-fA-F-]{6,})", response)
        seen_ids = set()
        provided_edit_ids = [eid for eid in provided_edit_ids if not (eid in seen_ids or seen_ids.add(eid))]

        def next_edit_id() -> str:
            if provided_edit_ids:
                return provided_edit_ids.pop(0)
            return str(uuid.uuid4())

        processing_response = response
        
        # Strip reminder text
        reminder_pattern = r"^[^\n]*REMINDER[^\n]*:.*?\n+"
        processing_response = re.sub(reminder_pattern, "", processing_response, flags=re.IGNORECASE)

        # Parse UPDATE blocks
        pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        matches = re.findall(pattern, processing_response, re.DOTALL)
        
        # Parse PATCH blocks (multiple formats)
        patch_matches = self._parse_patch_blocks(processing_response)
        
        print(f"DEBUG: Found {len(matches)} UPDATE blocks and {len(patch_matches)} PATCH blocks")
        
        display_response = response
        
        # Get active file for path normalization
        try:
            active_path = self.window.editor.get_current_file()[0]
        except Exception:
            active_path = None
        
        non_text_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                               '.mp4', '.avi', '.mov', '.mp3', '.wav',
                               '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}

        # Process UPDATE blocks
        if matches:
            def replace_match(match):
                m_path = self._normalize_edit_path(match.group(1).strip(), active_path)
                m_content = match.group(2).strip().replace('\\n', '\n')

                file_ext = os.path.splitext(m_path)[1].lower()
                if file_ext in non_text_extensions:
                    m_path = os.path.splitext(m_path)[0] + '.txt'

                m_id = next_edit_id()
                self.pending_edits[m_id] = (m_path, m_content)
                return f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>'

            display_response = re.sub(pattern, replace_match, display_response, flags=re.DOTALL)

        # Process PATCH blocks
        if patch_matches:
            display_response = self._process_patch_blocks(patch_matches, display_response, active_path, next_edit_id, non_text_extensions)

        # Process unified diff blocks
        display_response = self._process_diff_blocks(processing_response, display_response, active_path, next_edit_id, non_text_extensions)

        # Process fallback code blocks
        display_response = self._process_code_blocks(processing_response, display_response, active_path, next_edit_id, matches or patch_matches)

        # Parse GENERATE_IMAGE blocks
        gen_pattern = r":::GENERATE_IMAGE:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        gen_matches = re.findall(gen_pattern, response, re.DOTALL)
        
        if gen_matches:
            for content in gen_matches:
                prompt = ""
                workflow = None
                
                for line in content.split('\n'):
                    if line.lower().startswith("prompt:"):
                        prompt = line[7:].strip()
                    elif line.lower().startswith("workflow:"):
                        workflow = line[9:].strip()
                
                if not prompt and content:
                    prompt = content.strip()

                if prompt:
                    print(f"DEBUG: Agent requested image generation: {prompt}")
                    self.window.open_image_studio()
                    self.window.image_gen.generate_from_agent(prompt, workflow)
                    display_response += f'<br><i>Generating image for: "{prompt}"...</i><br>'

        # Clean up unknown edit links
        display_response = self._strip_unknown_edit_links(display_response)
        
        return display_response

    def _select_schema_id(self, enabled_tools: set | None, mode: str) -> str | None:
        """Determine effective schema id for this request.
        Priority: explicit selection in settings → tool-preferred → mode default → None.
        """
        chosen = self.settings.value("structured_schema_id", "None")
        if chosen and chosen != "None":
            return chosen
        # Tool-preferred schema
        try:
            from core.tool_base import get_registry
            sid = get_registry().get_preferred_schema_id(enabled_tools)
            if sid:
                return sid
        except Exception:
            pass
        # Mode defaults
        if mode == "edit":
            return "diff_patch"
        if mode == "ask":
            return "chat_split"
        return None

    def _parse_and_validate_structured(self, response_text: str, schema_id: str):
        """Attempt to parse response as JSON and validate against a schema.

        Returns (parsed_obj, valid_bool, validation_error_or_None).
        If parsing fails, tries a minimal repair by trimming trailing text and balancing braces/brackets.
        """
        import json
        try:
            data = json.loads(response_text)
            # Validate if jsonschema available
            valid = True
            err = None
            try:
                from core.llm.schemas import get_schema
                schema = get_schema(schema_id)
                if schema:
                    try:
                        import jsonschema  # optional
                        jsonschema.validate(instance=data, schema=schema)
                        valid = True
                    except ImportError:
                        valid = True  # cannot validate without package
                    except Exception as ve:
                        valid = False
                        err = ve
            except Exception:
                pass
            return data, valid, err
        except Exception:
            # Try minimal repair
            repaired = self._repair_json_string(response_text)
            if repaired:
                try:
                    data = json.loads(repaired)
                    valid = True
                    err = None
                    try:
                        from core.llm.schemas import get_schema
                        schema = get_schema(schema_id)
                        if schema:
                            try:
                                import jsonschema
                                jsonschema.validate(instance=data, schema=schema)
                            except ImportError:
                                pass
                            except Exception as ve:
                                valid = False
                                err = ve
                    except Exception:
                        pass
                    return data, valid, err
                except Exception:
                    return None, False, None
            return None, False, None

    def _repair_json_string(self, s: str) -> str | None:
        """Attempt a simple repair for truncated JSON by trimming trailing text
        and balancing braces/brackets. Returns repaired string or None.
        """
        s = s.strip()
        # Find first JSON start
        start_obj = s.find('{')
        start_arr = s.find('[')
        if start_obj == -1 and start_arr == -1:
            return None
        start = min([i for i in [start_obj, start_arr] if i != -1])
        s = s[start:]
        # Trim after last closing brace/bracket if present
        last_close_obj = s.rfind('}')
        last_close_arr = s.rfind(']')
        last_close = max(last_close_obj, last_close_arr)
        if last_close != -1:
            candidate = s[:last_close + 1]
        else:
            candidate = s
        # Balance braces/brackets
        open_curly = candidate.count('{')
        close_curly = candidate.count('}')
        open_square = candidate.count('[')
        close_square = candidate.count(']')
        # Append needed closers
        candidate += '}' * max(0, open_curly - close_curly)
        candidate += ']' * max(0, open_square - close_square)
        return candidate

    def _update_active_model_settings(self, provider_name: str, model_name: str) -> None:
        self._current_provider = provider_name
        self._current_model = model_name
        try:
            prefs = ModelPreferenceStore(self.settings)
            self._current_model_settings = prefs.get_settings(provider_name, model_name)
        except Exception:
            self._current_model_settings = ModelSettings()
        self._current_model_supports_structured = self._get_structured_support(provider_name, model_name)

    def _get_provider_model_from_settings(self) -> tuple[str, str]:
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "LM Studio":
            provider_name = "LM Studio (API)"
        if provider_name == "Ollama":
            model_name = self.settings.value("ollama_model", "llama3")
        else:
            model_name = self.settings.value("lm_studio_model", "llama3")
        return provider_name, model_name

    def _get_structured_support(self, provider_name: str, model_name: str) -> bool | None:
        key = (provider_name, model_name)
        if key in self._structured_support_cache:
            return self._structured_support_cache[key]

        support: bool | None = None
        try:
            from core.model_manager import ModelManager, build_default_sources

            mgr = ModelManager(build_default_sources(self.settings))
            infos = mgr.list_models(refresh=False)
            for info in infos:
                self._structured_support_cache[(info.provider, info.name)] = info.supports_structured_output
            support = self._structured_support_cache.get(key)
        except Exception as exc:
            print(f"DEBUG: structured support lookup failed: {exc}")

        if support is None:
            try:
                provider = self.window.get_llm_provider()
                support = bool(getattr(provider, "supports_structured_output", False))
            except Exception:
                support = False

        self._structured_support_cache[key] = support
        return support

    def _should_hide_structured_json(self) -> bool:
        structured_enabled = bool(self.settings.value("structured_enabled", False, type=bool))
        if not structured_enabled:
            return False

        if not self._current_provider or not self._current_model:
            provider_name, model_name = self._get_provider_model_from_settings()
            self._update_active_model_settings(provider_name, model_name)

        supports_structured = self._current_model_supports_structured
        if supports_structured is False:
            return False

        hide_pref = True
        if self._current_model_settings:
            hide_pref = bool(getattr(self._current_model_settings, "hide_structured_output_json", True))
        return hide_pref

    def _maybe_hide_structured_json(self, display_text: str, raw_text: str) -> tuple[str, str]:
        if not self._should_hide_structured_json():
            return display_text, raw_text

        candidate = raw_text or display_text
        parsed = None
        if isinstance(candidate, str):
            try:
                parsed = json.loads(candidate)
            except Exception:
                repaired = self._repair_json_string(candidate)
                if repaired:
                    try:
                        parsed = json.loads(repaired)
                    except Exception:
                        parsed = None
        if parsed is None:
            return display_text, raw_text

        preview = self._render_json_preview(parsed)
        pretty_block = self._format_json_block(parsed)
        note = "_JSON hidden. Use Show JSON to view raw structured output._"
        parts = [preview, pretty_block, note]
        return "\n\n".join([p for p in parts if p]), raw_text or display_text

    def _render_json_preview(self, payload, depth: int = 0) -> str:
        prefix = "  " * depth
        if isinstance(payload, dict):
            if not payload:
                return f"{prefix}- (empty object)"
            lines = []
            for key, value in payload.items():
                if isinstance(value, (dict, list)):
                    nested = self._render_json_preview(value, depth + 1)
                    nested_block = "\n".join(f"{'  ' * (depth + 1)}{line}" for line in nested.splitlines())
                    lines.append(f"{prefix}- **{key}**:\n{nested_block}")
                else:
                    lines.append(f"{prefix}- **{key}**: {self._stringify_json_value(value)}")
            return "\n".join(lines)
        if isinstance(payload, list):
            if not payload:
                return f"{prefix}- (empty array)"
            lines = []
            for idx, value in enumerate(payload):
                if isinstance(value, (dict, list)):
                    nested = self._render_json_preview(value, depth + 1)
                    nested_block = "\n".join(f"{'  ' * (depth + 1)}{line}" for line in nested.splitlines())
                    lines.append(f"{prefix}- [{idx}]:\n{nested_block}")
                else:
                    lines.append(f"{prefix}- [{idx}]: {self._stringify_json_value(value)}")
            return "\n".join(lines)
        return f"{prefix}{self._stringify_json_value(payload)}"

    @staticmethod
    def _stringify_json_value(value) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _format_json_block(payload) -> str:
        try:
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            return f"```json\n{rendered}\n```"
        except Exception:
            return ""

    # ===== Manual context management =====

    def add_context_file(self, path: str):
        if not path:
            return
        if path in self.manual_context_files:
            self._refresh_context_file_view()
            return
        self.manual_context_files.append(path)
        self._refresh_context_file_view()
        # Switch UI to Custom when manual context changes
        try:
            self.window.chat._set_context_combo_custom()
        except Exception:
            pass

    def remove_context_file(self, path: str):
        if not path:
            return
        try:
            self.manual_context_files.remove(path)
        except ValueError:
            return
        self._refresh_context_file_view()
        # Switch UI to Custom when manual context changes
        try:
            self.window.chat._set_context_combo_custom()
        except Exception:
            pass

    def _refresh_context_file_view(self):
        """Refresh the Context Files list to show current planned sources.
        Aggregates manual context, active file, open tabs per context level,
        and mentions in input among open tabs for 'visible' level.
        """
        try:
            self.refresh_context_sources_view()
        except Exception:
            pass

    def on_chat_input_changed(self):
        """Update context files when the user is typing in chat."""
        try:
            # Show spinner and debounce the refresh
            self.window.chat.show_context_spinner()
        except Exception:
            pass
        try:
            if self._input_debounce_timer.isActive():
                self._input_debounce_timer.stop()
            self._input_debounce_timer.start()
        except Exception:
            pass

    def refresh_context_sources_view(self):
        """Compute and update the context files UI with planned sources."""
        root = self.window.project_manager.get_root_path()
        files: list[str] = []
        seen: set[str] = set()

        def add_path(p: str):
            if not p:
                return
            if p not in seen:
                files.append(p)
                seen.add(p)

        # Manual pinned files first
        for p in list(self.manual_context_files):
            add_path(p)

        # If context is none, only manual files are shown
        if self.context_level == "none":
            self.window.chat.update_context_files(files, root)
            return

        # Active file
        try:
            active_path, _ = self.window.editor.get_current_file()
        except Exception:
            active_path = None
        if active_path:
            add_path(active_path)

        # All open tabs for 'visible_tabs', 'all_open' and 'full'
        if self.context_level in ("visible_tabs", "all_open", "full"):
            try:
                for p in list(self.window.editor.open_files.keys()):
                    add_path(p)
            except Exception:
                pass
        elif self.context_level == "visible":
            # Include mentioned files among open tabs based on current input text
            try:
                text = self.window.chat.input_field.toPlainText()
            except Exception:
                text = ""
            text_lower = text.lower()
            try:
                for p in list(self.window.editor.open_files.keys()):
                    base = os.path.basename(p).lower()
                    name_no_ext = os.path.splitext(base)[0]
                    if base in text_lower or (len(name_no_ext) > 3 and name_no_ext in text_lower):
                        add_path(p)
            except Exception:
                pass

        # RAG-derived sources based on current input (for all non-none levels)
        if self.context_level != "none" and getattr(self.window, 'rag_engine', None):
            try:
                # Use a small number of results to keep UI responsive
                text = self.window.chat.input_field.toPlainText()
                context = self.window.rag_engine.query(text or "", n_results=3, include_metadata=True)
                for chunk in context or []:
                    meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                    source = meta.get("source")
                    if source:
                        # Skip excluded files
                        try:
                            if self.window.rag_engine._should_exclude_file(source):
                                continue
                        except Exception:
                            pass
                        add_path(source)
            except Exception as e:
                # Non-fatal; ignore RAG errors for live view
                print(f"DEBUG: Live RAG context sources update failed: {e}")

        # Update the UI list with aggregated planned sources
        self.window.chat.update_context_files(files, root)

    def _inject_manual_context(
        self,
        system_prompt: str,
        token_usage: int,
        token_breakdown: dict,
        included_files: set,
    ) -> tuple[str, int, dict]:
        if not self.manual_context_files:
            return system_prompt, token_usage, token_breakdown

        root = self.window.project_manager.get_root_path()
        rag = self.window.rag_engine

        for path in list(self.manual_context_files):
            try:
                if root and os.path.commonpath([path, root]) != root:
                    continue
            except Exception:
                continue

            if path in included_files:
                continue

            if rag and rag._should_exclude_file(path):
                continue

            content = self.window.project_manager.read_file(path)
            if not content:
                continue

            tokens = estimate_tokens(content)
            system_prompt += f"\nPinned Context ({path}):\n{content}\n"
            token_usage += tokens
            token_breakdown[f"Manual: {path}"] = tokens
            included_files.add(path)

        return system_prompt, token_usage, token_breakdown

    def _render_structured_payload(self, payload: dict, schema_id: str) -> str:
        """Render a structured payload to a human-readable text, and enqueue diffs.
        For diff-like schemas, create pending edit links using existing flow.
        """
        try:
            if schema_id == 'basic_answer':
                ans = payload.get('answer', '')
                notes = payload.get('notes')
                out = f"**Answer**\n\n{ans}" if ans else ""
                if notes:
                    out += f"\n\n**Notes**\n\n{notes}"
                return out or str(payload)
            if schema_id == 'chat_split':
                analysis = payload.get('analysis')
                answer = payload.get('answer')
                actions = payload.get('actions')
                parts = []
                if analysis:
                    parts.append(f"**Analysis**\n\n{analysis}")
                if answer:
                    parts.append(f"**Answer**\n\n{answer}")
                if actions:
                    parts.append("**Actions**\n\n" + "\n".join(actions))
                return "\n\n".join(parts) or str(payload)
            if schema_id == 'tool_result':
                req = payload.get('request')
                res = payload.get('result')
                cits = payload.get('citations') or []
                import json
                res_str = json.dumps(res, ensure_ascii=False, indent=2) if not isinstance(res, str) else res
                out = []
                if req:
                    out.append(f"**Request**\n\n{req}")
                out.append(f"**Result**\n\n{res_str}")
                if cits:
                    out.append("**Citations**\n\n" + "\n".join(cits))
                return "\n\n".join(out)
            if schema_id == 'diff_patch':
                print(f"DEBUG: Processing diff_patch schema, batch_mode={self._use_batch_mode()}, diff_parser={self._diff_parser is not None}")
                
                # Use new batch system if enabled
                if self._use_batch_mode() and self._diff_parser:
                    try:
                        print("DEBUG: Attempting to parse structured diff_patch with batch system")
                        batch = self._diff_parser.parse_structured_json(payload, schema_id)
                        print(f"DEBUG: Parsed structured JSON into batch with {len(batch.edits)} edits")
                        
                        if batch.edits:
                            batch_id = batch.batch_id
                            self.pending_edit_batches[batch_id] = batch
                            
                            files_affected = batch.total_files_affected()
                            total_edits = len(batch.edits)
                            
                            summary = payload.get('summary', '')
                            warnings = payload.get('warnings', [])
                            
                            out = []
                            if summary:
                                out.append(f"**Summary**\n\n{summary}")
                            
                            out.append(f'\n<br><b><a href="batch:{batch_id}">📝 Review {total_edits} Changes to {files_affected} Files</a></b><br>')
                            
                            if warnings:
                                out.append("**Warnings**\n\n" + "\n".join(warnings))
                            
                            print(f"DEBUG: Created batch link for {total_edits} edits")
                            return "\n\n".join(out)
                    except Exception as e:
                        print(f"ERROR: Failed to parse structured diff_patch: {e}")
                        import traceback
                        traceback.print_exc()
                        # Fall through to legacy handling
                
                print("DEBUG: Using legacy diff_patch handling")
                # Legacy handling
                summary = payload.get('summary')
                edits = payload.get('edits') or []
                warnings = payload.get('warnings') or []
                out = []
                if summary:
                    out.append(f"**Summary**\n\n{summary}")
                # Create pending edits and links
                active_path = None
                try:
                    active_path = self.window.editor.get_current_file()[0]
                except Exception:
                    pass
                seen_ids = set()
                for edit in edits:
                    path = edit.get('path') or active_path or 'unknown.txt'
                    after = edit.get('after') or ''
                    # Non-text extension fallback
                    ext = os.path.splitext(path)[1].lower()
                    non_text_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                                           '.mp4', '.avi', '.mov', '.mp3', '.wav',
                                           '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}
                    if ext in non_text_extensions:
                        path = os.path.splitext(path)[0] + '.txt'
                    # Normalize path similar to UPDATE handler
                    path = self._normalize_edit_path(path, active_path)
                    # Create id
                    eid = str(uuid.uuid4())
                    while eid in seen_ids:
                        eid = str(uuid.uuid4())
                    seen_ids.add(eid)
                    self.pending_edits[eid] = (path, after)
                    out.append(f"<b><a href=\"edit:{eid}\">Review Changes for {path}</a></b>")
                if warnings:
                    out.append("**Warnings**\n\n" + "\n".join(warnings))
                return "\n\n".join(out)
        except Exception as e:
            print(f"DEBUG: Failed to render structured payload: {e}")
        # Fallback to pretty JSON
        try:
            import json
            return json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception:
            return str(payload)
    
    def _continue_response(self):
        """Automatically continue the previous response."""
        provider = self.window.get_llm_provider()
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "LM Studio":
            provider_name = "LM Studio (Native SDK)"
            self.settings.setValue("llm_provider", provider_name)
        model = self.settings.value("ollama_model", "llama3") if provider_name == "Ollama" else self.settings.value("lm_studio_model", "llama3")
        system_prompt = self.window.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant.")
        )

        # Ensure model is loaded with user-facing messages
        try:
            loaded_state = provider.is_model_loaded(model) if hasattr(provider, "is_model_loaded") else None
            if loaded_state is False:
                # Show spinner in chat UI
                try:
                    self.window.chat.show_model_loading(model)
                except Exception:
                    pass
                self.window.chat.append_message("System", f"Model '{model}' is not loaded. Loading now…")
                from core.model_manager import ModelManager, build_default_sources
                mgr = ModelManager(build_default_sources(self.settings))
                ok, err = mgr.load_model(provider_name, model)
                if ok:
                    import time
                    time.sleep(1)
                    self.window.chat.append_message("System", f"Model '{model}' loaded.")
                    try:
                        self.window.update_model_controls(refresh=True)
                    except Exception:
                        pass
                else:
                    self.window.chat.append_message("System", f"Failed to load model '{model}': {err}")
                try:
                    self.window.chat.hide_model_loading()
                except Exception:
                    pass
            elif loaded_state is True:
                self.window.chat.append_message("System", f"Model '{model}' is already loaded.")
        except Exception:
            pass

        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            [],
            system_prompt,
            images=None,
            enabled_tools=self.window.project_manager.get_enabled_tools(),
            mode=self.chat_mode,
        )
        self.worker.response_thinking_start.connect(self.on_chat_thinking_start)
        self.worker.response_thinking_chunk.connect(self.on_chat_thinking_chunk)
        self.worker.response_thinking_done.connect(self.on_chat_thinking_done)
        self.worker.response_chunk.connect(self.on_chat_chunk)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()
        self.window._update_token_dashboard()

    def handle_continue(self):
        """Manually continue the conversation if the model stopped early."""
        if not self.chat_history:
            self.window.statusBar().showMessage("No conversation to continue", 2000)
            return

        self.window.chat.show_thinking()
        self._continue_response()
    
    def handle_new_chat(self):
        """Start a new chat, saving the current one to history first."""
        if self.chat_history:
            self.save_current_chat_session()
        
        # Clear chat history and UI
        self.chat_history = []
        self.window.chat.clear_chat()
        self.pending_edits = {}
        
        # Clear selection info
        self._last_selection_info = None
        
        self.window.statusBar().showMessage("Started new chat (previous chat saved to history)", 3000)

    def _maybe_handle_structured_debug(self, message: str) -> bool:
        """Intercept debug commands to inject structured payloads without provider.
        Returns True if handled.
        Commands:
          /structured_demo diff  -> emits a sample diff_patch payload
          /structured_json <json> -> treats remainder as JSON payload
        """
        try:
            if message.strip().startswith("/structured_demo"):
                parts = message.strip().split()
                kind = parts[1] if len(parts) > 1 else "diff"
                if kind == "diff":
                    payload = {
                        "summary": "Update README and fix typos",
                        "edits": [
                            {"path": "README.md", "after": "# Project\n\nUpdated content..."},
                            {"path": "docs/notes.md", "after": "Notes updated."}
                        ],
                        "warnings": ["Review changes before applying."],
                    }
                    import json
                    self.on_chat_response(json.dumps(payload))
                    return True
                return False
            if message.strip().startswith("/structured_json "):
                raw = message.strip()[len("/structured_json "):]
                self.on_chat_response(raw)
                return True
        except Exception:
            pass
        return False

    def handle_regenerate(self):
        """Regenerate the last assistant response."""
        if not self.chat_history:
            return
        
        # Find the last assistant message
        last_assistant_idx = None
        last_user_idx = None
        
        for i in range(len(self.chat_history) - 1, -1, -1):
            if self.chat_history[i]['role'] == 'assistant' and last_assistant_idx is None:
                last_assistant_idx = i
            elif self.chat_history[i]['role'] == 'user' and last_assistant_idx is not None and last_user_idx is None:
                last_user_idx = i
                break
        
        if last_assistant_idx is None:
            QMessageBox.information(self.window, "Nothing to Regenerate", "No AI response found to regenerate.")
            return
        
        # Remove the last assistant message from history and rebuild the chat view
        del self.chat_history[last_assistant_idx]
        self.window.chat.clear_chat()
        for msg in self.chat_history:
            role = msg.get("role")
            sender = {
                "user": "User",
                "assistant": "Assistant",
                "tool": "Tool",
            }.get(role, "System")
            self.window.chat.append_message(sender, msg.get("content", ""))
        
        # Show thinking indicator
        self.window.chat.show_thinking()
        
        # Resend the request
        provider = self.window.get_llm_provider()
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            model = self.settings.value("ollama_model", "llama3")
        else:
            model = self.settings.value("lm_studio_model", "llama3")

        # Ensure model is loaded with user-facing messages
        try:
            loaded_state = provider.is_model_loaded(model) if hasattr(provider, "is_model_loaded") else None
            if loaded_state is False:
                # Show spinner in chat UI
                try:
                    self.window.chat.show_model_loading(model)
                except Exception:
                    pass
                self.window.chat.append_message("System", f"Model '{model}' is not loaded. Loading now…")
                from core.model_manager import ModelManager, build_default_sources
                # Map deprecated name if needed
                if provider_name == "LM Studio":
                    provider_name = "LM Studio (Native SDK)"
                    self.settings.setValue("llm_provider", provider_name)
                mgr = ModelManager(build_default_sources(self.settings))
                ok, err = mgr.load_model(provider_name, model)
                if ok:
                    import time
                    time.sleep(1)
                    self.window.chat.append_message("System", f"Model '{model}' loaded.")
                    try:
                        self.window.update_model_controls(refresh=True)
                    except Exception:
                        pass
                else:
                    self.window.chat.append_message("System", f"Failed to load model '{model}': {err}")
                try:
                    self.window.chat.hide_model_loading()
                except Exception:
                    pass
            elif loaded_state is True:
                self.window.chat.append_message("System", f"Model '{model}' is already loaded.")
        except Exception:
            pass
        
        # Get RAG context if available
        context = []
        if self.window.rag_engine and last_user_idx is not None:
            query = self.chat_history[last_user_idx]['content']
            context = self.window.rag_engine.query(query, n_results=3)
        
        # Build system prompt
        system_prompt = self.window.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant.")
        )
        
        # Include project structure
        if self.window.project_manager.root_path:
            structure = self.window.project_manager.get_project_structure()
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
        
        enabled_tools = self.window.project_manager.get_enabled_tools()
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=None,
            enabled_tools=enabled_tools,
            mode=self.chat_mode,
        )
        self.worker.response_thinking_start.connect(self.on_chat_thinking_start)
        self.worker.response_thinking_chunk.connect(self.on_chat_thinking_chunk)
        self.worker.response_thinking_done.connect(self.on_chat_thinking_done)
        self.worker.response_chunk.connect(self.on_chat_chunk)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

    def handle_message_deleted(self, msg_index):
        """Handle message deletion from chat history.
        
        Args:
            msg_index: Index of message to delete
        """
        if 0 <= msg_index < len(self.chat_history):
            self.chat_history.pop(msg_index)
            
    def handle_message_edited(self, msg_index, new_content):
        """Handle message edit in chat history.
        
        Args:
            msg_index: Index of message to edit
            new_content: New message content
        """
        if 0 <= msg_index < len(self.chat_history):
            self.chat_history[msg_index]["content"] = new_content

    def save_current_chat_session(self):
        """Save current chat session to history."""
        if not self.chat_history:
            print("DEBUG: No chat history to save")
            return
            
        project_path = self.window.project_manager.root_path
        if not project_path:
            print("DEBUG: No project path, cannot save chat history")
            return
            
        key = hashlib.md5(project_path.encode()).hexdigest()
        
        # Save chat history
        import json
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        session_data = {
            "timestamp": timestamp,
            "messages": self.chat_history
        }
        
        print(f"DEBUG: Saving chat session with {len(self.chat_history)} messages to key: chat_history/{key}")
        
        # Get existing sessions
        sessions_key = f"chat_history/{key}"
        existing = self.settings.value(sessions_key, [])
        if not isinstance(existing, list):
            existing = []
        
        existing.append(session_data)
        
        # Keep last 50 sessions
        existing = existing[-50:]
        
        self.settings.setValue(sessions_key, existing)
        self.settings.sync()
        
        print(f"DEBUG: Chat session saved. Total sessions for this project: {len(existing)}")

    def open_chat_history(self):
        """Open chat history dialog."""
        if not self.window.project_manager.root_path:
            QMessageBox.information(self.window, "No Project", "Open a project first to view chat history.")
            return
        
        project_path = self.window.project_manager.root_path
        dialog = ChatHistoryDialog(self.settings, self.window, project_path)
        dialog.message_copy_requested.connect(self.copy_message_to_current_chat)
        dialog.exec()
    
    def copy_message_to_current_chat(self, message_content):
        """Copy a message from history to current chat.
        
        Args:
            message_content: Message content to copy
        """
        self.window.chat.input_field.setPlainText(message_content)
        self.window.statusBar().showMessage("Message copied to input", 2000)

    def on_context_level_changed(self, level):
        """Handle context level change.
        
        Args:
            level: New context level (none/visible/all_open/full)
        """
        self.context_level = level
        print(f"DEBUG: Context level changed to: {level}")
        try:
            self.window.chat.show_context_spinner()
        except Exception:
            pass
        # Refresh planned context list on change
        try:
            self.refresh_context_sources_view()
        except Exception:
            pass

    def on_tabs_changed(self, *args):
        """Handle editor tab open/close or switch events: show spinner and refresh."""
        try:
            self.window.chat.show_context_spinner()
        except Exception:
            pass
        try:
            self.refresh_context_sources_view()
        except Exception:
            pass
    
    def on_mode_changed(self, mode):
        """Handle chat mode change.
        
        Args:
            mode: New mode (ask or edit)
        """
        self.chat_mode = mode
        print(f"DEBUG: Chat mode changed to: {mode}")

    def on_tools_enabled_changed(self, enabled: bool):
        """Handle tools enabled/disabled change.
        
        Args:
            enabled: Whether tools are enabled
        """
        self.tools_enabled = enabled
        print(f"DEBUG: Tools enabled changed to: {enabled}")

    def on_tool_finished(self, result_text, extra_data):
        """Handle tool execution completion.
        
        Args:
            result_text: Tool result text
            extra_data: Additional data from tool (e.g., image results)
        """
        self.window.chat.remove_thinking()
        
        print(f"DEBUG: on_tool_finished called: result_text={result_text[:100]}, extra_data type={type(extra_data)}, extra_data={extra_data}")
        
        # Check if this is an image search result with image data
        if extra_data and isinstance(extra_data, list) and len(extra_data) > 0:
            print(f"DEBUG: extra_data is list with {len(extra_data)} items")
            print(f"DEBUG: first item keys: {extra_data[0].keys() if isinstance(extra_data[0], dict) else 'not a dict'}")
            # Check if it looks like image results (has 'image' or 'thumbnail' keys)
            if isinstance(extra_data[0], dict) and ('image' in extra_data[0] or 'thumbnail' in extra_data[0]):
                print(f"DEBUG: Creating ImageSelectionDialog with {len(extra_data)} images")
                # Show image selection dialog
                from gui.dialogs.image_dialog import ImageSelectionDialog
                if self.window.project_manager.root_path:
                    dialog = ImageSelectionDialog(extra_data, self.window.project_manager.root_path, self.window)
                    print(f"DEBUG: Dialog created, executing...")
                    if dialog.exec():
                        saved_paths = dialog.saved_paths
                        if saved_paths:
                            result_text = f"Successfully found and saved {len(saved_paths)} images from the search. Images were presented to the user and selected. Paths: {', '.join(saved_paths)}"
                        else:
                            result_text = "Search found images but user chose not to save any."
                    else:
                        result_text = "User cancelled the image selection dialog."
                else:
                    result_text = "Error: No project open to save images."
        
        # Continue chat with result
        self.continue_chat_with_tool_result(result_text)
        
    def continue_chat_with_tool_result(self, result):
        """Continue chat after tool execution with result.
        
        Args:
            result: Tool execution result
        """
        # Add tool result to chat history
        self.chat_history.append({"role": "tool", "content": result})
        
        # Show result in chat
        self.window.chat.append_message("Tool Result", f"<pre>{result}</pre>")
        
        # Continue conversation with tool result as context
        self.window.chat.show_thinking()
        self._continue_response()

    def handle_chat_link(self, url):
        """Handle link clicks in chat (edit proposals).
        
        Args:
            url: Clicked URL (edit:ID or batch:ID format)
        """
        # Handle batch edit links (new system)
        if url.startswith("batch:"):
            self._handle_batch_link(url)
            return
        
        # Handle single edit links (legacy system)
        if url.startswith("edit:"):
            edit_id = url[5:]
            if edit_id in self.pending_edits:
                path, new_content = self.pending_edits[edit_id]
                
                # Show diff dialog
                try:
                    old_content = self.window.project_manager.read_file(path) or ""
                except:
                    old_content = ""
                    
                dialog = DiffDialog(path, old_content, new_content, parent=self.window)
                if dialog.exec():
                    # Apply the edit - update editor only, don't save to disk
                    try:
                        # Resolve absolute path for lookup in open_files
                        if not os.path.isabs(path) and self.window.project_manager.root_path:
                            abs_path = os.path.join(self.window.project_manager.root_path, path)
                        else:
                            abs_path = path
                        
                        # Check both relative and absolute path formats
                        widget = None
                        if path in self.window.editor.open_files:
                            widget = self.window.editor.open_files[path]
                        elif abs_path in self.window.editor.open_files:
                            widget = self.window.editor.open_files[abs_path]
                        
                        if widget and isinstance(widget, DocumentWidget):
                            widget.replace_content_undoable(new_content)
                            self.window.statusBar().showMessage(f"Applied changes to {path} - Press Ctrl+S to save", 3000)
                        else:
                            # File not open - save directly to disk
                            saved = self.window.project_manager.save_file(path, new_content)
                            if not saved:
                                raise IOError("Save returned False")
                            self.window.statusBar().showMessage(f"Applied changes to {path}", 3000)
                    except Exception as e:
                        QMessageBox.critical(self.window, "Error", f"Failed to apply changes: {e}")
                        
                # Remove from pending
                del self.pending_edits[edit_id]
    
    def _handle_batch_link(self, url: str):
        """Handle batch edit link click.
        
        Args:
            url: Batch URL (batch:ID format)
        """
        batch_id = url[6:]  # Remove "batch:" prefix
        
        if batch_id not in self.pending_edit_batches:
            QMessageBox.warning(self.window, "Batch Not Found", 
                              f"Edit batch {batch_id} not found. It may have been applied or cleared.")
            return
        
        batch = self.pending_edit_batches[batch_id]
        
        # Show batch diff dialog
        dialog = BatchDiffDialog(batch, parent=self.window)
        if dialog.exec():
            # Apply enabled edits
            enabled_edits = dialog.get_enabled_edits()
            
            if not enabled_edits:
                QMessageBox.information(self.window, "No Changes", "No edits were selected to apply.")
                return
            
            # Apply each enabled edit
            applied_count = 0
            failed_files = []
            
            for edit in enabled_edits:
                try:
                    self._apply_single_edit(edit)
                    applied_count += 1
                except Exception as e:
                    failed_files.append(f"{edit.file_path}: {e}")
                    print(f"ERROR: Failed to apply edit to {edit.file_path}: {e}")
            
            # Show results
            if failed_files:
                error_msg = f"Applied {applied_count} edits successfully.\n\nFailed to apply:\n"
                error_msg += "\n".join(failed_files[:5])  # Show first 5 errors
                if len(failed_files) > 5:
                    error_msg += f"\n... and {len(failed_files) - 5} more"
                QMessageBox.warning(self.window, "Partial Success", error_msg)
            else:
                self.window.statusBar().showMessage(
                    f"Applied {applied_count} changes to {len(set(e.file_path for e in enabled_edits))} files - Press Ctrl+S to save",
                    5000
                )
            
            # Remove batch from pending
            del self.pending_edit_batches[batch_id]
    
    def _apply_single_edit(self, edit: FileEdit):
        """Apply a single FileEdit to the filesystem or editor.
        
        Args:
            edit: FileEdit to apply
            
        Raises:
            Exception if application fails
        """
        path = edit.file_path
        new_content = edit.new_content
        
        # Resolve absolute path for lookup in open_files
        if not os.path.isabs(path) and self.window.project_manager.root_path:
            abs_path = os.path.join(self.window.project_manager.root_path, path)
        else:
            abs_path = path
        
        # Check if file is open in editor
        widget = None
        if path in self.window.editor.open_files:
            widget = self.window.editor.open_files[path]
        elif abs_path in self.window.editor.open_files:
            widget = self.window.editor.open_files[abs_path]
        
        if widget and isinstance(widget, DocumentWidget):
            # File is open - update editor
            widget.replace_content_undoable(new_content)
        else:
            # File not open - save directly to disk
            saved = self.window.project_manager.save_file(path, new_content)
            if not saved:
                raise IOError(f"Failed to save {path}")

    def _normalize_edit_path(self, raw_path: str, active_path: str | None) -> str:
        """Normalize and resolve file paths from AI output.
        
        - Strip quotes/backticks/angle brackets
        - Collapse redundant slashes
        - Resolve basenames in project
        - Fallback to active file when empty
        
        Args:
            raw_path: Raw path from AI
            active_path: Currently active file path
            
        Returns:
            Normalized path string
        """
        import difflib
        
        path = raw_path.strip()
        
        # Remove enclosing quotes/backticks/angle brackets
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        if (path.startswith('<') and path.endswith('>')) or (path.startswith('`') and path.endswith('`')):
            path = path[1:-1]
            
        # Normalize slashes
        path = path.replace('\\', '/')
        if path.startswith('./'):
            path = path[2:]
            
        # Drop line markers or closers
        if '\n' in path:
            path = path.splitlines()[0].strip()
        path = re.split(r"\s+L\d+:", path)[0].strip()
        
        for marker in (":::END:::", ":::END", ":::"):
            if marker in path:
                path = path.split(marker)[0].strip()
        
        # Collapse duplicate slashes
        while '//' in path:
            path = path.replace('//', '/')
        path = path.strip()
        
        # Fallback to active file
        if not path and active_path:
            return active_path
            
        # Convert absolute to relative
        if self.window.project_manager.root_path and os.path.isabs(path):
            try:
                rel = os.path.relpath(path, self.window.project_manager.root_path)
                if not rel.startswith('..'):
                    path = rel
            except Exception:
                pass
        
        # Resolve basename in project
        if '/' not in path and self.window.project_manager.root_path:
            candidates = []
            for root, dirs, files in os.walk(self.window.project_manager.root_path):
                for f in files:
                    if f == path:
                        candidates.append(os.path.relpath(os.path.join(root, f), self.window.project_manager.root_path))
            
            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1 and active_path:
                active_dir = os.path.dirname(active_path)
                for c in candidates:
                    if os.path.dirname(c) == active_dir:
                        return c
                candidates.sort(key=lambda p: len(os.path.dirname(p)))
                return candidates[0]
        
        # Fuzzy matching
        if self.window.project_manager.root_path:
            target = path.split('/')[-1]
            index = []
            for root, dirs, files in os.walk(self.window.project_manager.root_path):
                for f in files:
                    index.append(os.path.relpath(os.path.join(root, f), self.window.project_manager.root_path))
            basenames = [os.path.basename(p) for p in index]
            import difflib
            matches = difflib.get_close_matches(target, basenames, n=1, cutoff=0.8)
            if matches:
                m = matches[0]
                for p in index:
                    if os.path.basename(p) == m:
                        return p
        
        return path

    def _parse_patch_blocks(self, response):
        """Parse all PATCH block formats from response.
        
        Returns list of (path, body) tuples.
        """
        # Fenced PATCH blocks
        fenced_patch_pattern = r"```[a-z]*\s*\n\s*:::PATCH\s+([^\n:]+)\s*(?:::\s*)?\n((?:(?!:::END:::)[\s\S])*?)\s*:::END:::\s*\n```"
        fenced_matches = re.findall(fenced_patch_pattern, response, re.DOTALL | re.IGNORECASE)
        
        # Remove fenced blocks from response to avoid double-parsing
        response_no_fenced = re.sub(fenced_patch_pattern, '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Bare PATCH blocks (allow optional closing ::: after path)
        patch_pattern = r":::PATCH\s+([^\n]+?)\s*(?:::\s*)?\n(.*?)(?:\s*(?::::END:::|:::END|:::)|\s*$)"
        bare_matches = re.findall(patch_pattern, response_no_fenced, re.DOTALL)
        
        all_matches = list(fenced_matches) + list(bare_matches)
        
        # Dedupe
        unique = []
        seen = set()
        for p, b in all_matches:
            key = (p.strip(), b.strip())
            if key not in seen:
                seen.add(key)
                unique.append((p, b))
        
        return unique

    def _process_patch_blocks(self, patch_matches, display_response, active_path, next_edit_id, non_text_extensions):
        """Process PATCH blocks and append review links."""
        def _clean_patch_body(body: str) -> str:
            cleaned = body.strip()
            link_pattern = r'<br><b><a href="edit:[^"]+">.*?</a></b><br>'
            if re.search(link_pattern, cleaned):
                cleaned = re.sub(link_pattern, '', cleaned).strip()
            if ':::END:::' in cleaned:
                cleaned = cleaned.split(':::END:::')[0]
            return cleaned

        links_html = []
        seen = set()

        for m_path_raw, patch_body in patch_matches:
            if not m_path_raw:
                continue

            raw_path_clean = m_path_raw.strip()
            m_path = self._normalize_edit_path(raw_path_clean, active_path)
            patch_body = _clean_patch_body(patch_body)

            success, m_new_content = self._apply_patch_block(m_path, patch_body)
            if not success or m_new_content is None:
                continue

            file_ext = os.path.splitext(m_path)[1].lower()
            if file_ext in non_text_extensions:
                m_path = os.path.splitext(m_path)[0] + '.txt'

            dedupe_key = (m_path, m_new_content)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            m_id = next_edit_id()
            self.pending_edits[m_id] = (m_path, m_new_content)
            links_html.append(f'<br><b><a href="edit:{m_id}">Review Changes for {m_path}</a></b><br>')

            # Strip original patch block from the displayed response to avoid clutter
            block_pattern = re.compile(rf":::PATCH\s*{re.escape(raw_path_clean)}.*?:::END:::", re.DOTALL)
            display_response = block_pattern.sub('', display_response, count=1)

        if links_html:
            display_response += "\n" + "".join(links_html)

        return display_response

    def _process_diff_blocks(self, processing_response, display_response, active_path, next_edit_id, non_text_extensions):
        """Process unified diff blocks."""
        diff_pattern = r"```diff\s*\n(.*?)```"
        diff_blocks = re.findall(diff_pattern, processing_response, re.DOTALL)
        
        if not diff_blocks:
            return display_response

        def replace_diff_block(match):
            diff_text = match.group(1)
            target_path = self._extract_diff_target_path(diff_text)
            
            if not target_path:
                return match.group(0)
                
            norm_path = self._normalize_edit_path(target_path.strip(), active_path)
            success, m_new = self._apply_unified_diff(norm_path, diff_text)
            
            if not success or m_new is None:
                return match.group(0)

            file_ext = os.path.splitext(norm_path)[1].lower()
            if file_ext in non_text_extensions:
                norm_path = os.path.splitext(norm_path)[0] + '.txt'

            m_id = next_edit_id()
            self.pending_edits[m_id] = (norm_path, m_new)
            return f'<br><b><a href="edit:{m_id}">Review Changes for {norm_path}</a></b><br>'

        return re.sub(diff_pattern, replace_diff_block, display_response, flags=re.DOTALL)

    def _process_code_blocks(self, processing_response, display_response, active_path, next_edit_id, has_explicit_edits):
        """Process fallback code blocks as full-file updates."""
        code_block_pattern = r"```(?:markdown|md|text)?\s*\n(.*?)```"
        code_blocks = re.findall(code_block_pattern, processing_response, re.DOTALL)
        
        if not code_blocks or not active_path or has_explicit_edits:
            return display_response

        def replace_code_block(m):
            full_text = m.group(1)
            edit_id = next_edit_id()
            self.pending_edits[edit_id] = (active_path, full_text.strip())
            return f'<br><b><a href="edit:{edit_id}">Review Changes for {active_path}</a></b><br>'

        return re.sub(code_block_pattern, replace_code_block, display_response, flags=re.DOTALL)

    def _extract_diff_target_path(self, diff_text: str) -> str | None:
        """Extract target file path from unified diff headers."""
        for line in diff_text.splitlines():
            if line.startswith('+++ '):
                p = line[4:].strip()
                if p.startswith('b/') or p.startswith('a/'):
                    p = p[2:]
                return p
        for line in diff_text.splitlines():
            if line.startswith('--- '):
                p = line[4:].strip()
                if p.startswith('b/') or p.startswith('a/'):
                    p = p[2:]
                return p
        return None

    def _strip_unknown_edit_links(self, html: str) -> str:
        """Remove edit links that don't correspond to pending edits."""
        def check_link(match):
            edit_id = match.group(1)
            if edit_id in self.pending_edits:
                return match.group(0)
            return ""
        
        return re.sub(r'<br><b><a href="edit:([^"]+)">.*?</a></b><br>', check_link, html)

    def _clean_patch_body(self, patch_body: str) -> str:
        """Clean patch body by removing citations and footnote markers.
        
        Removes:
        - **Citations:** section and everything after it
        - Footnote references like [^1], [^2], etc.
        
        Args:
            patch_body: Raw patch content from LLM
            
        Returns:
            Cleaned patch body
        """
        # Remove Citations section (everything from **Citations:** onwards)
        citations_pattern = r'\*\*Citations:\*\*.*$'
        patch_body = re.sub(citations_pattern, '', patch_body, flags=re.DOTALL | re.MULTILINE)
        
        # Remove footnote markers like [^1], [^2], [^3], etc.
        footnote_pattern = r'\[\^\d+\]'
        patch_body = re.sub(footnote_pattern, '', patch_body)
        
        # Clean up any trailing whitespace left behind
        patch_body = patch_body.rstrip()
        
        return patch_body
    
    def _apply_patch_block(self, file_path: str, patch_body: str) -> tuple[bool, str | None]:
        """Apply PATCH block to file content.
        
        Supports:
        - Line replacements: L42: old => new
        - Range replacements: L10-L15: new content
        
        Returns (success, new_content)
        """
        # Clean up patch body: remove citations section and footnote markers
        patch_body = self._clean_patch_body(patch_body)
        
        try:
            current = self.window.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for patch {file_path}: {e}")
            return False, None

        if current is None:
            return False, None

        lines = current.split("\n")
        applied_any = False

        # Parse patch lines
        raw_lines = patch_body.splitlines()
        i = 0
        
        while i < len(raw_lines):
            raw = raw_lines[i]
            line = raw.strip()
            i += 1
            
            if not line:
                continue
            
            # Range replacement: L10-L15:
            m_range = re.match(r"L(\d+)\s*-\s*L(\d+):\s*(.*)", line)
            if m_range:
                start_no = int(m_range.group(1))
                end_no = int(m_range.group(2))
                trailing = m_range.group(3).strip()
                
                repl_lines = []
                if trailing:
                    repl_lines.append(trailing)
                
                # Capture subsequent lines
                while i < len(raw_lines):
                    peek = raw_lines[i]
                    if re.match(r"\s*L\d+:", peek):
                        break
                    repl_lines.append(peek)
                    i += 1
                
                # Apply replacement
                s_idx = max(1, start_no)
                e_idx = min(len(lines), end_no)
                
                if s_idx <= e_idx:
                    before = lines[:s_idx - 1]
                    after = lines[e_idx:]
                    lines = before + repl_lines + after
                    applied_any = True
                continue
            
            # Line replacement: L42: old => new
            m = re.match(r"L(\d+):\s*(.+?)\s*(?:=>|->)\s*(.+)", line)
            if m:
                line_no = int(m.group(1))
                old_text = m.group(2)
                new_text = m.group(3)
                
                if 1 <= line_no <= len(lines):
                    current_line = lines[line_no - 1]
                    if old_text in current_line:
                        lines[line_no - 1] = current_line.replace(old_text, new_text, 1)
                    else:
                        lines[line_no - 1] = new_text
                    applied_any = True
                continue
            
            # Simple replacement/insertion: L42: new text (can span multiple lines)
            m2 = re.match(r"L(\d+):\s*(.*)", line)
            if m2:
                line_no = int(m2.group(1))
                first_line = m2.group(2).strip()
                
                # Collect all subsequent non-directive lines as part of this insertion
                new_lines = []
                if first_line:
                    new_lines.append(first_line)
                
                # Capture subsequent lines until we hit another L##: directive or end
                while i < len(raw_lines):
                    peek = raw_lines[i]
                    # Stop if we hit another line directive
                    if re.match(r"\s*L\d+:", peek):
                        break
                    # Stop if we hit a range directive
                    if re.match(r"\s*L\d+\s*-\s*L\d+:", peek):
                        break
                    new_lines.append(peek.rstrip())
                    i += 1
                
                # Insert at line_no (this inserts before the line, pushing existing content down)
                if 1 <= line_no <= len(lines) + 1:
                    # Insert the new content at the specified line
                    before = lines[:line_no - 1]
                    after = lines[line_no - 1:]
                    lines = before + new_lines + after
                    applied_any = True
                    continue

        if not applied_any:
            return False, None

        new_content = "\n".join(lines)
        if current.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
            
        return True, new_content

    def _apply_unified_diff(self, file_path: str, diff_text: str) -> tuple[bool, str | None]:
        """Apply unified diff to file content.
        
        Returns (success, new_content)
        """
        try:
            original = self.window.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for diff {file_path}: {e}")
            return False, None

        if original is None:
            return False, None

        orig_lines = original.split("\n")
        new_lines = []
        orig_idx = 0

        lines = diff_text.splitlines()
        i = 0
        
        # Skip headers
        while i < len(lines) and (lines[i].startswith('--- ') or lines[i].startswith('+++ ')):
            i += 1

        hunk_header_re = re.compile(r"@@\s*-([0-9]+)(?:,([0-9]+))?\s*\+([0-9]+)(?:,([0-9]+))?\s*@@")
        any_applied = False

        while i < len(lines):
            if not lines[i].startswith('@@'):
                i += 1
                continue

            m = hunk_header_re.match(lines[i])
            i += 1
            
            if not m:
                continue
                
            orig_start = int(m.group(1))
            target_orig_pos = max(0, orig_start - 1)
            
            if target_orig_pos > orig_idx:
                new_lines.extend(orig_lines[orig_idx:target_orig_pos])
                orig_idx = target_orig_pos

            # Process hunk body
            while i < len(lines) and not lines[i].startswith('@@'):
                line = lines[i]
                i += 1
                
                if not line:
                    new_lines.append('')
                    continue
                    
                prefix = line[0]
                content = line[1:] if len(line) > 1 else ''
                
                if prefix == ' ':
                    # Context
                    if orig_idx < len(orig_lines):
                        new_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                    else:
                        new_lines.append(content)
                elif prefix == '-':
                    # Deletion
                    if orig_idx < len(orig_lines):
                        orig_idx += 1
                elif prefix == '+':
                    # Addition
                    new_lines.append(content)
                    
            any_applied = True

        # Append remaining
        if orig_idx < len(orig_lines):
            new_lines.extend(orig_lines[orig_idx:])

        if not any_applied:
            return False, None

        new_content = "\n".join(new_lines)
        if original.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
            
        return True, new_content    
    def execute_tool_from_menu(self, tool, query: str, extra_settings=None):
        """Execute a tool from the Tools menu with query and optional settings.
        
        Args:
            tool: The Tool instance to execute
            query: The search query string
            extra_settings: Optional dict with extra settings (e.g., {"sort": "score"})
        """
        try:
            # Store search context for pagination
            self._current_search_context = (tool, query, extra_settings or {})
            self._current_page = 1
            
            # Get enabled tools from project settings
            enabled_tools = self.window.project_manager.get_enabled_tools()
            
            # Log that tool is being executed
            self.window.chat.append_message("System", f"Executing {tool.name} tool...")
            
            # Create and start tool worker
            # Note: ToolWorker expects tool_name (str), query, enabled_tools, project_manager
            self.tool_worker = ToolWorker(
                tool_name=tool.name,
                query=query,
                enabled_tools=enabled_tools,
                project_manager=self.window.project_manager
            )
            
            # Store extra settings for later use (if needed)
            self.tool_worker.extra_settings = extra_settings or {}
            
            # Connect signals
            self.tool_worker.finished.connect(self._on_tool_from_menu_finished)
            
            # Show thinking indicator
            self.window.chat.show_thinking()
            
            # Start worker
            self.tool_worker.start()
            
        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Tool Execution Error",
                f"Error executing {tool.name}: {str(e)}"
            )
            print(f"Error in execute_tool_from_menu: {e}")
            import traceback
            traceback.print_exc()
    
    def _navigate_search_page(self, direction: int):
        """Navigate to next or previous page of search results.
        
        Args:
            direction: 1 for next page, -1 for previous page
        """
        if not self._current_search_context:
            QMessageBox.warning(self.window, "No Search", "No active search to navigate.")
            return
        
        self._current_page += direction
        if self._current_page < 1:
            self._current_page = 1
            QMessageBox.information(self.window, "First Page", "Already on the first page.")
            return
        
        tool, query, extra_settings = self._current_search_context
        
        try:
            # Get enabled tools from project settings
            enabled_tools = self.window.project_manager.get_enabled_tools()
            
            # Add page parameter to extra settings
            settings_with_page = (extra_settings or {}).copy()
            settings_with_page["page"] = self._current_page
            
            # Log the navigation
            page_word = "next" if direction > 0 else "previous"
            self.window.chat.append_message("System", f"Loading {page_word} page (page {self._current_page})...")
            
            # Create and start tool worker with page parameter
            self.tool_worker = ToolWorker(
                tool_name=tool.name,
                query=query,
                enabled_tools=enabled_tools,
                project_manager=self.window.project_manager
            )
            
            # Store settings including page
            self.tool_worker.extra_settings = settings_with_page
            
            # Connect signals
            self.tool_worker.finished.connect(self._on_tool_from_menu_finished)
            
            # Show thinking indicator
            self.window.chat.show_thinking()
            
            # Start worker
            self.tool_worker.start()
            
        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Navigation Error",
                f"Error loading next page: {str(e)}"
            )
            # Reset page on error
            self._current_page -= direction
    
    def _on_tool_from_menu_finished(self, result_text, extra_data):
        """Handle tool completion from menu execution."""
        self.window.chat.remove_thinking()
        
        # Show result message with page info if navigating
        if self._current_page > 1:
            result_text = f"{result_text} (Page {self._current_page})"
        self.window.chat.append_message("System", result_text)
        
        # If there are images, show image selection dialog with pagination
        if extra_data:
            from gui.dialogs.image_dialog import ImageSelectionDialog
            dialog = ImageSelectionDialog(
                extra_data, 
                self.window.project_manager.root_path, 
                self.window,
                on_next_page=lambda: self._navigate_search_page(1),
                on_prev_page=lambda: self._navigate_search_page(-1),
                current_page=self._current_page,
                has_search_context=self._current_search_context is not None
            )
            if dialog.exec():
                saved_paths = dialog.get_saved_paths()
                if saved_paths:
                    for p in saved_paths:
                        name = os.path.basename(p)
                        self.window.chat.append_message("System", f"Image saved to: {name}")

    
