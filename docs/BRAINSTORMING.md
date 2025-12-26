# Inkwell AI — Brainstorming Ideas

Ideas and feature proposals to evolve Inkwell AI into a smooth, writer-focused workspace for Markdown + images, supercharged by RAG, LLM agents, and ComfyUI image generation.

## Vision
- A focused creative studio for long-form writing and visual ideation.
- Treat a project as a living knowledge base (Markdown + assets) where AI assists with drafting, revising, researching, and illustrating.
- Keep control local: transparent edits, review diffs, and commit changes intentionally.

## Guiding Principles
- Writer-first UX: low-friction, predictable, and easy to undo/redo.
- Trustworthy AI: cite sources, show context, be explicit about changes.
- Modular: plug-in providers (LLMs, RAG, image workflows) without lock-in.
- Local-first: fast indexing, cache results, no surprise network calls.

---

## Short-Term (1–2 weeks) — ✅ MOSTLY COMPLETE
- **RAG Indexing UX:** ✅ DONE
  - ✅ Progress bar and per-file status (with color-coded dots: green=indexed, orange=needs_reindex, red=not_indexed).
  - ✅ Cancel/restart indexing via IndexWorker thread.
  - ✅ Incremental index updates with mtime-based tracking for fast reindexing.
  - ⏳ Exclusion rules (e.g., `.inkwellignore` or settings-based globs) — pending.
- **Edit Blocks Reliability:** ✅ DONE
  - ✅ Non-text edits default to `.md/.txt` with safe fallbacks (done for images → descriptions).
  - ✅ Preview-and-apply flow consistently funnels through the diff dialog.
  - ✅ Fuzzy path matching for more forgiving edit proposals.
- **Chat Export & Context:** ⏳ PARTIAL
  - ✅ Auto-save chat sessions with browsable history (View > Chat History).
  - ✅ Chat export as Markdown (Save Chat as File).
  - ⏳ Add project metadata block (title, tags) and optional headers — pending.
  - ⏳ Quick-insert "Project Snapshot" citation in chat — pending.
- **Sidebar File Ops:** ✅ DONE
  - ✅ Rename/move with undo/redo, tab retargeting, and drag-and-drop.
  - ⏳ Contextual actions: "Duplicate", "Open Containing Folder" — pending.
- **Image Save UX:** ✅ DONE
  - ✅ Default folder (settings-based), choose/create subfolder, filename prompt.
  - ✅ Optional post-save: insert `![alt](relative_path)` link into current doc.

## Medium-Term (1–2 months) — ⏳ PARTIAL PROGRESS
- **Project Schema & Templates:** ⏳ PENDING
  - Project.yaml (optional) with title, description, tags, and structure.
  - Template wizards: novel, blog series, documentation set.
- **RAG Quality & Context Management:** ⏳ PARTIAL
  - ⏳ Metadata-aware chunking (headings, front-matter, citation blocks) — pending.
  - ⏳ Semantic search with citation snippets and confidence — pending.
  - ✅ Context level selector (None / Visible Tab+Mentioned / All Open Tabs / Full) — controls which files are included as context.
  - ⏳ "Context Cards" pinned to chat (sources surfaced inline) — pending.
- **Agent Tools for Writers:** ⏳ PARTIAL
  - ✅ Tool system infrastructure: plugin-based architecture with per-tool configurable settings (via `.inkwell/config.json`).
  - ⏳ Refactor assistant: propose rewrites with rationale, tone, and style controls — pending.
  - ⏳ Structure assistant: generate outlines, table-of-contents, and cross-links — pending.
  - ⏳ Reference assistant: fetch citations from selected docs and suggest inline links — pending.
- **Image Studio:** ✅ DONE
  - ✅ Prompt library + tags; per-workflow parameter presets.
  - ✅ Seed management, variant generation, batch outputs.
  - ✅ "Insert into doc" and "Attach to chat" shortcuts.
- **Workflow & Integrations:** ⏳ PENDING
  - Export to static site (Markdown → Hugo/Jekyll-compatible output).
  - Git integration: commit, branch, and diff from within the app.
