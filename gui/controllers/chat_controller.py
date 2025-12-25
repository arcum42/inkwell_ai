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
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QSettings

from gui.workers import ChatWorker, ToolWorker, BatchWorker
from gui.dialogs.diff_dialog import DiffDialog
from gui.dialogs.chat_history_dialog import ChatHistoryDialog
from gui.dialogs.image_dialog import ImageSelectionDialog
from gui.editor import DocumentWidget, ImageViewerWidget


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
        self.pending_edits = {}  # id -> (path, content)
        self._raw_ai_responses = []  # Track raw AI responses before parsing
        self._last_selection_info = None  # Store selection context
        self._last_token_usage = None
        self.context_level = "visible"  # Default context level
        self.chat_mode = "edit"  # Default mode: edit or ask
        self.worker = None
        self.tool_worker = None
        self.batch_worker = None
        
    def handle_chat_message(self, message):
        """Handle incoming chat message from user.
        
        Args:
            message: User message text
        """
        print(f"DEBUG: Context level for this message: {self.context_level}")
        self.chat_history.append({"role": "user", "content": message})
        
        provider = self.window.get_llm_provider()
        provider_name = self.settings.value("llm_provider", "Ollama")
        if provider_name == "Ollama":
            model = self.settings.value("ollama_model", "llama3")
        else:
            model = self.settings.value("lm_studio_model", "llama3")
            
        token_usage = estimate_tokens(message)
        token_breakdown = {"User message": token_usage}

        # Update chat header to reflect current model
        try:
            models = provider.list_models()
            vision_models = [m for m in models if provider.is_vision_model(m)]
            self.window.chat.update_model_info(provider_name, model, models, vision_models)
        except Exception:
            pass
        
        # Retrieve context if RAG is active and context level allows
        context = []
        mentioned_files = set()
        included_files = set()  # Track all files already included in system prompt
        
        if self.context_level != "none" and self.window.rag_engine:
            print(f"DEBUG: Querying RAG for: {message}")
            context = self.window.rag_engine.query(message, n_results=5, include_metadata=True)
            print(f"DEBUG: Retrieved {len(context)} chunks")
            
            # Extract mentioned file paths and estimate tokens
            rag_file_info = []
            for chunk in context:
                meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                source = meta.get("source")
                if source:
                    mentioned_files.add(source)
            
            if mentioned_files:
                for source in sorted(mentioned_files):
                    try:
                        content = self.window.project_manager.read_file(source)
                        if content:
                            tokens = estimate_tokens(content)
                            rag_file_info.append(f"{source} ({tokens} tokens)")
                            token_usage += tokens
                            token_breakdown[f"RAG: {source}"] = token_breakdown.get(f"RAG: {source}", 0) + tokens
                            included_files.add(source)  # Mark as included
                    except Exception:
                        pass
                
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
        
        # Add other open tabs if context level is "all_open" or "full"
        if self.context_level in ("all_open", "full"):
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

        # Inject Project Structure
        if self.window.project_manager.root_path:
            structure = self.window.project_manager.get_project_structure()
            if len(structure) > 20000:
                structure = structure[:20000] + "\n... (truncated)"
            system_prompt += f"\n\nProject Structure:\n{structure}"
            token_usage += estimate_tokens(structure)
            token_breakdown["Project structure"] = estimate_tokens(structure)
            
        # Include selection info if present
        self._include_selection_info(active_path, token_usage, token_breakdown)
        
        # Add final reminder for ask mode
        if self.chat_mode == "ask":
            print("DEBUG: ASK MODE ACTIVE - Disabling tools and edit instructions")
            system_prompt += (
                "\n\n" + "="*60 + "\n"
                "REMINDER: ASK MODE - No file modifications, no patches, no diffs.\n"
                "Provide helpful information and plain text suggestions only.\n"
                "="*60
            )
            # Disable all tools in ask mode
            enabled_tools = set()  # Empty set disables all tools
        
        print(f"DEBUG: Enabled tools for this request: {enabled_tools}")
        print(f"DEBUG: Chat mode: {self.chat_mode}")
             
        self.worker = ChatWorker(
            provider,
            self.chat_history,
            model,
            context,
            system_prompt,
            images=attached_images if is_vision else None,
            enabled_tools=enabled_tools,
            mode=self.chat_mode,
        )
        self.worker.response_thinking_start.connect(self.on_chat_thinking_start)
        self.worker.response_thinking_chunk.connect(self.on_chat_thinking_chunk)
        self.worker.response_thinking_done.connect(self.on_chat_thinking_done)
        self.worker.response_chunk.connect(self.on_chat_chunk)
        self.worker.response_received.connect(self.on_chat_response)
        self.worker.start()

        # Update dashboard with latest token estimate
        if context:
            for chunk in context:
                if isinstance(chunk, dict):
                    ctokens = estimate_tokens(chunk.get("text", ""))
                    token_usage += ctokens
                    source = chunk.get("metadata", {}).get("source", "context")
                    token_breakdown[f"RAG chunk: {source}"] = token_breakdown.get(f"RAG chunk: {source}", 0) + ctokens
                else:
                    ctokens = estimate_tokens(str(chunk))
                    token_usage += ctokens
                    token_breakdown["RAG chunk"] = token_breakdown.get("RAG chunk", 0) + ctokens
        self.window._update_token_dashboard(token_usage, token_breakdown)

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
            "\n\n## Edit Formats\n"
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
        
        # If we were streaming, replace the streamed content with parsed version
        # Otherwise, add as a new message
        if self.window.chat.streaming_response:
            self.window.chat.finish_streaming_response(display_response, raw_text=response)
        else:
            self.window.chat.append_message("Assistant", display_response, raw_text=response)
        
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
        
        # Capture any edit:XYZ ids already present in the response
        provided_edit_ids = re.findall(r"edit:([0-9a-fA-F-]{6,})", response)
        seen_ids = set()
        provided_edit_ids = [eid for eid in provided_edit_ids if not (eid in seen_ids or seen_ids.add(eid))]

        def next_edit_id() -> str:
            if provided_edit_ids:
                return provided_edit_ids.pop(0)
            return str(uuid.uuid4())
        
        # Check for tool execution requests
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
    
    def _continue_response(self):
        """Automatically continue the previous response."""
        provider = self.window.get_llm_provider()
        model = self.settings.value("ollama_model", "llama3")
        system_prompt = self.window.project_manager.get_system_prompt(
            self.settings.value("system_prompt", "You are Inkwell AI, a creative writing assistant.")
        )

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
        
        # Get RAG context if available
        context = []
        if self.window.rag_engine and last_user_idx is not None:
            query = self.chat_history[last_user_idx]['content']
            context = self.window.rag_engine.query(query, n_results=5)
        
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
    
    def on_mode_changed(self, mode):
        """Handle chat mode change.
        
        Args:
            mode: New mode (ask or edit)
        """
        self.chat_mode = mode
        print(f"DEBUG: Chat mode changed to: {mode}")

    def on_tool_finished(self, result_text, extra_data):
        """Handle tool execution completion.
        
        Args:
            result_text: Tool result text
            extra_data: Additional data from tool (e.g., image results)
        """
        self.window.chat.remove_thinking()
        
        # Check if this is an image search result with image data
        if extra_data and isinstance(extra_data, list) and len(extra_data) > 0:
            # Check if it looks like image results (has 'image' or 'thumbnail' keys)
            if isinstance(extra_data[0], dict) and ('image' in extra_data[0] or 'thumbnail' in extra_data[0]):
                # Show image selection dialog
                from gui.dialogs.image_dialog import ImageSelectionDialog
                if self.window.project_manager.root_path:
                    dialog = ImageSelectionDialog(extra_data, self.window.project_manager.root_path, self.window)
                    if dialog.exec():
                        saved_paths = dialog.saved_paths
                        if saved_paths:
                            result_text += f"\n\nSaved {len(saved_paths)} images:\n" + "\n".join(saved_paths)
                        else:
                            result_text += "\n\nNo images were saved."
                    else:
                        result_text += "\n\nImage selection cancelled."
                else:
                    result_text += "\n\nError: No project open to save images."
        
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
            url: Clicked URL (edit:ID format)
        """
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