- **Program-Wide Asset Library:** ⏳ NEW FEATURE (HIGH VALUE)
  - **Concept:** Separate global asset repository (outside project folders) for reusable content across all projects.
  - **Indexed & Searchable:** RAG index for program-level assets; clearly separated from project indices in debug output.
  - **Asset Types:**
    - **LLM Instructions/Prompts:** System prompts, instruction templates, style guides, writing principles.
    - **ComfyUI Workflows:** Global workflow library with tags (portrait, landscape, style-transfer, etc.).
    - **Tone/Style References:** Character voice guides, narrative styles, tone examples.
    - **Tool Snippets:** Reusable tool definitions and configurations (search queries, formatting rules, etc.).
    - **Chat Templates:** Pre-written conversation starters, common questions, refactoring commands.
  - **Storage:** Flat directory structure in `~/.inkwell_assets/` or similar (OS-configurable).
  - **Organization:** Tags/categories, version tracking, metadata (created date, last used, usage count).
  - **Discovery:** 
    - Dedicated "Asset Library" view/dialog in main UI.
    - Quick insert/link UI in editor and chat with fuzzy search.
    - Tag-based filtering and grouping.
  - **Usage in Projects:**
    - **Include in context:** Option to include program-level instruction assets in RAG context (with clear "system" indicator).
    - **Apply workflows:** Drag-drop or "Use This" button to apply global workflow to image gen.
    - **Clone to project:** Copy and customize global asset into project-level assets.
  - **Workflow Integration:**
    - When user creates a good prompt/workflow in a project, offer "Save to Library" option.
    - Import from library with one-click insertion.
  - **Metadata & Search:**
    - Each asset has: title, description, tags, creation date, last modified, usage count.
    - Full-text search across all asset content.
    - Pinned/favorites for frequently used assets.

## Long-Term (3–6 months) — ⏳ PLANNING STAGE
- **Multi-Project RAG:**
  - Cross-project references; "research" projects separate from "writing".
- **Assistant Personas & Sessions:**
  - ✅ Save chat sessions tied to a persona and project context (PARTIALLY DONE — chat sessions saved with timestamps and titles).
  - ⏳ Per-persona system prompts and settings — pending.
- **Evaluation & Quality Gates:**
  - Style consistency checks; plagiarism detection (local, opt-in);
  - Prompt outcome tracking for recurring tasks.
- **Plug-in Architecture:**
  - ✅ Providers for different LLMs (DONE — Ollama, LM Studio).
  - ✅ Extension points for custom tools (DONE — Tool base class and registry).
  - ⏳ Vector DB providers (currently ChromaDB-only).
  - ⏳ Image backend pluggability (currently ComfyUI-only).

---

## RAG & LLM Enhancements

### Indexing & Chunking
- ✅ PARTIAL
  - ✅ Incremental updates with mtime tracking (DONE).
  - ⏳ **Markdown-aware parsing** — respect heading hierarchy, code blocks, frontmatter
    - Parse document structure (H1/H2/H3 headings) to create semantic boundaries
    - Keep code blocks together (don't split mid-function)
    - Preserve frontmatter (YAML/TOML) as context
    - Create chunk metadata: heading path, section context, language/type
  - ⏳ **Adaptive chunk sizes** — balance granularity with context window
    - Small chunks (300–500 tokens) for dense prose/dialogue
    - Larger chunks (800–1000 tokens) for code, reference material
    - Minimum 200 tokens; maximum 1500 (configurable)
    - Overlap 50–100 tokens between chunks to preserve context flow
  - ⏳ **Smart chapter/section breaks** — index full sections as retrievable units
    - Allow retrieval at multiple levels (single paragraph → full chapter)
    - Store parent heading metadata for recontextualizing snippets

### Hybrid Search
- ⏳ PENDING
  - **Combine keyword + semantic search** for better recall
    - Keyword search: BM25 for exact term matches (fast, deterministic)
    - Semantic search: Vector embeddings for intent/concept matching
    - Merge results with weighted scoring (e.g., 0.4 keyword + 0.6 semantic)
    - Return ranked union of both, deduplicated by chunk ID
  - **Re-ranking by relevance** — use LLM embeddings to score results
    - Compute embedding similarity between query and top-k candidates
    - Re-order by semantic closeness before sending to LLM
    - Show confidence scores in debug output
  - **Fallback strategy** — if semantic search has few results, boost keyword matches
    - Minimum 3 results guaranteed (keyword-only if needed)
    - Show which search method contributed each result

### Token Optimization & Context Caching
- ⏳ PENDING
  - **Smart context truncation**
    - Estimate tokens per chunk; cap context at 70% of window
    - Prioritize: (1) Recent edits, (2) Explicitly mentioned files, (3) Highest semantic score
    - Drop low-confidence chunks first when exceeding limit
    - Show "context full" warning with dropped chunks listed
  - **Context caching layer** — reuse context across sequential queries in same session
    - Cache RAG results + embeddings for recent 5 files for 10 minutes
    - If same file queried again, return cached chunks + delta (new edits only)
    - Invalidate cache on file write or project reindex
    - Debug output: show cache hits/misses and tokens saved
  - **Conversation-aware context** — track which files/topics have been discussed
    - Build implicit "conversation context" from chat history (last 5 messages)
    - Prefer chunks semantically similar to recent exchanges
    - De-duplicate: if a chunk was already in context 2 messages ago, skip it this time
    - Optional: let user "lock" important context (pin to conversation)
  - **Token accounting dashboard** (optional future enhancement)
    - Show context size per query, cumulative tokens per session
    - Alerts if approaching model limit; suggest pruning

### Citations & Transparency
- ⏳ PARTIAL
  - ✅ RAG sources shown in debug output with token counts (DONE).
  - ⏳ **Show source path + heading in responses**
    - Format: `[source: project/Characters/Protag.md § Character Traits]`
    - Hyperlink to file location if in editor
    - Include chunk ID for debugging
  - ⏳ **Inline footnotes in AI responses**
    - LLM learns to format: `...some text[^1]` with reference at bottom
    - Footnote: `[^1]: From Characters/Protag.md (line 42–56)`
    - User can click to jump to source in editor

### Context Controls & Preferences
- ✅ DONE
  - ✅ Context level selector with four modes (None / Visible Tab+Mentioned / All Open Tabs / Full).
  - ✅ Include/exclude based on context level; token estimates shown.
  - ⏳ **Prefer "recently edited" files** — boost priority of fresh content
    - Weight chunks by recency (newer = higher priority)
    - Time decay: files edited <1h ago get 1.0x boost, <1d = 0.8x, <1w = 0.5x
    - Optional: let user toggle "recent-first" mode

### Safety & Verification
- ✅ DONE
  - ✅ Never overwrite binaries; enforce diff review.
  - ✅ Annotate edits with inline controls.
  - ⏳ **Fact-checking** — validate LLM claims against sources
    - For edit proposals: check if referenced source chunks are actually in context
    - Flag edits that cite nonexistent or distant sources
    - Show confidence: "claim matches source exactly" vs "paraphrased" vs "inferred"

### Persistent System Prompts & Personas
- ⏳ PENDING
  - Per-project persona configuration, stored in settings or project.yaml
  - Multiple personas per project (writer, editor, critic) with distinct prompts
  - Context-aware system prompts (e.g., "You are writing noir dialogue" if editing Characters/Noir.md)

## Image Generation & Analysis
- ✅ DONE
  - ✅ Workflow presets per project; prompt snippets by tag (e.g., "portrait", "scene").
  - ✅ Seed management, variant generation, batch outputs.
  - ✅ Save-and-insert shortcut into current doc; auto-relative paths.
  - ✅ Quick compare grid outputs.
- ⏳ **Batch Image Description:** (PENDING)
  - Process all images in a folder with vision LLM to generate descriptions.
  - Customizable instruction prompt (manual input).
  - Instruction template from a document (e.g., "Follow style in descriptions.md").
  - Save descriptions as .txt alongside images or in a manifest file.
  - Progress bar and cancellation support.
  - Optional: insert descriptions as image alt-text in Markdown docs.

## Project & Content Management
- ✅ PARTIAL
  - ✅ Rename/move with undo/redo (DONE).
  - ⏳ Bulk operations with pattern support; duplicate subtree — pending.
  - ⏳ Smart links: autocomplete intra-project links; broken link detector — pending.
  - ⏳ Outline view (tree + headings) syncs with editor; jump-to-section — pending.
  - ⏳ Backlinks: show references to a doc; basic graph — pending.

## Asset Management (Project vs. Program-Level) — ⏳ NEW FEATURE
- **Architecture Overview:**
  - **Project Assets:** Stored in `project_root/assets/` (Markdown, images, ComfyUI workflows specific to this project).
  - **Program Assets:** Stored in `~/.inkwell/assets/` (global, reusable across all projects, indexed separately).
  - **Clear Separation:** Different RAG indices, distinct UI indicators, separate storage locations.
  
- **Project-Level Assets:** ✅ PARTIAL
  - ✅ Image save/organization (DONE).
  - ✅ Custom project workflows (DONE via image studio).
  - ⏳ Project-specific instruction sets — pending.
  - ⏳ Project README/guidelines — pending.
  
- **Program-Level Assets:** ⏳ PENDING (PLANNED)
  - **LLM Instructions Library:**
    - Reusable system prompts (editor role, researcher role, critic role, etc.).
    - Writing style guides (dramatic, noir, comedic, technical, etc.).
    - Instruction templates for common tasks (summarize, outline, refactor, explain, etc.).
    - Tone/voice examples with sample inputs/outputs.
    - Each asset versioned; can be updated globally or cloned to project for customization.
  
  - **ComfyUI Workflow Library:**
    - Global workflow templates with metadata (name, tags, parameters).
    - Categorized: portraits, landscapes, scene generation, style transfer, upscaling, etc.
    - Parameter presets (e.g., "cinematic quality", "watercolor", "sketch style").
    - Usage tracking (count, last used, rating).
  
  - **Reusable Tool Configurations:**
    - Saved tool settings for Web Reader (character limits), Wikipedia (language, include links), etc.
    - Searchable by tool name and use case.
  
  - **Chat Templates:**
    - Pre-written prompts for common workflows (e.g., "Generate a character description", "Outline a chapter", "Find plot holes").
    - Can be inserted into current chat with optional parameter substitution.
  
  - **Asset Discovery & Usage:**
    - **Library Browser:** Dedicated dialog or sidebar showing all program assets, filterable by type and tags.
    - **Inline Insert:** Quick fuzzy-search popup when typing in chat (e.g., `@system-prompt` or `@workflow`).
    - **Editor Link:** In Markdown, insert asset references like `[system-prompt: editor](inkwell://assets/prompts/editor)` for auto-expansion in chat context.
    - **Workflow Shortcuts:** Drag-drop or "Use This Workflow" button to apply global workflows to image gen.
    - **Clone to Project:** "Save variant to project" option to copy and customize an asset locally.
  
  - **Usage Analytics:**
    - Track which assets are used most frequently.
    - Suggest improvements based on patterns (e.g., "You use the 'editor' prompt in 80% of projects").
    - Display "last used" timestamp for quick access.
  
  - **Versioning & Sync:**
    - Program assets versioned (stored as `asset_name_v1.md`, `asset_name_v2.md`).
    - Option to auto-update to latest version or lock to specific version in projects.
    - Changelog for significant asset updates.
  
  - **RAG Integration:**
    - Program assets indexed separately; can toggle inclusion in context queries.
    - Debug output shows "Program Assets RAG" vs "Project Assets RAG" distinctly.
    - Option to search program assets only or project+program combined.
  
  - **Quick Create Workflow:**
    - When user saves successful prompt/workflow in a project, offer "Add to Program Library" option.
    - Simple dialog: title, tags, description, optional category.
    - Automatically moved/copied to `~/.inkwell/assets/` with metadata.

## UX & Workflow — ⏳ PARTIAL
- ✅ PARTIAL
  - ✅ Keyboard-centric flows: Ctrl+Enter to send messages (DONE).
  - ⏳ Search, quick open, toggle preview — pending.
- **Search & Replace:** ⏳ PENDING
  - Find/replace in current file or across project; regex support; batch replace with preview.
  - Dialog or side panel with match highlighting and navigation.
- **Line Numbers:** ⏳ PENDING
  - Optional display in editor gutter; configurable via settings.
- **Model Switcher:** ✅ DONE
  - ✅ Quick-access dropdown in main window to change provider (Ollama/LM Studio) and model.
  - ✅ Indicator showing which models are available; vision capability indicators (👁️ emoji).
  - ✅ Auto-refresh button (🔃) to reload available models from provider.
- **Chat UI Overhaul:** ✅ DONE
  - ✅ Emoji-only buttons for compact layout (📁 save, 📄 copy, 📋 clipboard, 🔄 regenerate, 🔃 refresh).
  - ✅ FlowLayout for wrapping buttons instead of forcing single line.
  - ✅ QPlainTextEdit for multi-line input (40–80px) with Ctrl+Enter support.
  - ✅ Message editing and deletion with inline controls (✏️ Edit, 🗑️ Delete).
  - ✅ Regenerate last response with automatic history cleanup.
  - ✅ Auto-continue incomplete responses (detects unclosed blocks and abrupt endings).
- **Debug & Status Output:** ✅ DONE
  - ✅ Console debug messages showing context level, RAG files with token estimates, and active/open file info.
  - ⏳ Status bar visual indicator for LLM provider, model, and context size — partial.
- **Task Palette:** ⏳ PENDING
  - "Rewrite Selection", "Summarize File", "Explain Diff", "Generate Image from Selection".
- **Diff Dialog Improvements:** ✅ DONE
  - ✅ Side-by-side comparison with preview toggle.
  - ✅ Summary stats (added/removed/changed lines).
  - ⏳ Word-level diffs — pending.

## Integrations
- ⏳ PENDING
  - Git: staged diffs, commit messages, and "commit with AI summary".
  - Static site export: theme selection and asset bundling.
  - Optional external search/tool hooks (user-provided scripts).

## Reliability & Performance
- ⏳ PARTIAL
  - ✅ Index cache with invalidation on change via mtime tracking (DONE).
  - ✅ Async cancellations for long ops (IndexWorker); clear feedback (DONE).
  - ✅ Recoverable states via progress indicators (DONE).
  - ✅ Error surfaces standardized (dialogs + console logs) (DONE).

## Developer Experience
- ✅ PARTIAL
  - ✅ Configurable logging (debug output visible in console) (DONE).
  - ✅ Testable core modules (RAG, edit parsing, indexing) (DONE).
  - ⏳ CI hooks (lint/type-check); release notes — pending.

---

## Suggested Next Steps (Prioritized)
1. ✅ RAG UX pass: cancelable indexer with progress; mtime-based tracking (DONE). **Next:** `.inkwellignore` support.
2. ✅ Citations in RAG context (sources shown in debug output). **Next:** clickable source links in chat.
3. ✅ Prompt library + image workflow presets; insert-to-doc shortcut (DONE).
4. **Program-Level Asset Library:** NEW HIGH-VALUE FEATURE
   - Store global LLM instructions, workflows, tone guides outside projects.
   - Separate RAG index for program assets; clear UI separation.
   - Quick-insert in chat via fuzzy search and inline references.
   - "Save to Library" workflow from successful prompts/workflows.
   - Particularly valuable for ComfyUI workflows (can be version-controlled and reused globally).
5. **Batch image description tool:** folder selection, customizable prompts, template-from-doc support. (PENDING)
6. ⏳ Outline view and broken-link detector. (PENDING)
7. ⏳ Git integration basics (commit, diff, push). (PENDING)
8. ✅ Chat history and session management (DONE).
9. ✅ Provider/model selection with vision indicators (DONE).
10. ✅ Response auto-completion for incomplete blocks (DONE).
11. ⏳ Export chat sessions with project metadata headers. (PENDING)
12. ⏳ Per-project system prompts and persona configuration. (PENDING)
13. ⏳ Search & replace across project with regex support. (PENDING)
14. ⏳ Integration between project and program assets (clone, import, override). (PENDING)

## Open Questions & Decisions
- ✅ Per-project settings: `.inkwell/config.json` now stores enabled tools and per-tool settings. Works alongside global QSettings for provider/model defaults.
- Desired citation format: inline footnotes vs endnotes? (Still TBD for RAG sources in responses.)
- Export pipelines (single best target first: Hugo/Jekyll/Docs-as-code?).
- Should "Batch image description" be a Tool or a native feature?
- Context level modes fully defined; should we add a "Custom" mode to select specific folders?
- Should per-project system prompts be stored in project.yaml or `.inkwell/config.json`?
---

## Asset Management: Project vs. Program-Level

### Concept
The key insight is that some assets are *project-specific* (characters, plot outlines, custom tools) while others are *globally useful* (tone guides, LLM instructions, ComfyUI workflows, chat templates). Currently, everything is project-local. We should:
- Keep project assets in `project_root/assets/`
- Store program-wide assets in `~/.inkwell/assets/`
- Index both via RAG with clear separation in debug output
- Allow assets to be "promoted" from project to program (save-to-library)
- Allow assets to be cloned from program to project (with optional auto-updates)

### Project-Level Assets (Current)
- Character sheets, location guides, plot notes
- Project-specific prompts and tone guides
- Custom workflow variants for this project
- Indexed in project's RAG

### Program-Level Assets (New)
1. **LLM Instructions & Prompts**
   - Character personality guides (reusable across projects)
   - Tone/style templates ("noir detective," "cozy mystery," etc.)
   - System prompts for different writing tasks (outlining, dialogue, description)
   - Taggable, searchable, with version history

2. **ComfyUI Workflows**
   - Global workflow library (image generation, upscaling, style transfer, etc.)
   - With parameter presets and example outputs
   - Can be used in any project; each project can have overrides
   - Version tracking for workflow updates

3. **Tool Configurations**
   - Custom tool definitions shared across projects
   - Search/web lookup templates
   - API integration setups

4. **Chat Templates & Conversation Starters**
   - Prompt sequences for common writing tasks
   - Session recovery / continuation patterns
   - Q&A templates for different project types

5. **Usage Analytics & Ratings**
   - Track which assets are most useful
   - Community "best practices" (if shared with others)
   - Auto-suggest frequently-used assets in context

### Asset Discovery & Usage
1. **Library Browser Dialog** - Browse all program assets, preview, insert into project
2. **Inline Fuzzy Search** - `/` in chat to quick-insert an instruction or prompt
3. **Editor Smart Links** - `@tone:noir` references resolved from library
4. **Workflow Shortcuts** - ComfyUI workflow quick-menus in image generation dialog
5. **Clone on First Use** - Drag program asset into project to create local override

### Storage & Metadata
Program assets stored in `~/.inkwell/assets/` with structure:
```
~/.inkwell/assets/
├── llm_instructions/
│   ├── character_guides/
│   ├── tone_templates/
│   └── system_prompts/
├── workflows/
│   ├── image_gen/
│   └── comfyui_presets/
├── tools/
├── chat_templates/
└── .index/  (RAG database for program assets)
```

Each asset has metadata (tags, creation date, version, usage count, rating).

### RAG Integration
- Separate `program_assets_index` in addition to project index
- Debug output shows `[Project RAG]` and `[Program RAG]` separately
- Search can filter by source or search both simultaneously
- Assets inherit project context when used (no cross-contamination)

### Versioning & Sync
- Program assets are timestamped (e.g., `tone_guide_v1_2024-01-15.md`)
- Projects can opt-in to auto-updates or pin to specific version
- Changelog stored alongside asset
- Cloned assets in projects can be manually synced or kept as local overrides

### Quick-Create Workflow
When a prompt/workflow is successful in a project:
1. Right-click → "Save to Program Library"
2. Choose category, add tags, version notes
3. Asset becomes available globally for next use
4. Other projects can discover and reuse it

This makes the library grow organically from successful work, not manual curation.