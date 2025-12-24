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

## Short-Term (1–2 weeks)
- **RAG Indexing UX:**
  - Progress bar and per-file status; cancel/restart indexing.
  - Incremental index updates on save; debounce large files.
  - Exclusion rules (e.g., `.inkwellignore` or settings-based globs).
- **Edit Blocks Reliability:**
  - Non-text edits default to `.md/.txt` with safe fallbacks (done for images → descriptions).
  - Preview-and-apply flow consistently funnels through the diff dialog.
- **Chat Export & Context:**
  - Add project metadata block (title, tags) and optional headers when exporting chat to `.md`.
  - Quick-insert “Project Snapshot” citation in chat.
- **Sidebar File Ops:**
  - Rename/move (done), drag-and-drop (done), undo/redo (done), with tab retargeting.
  - Contextual actions: “Duplicate”, “Open Containing Folder”.
- **Image Save UX:**
  - Default folder (done), choose/create subfolder (done), filename prompt.
  - Optional post-save: insert `![alt](relative_path)` link into current doc.

## Medium-Term (1–2 months)
- **Project Schema & Templates:**
  - Project.yaml (optional) with title, description, tags, and structure.
  - Template wizards: novel, blog series, documentation set.
- **RAG Quality:**
  - Metadata-aware chunking (headings, front-matter, citation blocks).
  - Semantic search with citation snippets and confidence.
  - “Context Cards” pinned to chat (sources surfaced inline).
- **Agent Tools for Writers:**
  - Refactor assistant: propose rewrites with rationale, tone, and style controls.
  - Structure assistant: generate outlines, table-of-contents, and cross-links.
  - Reference assistant: fetch citations from selected docs and suggest inline links.
- **Image Studio:**
  - Prompt library + tags; per-workflow parameter presets.
  - Seed management, variant generation, batch outputs.
  - “Insert into doc” and “Attach to chat” shortcuts.
- **Workflow & Integrations:**
  - Export to static site (Markdown → Hugo/Jekyll-compatible output).
  - Git integration: commit, branch, and diff from within the app.

## Long-Term (3–6 months)
- **Multi-Project RAG:**
  - Cross-project references; “research” projects separate from “writing”.
- **Assistant Personas & Sessions:**
  - Save chat sessions tied to a persona and project context (e.g., “Editor”, “Researcher”, “Illustrator”).
- **Evaluation & Quality Gates:**
  - Style consistency checks; plagiarism detection (local, opt-in);
  - Prompt outcome tracking for recurring tasks.
- **Plug-in Architecture:**
  - Providers for different LLMs, vector DBs, and image backends.
  - Extension points for custom tools (e.g., grammar checkers, citation managers).

---

## RAG & LLM Enhancements
- **Indexing:** adaptive chunk sizes (respect headings), Markdown-aware parsing.
- **Citations:** show source path + heading; inline footnotes in AI responses.
- **Context Controls:** include/exclude folders, prefer “recently edited” files.
- **Safety:** never overwrite binaries; enforce diff review; annotate edits.
- **Persistent System Prompts:** per-project persona configuration, stored in settings or project.yaml.

## Image Generation & Analysis
- Workflow presets per project; prompt snippets by tag (e.g., “portrait”, “scene”).
- Seed & variation panel; grid outputs; quick compare.
- Save-and-insert shortcut into current doc; auto-relative paths.
- Batch generation from outline or character sheets.- **Batch Image Description:** Process all images in a folder with vision LLM to generate descriptions. Features:
  - Customizable instruction prompt (manual input).
  - Instruction template from a document (e.g., "Follow style in descriptions.md").
  - Save descriptions as .txt alongside images or in a manifest file.
  - Progress bar and cancellation support.
  - Optional: insert descriptions as image alt-text in Markdown docs.
## Project & Content Management
- Bulk operations: rename/move with pattern support; duplicate subtree.
- Smart links: autocomplete intra-project links; broken link detector.
- Outline view (tree + headings) syncs with editor; jump-to-section.
- Backlinks: show references to a doc; basic graph (optional).

## UX & Workflow
- Keyboard-centric flows (search, quick open, toggle preview, format).- **Search & Replace:** Find/replace in current file or across project; regex support; batch replace with preview.
  - Dialog or side panel with match highlighting and navigation.
- **Line Numbers:** Optional display in editor gutter; configurable via settings.
- **Model Switcher:** Quick-access dropdown in main window to change current LLM model.
  - Indicator showing which models are loaded/active in Ollama/LM Studio.
  - Auto-refresh to track when providers unload idle models.- Task palette: “Rewrite Selection”, “Summarize File”, “Explain Diff”, “Generate Image from Selection”.
- Diff dialog improvements: syntax highlighting; word-level diffs.
- Status area: LLM provider, model, context size, and current RAG sources.

## Integrations
- Git: staged diffs, commit messages, and “commit with AI summary”.
- Static site export: theme selection and asset bundling.
- Optional external search/tool hooks (user-provided scripts).

## Reliability & Performance
- Index cache with invalidation on change; warm startup.
- Async cancellations for long ops; clear feedback and recoverable states.
- Error surfaces standardized (dialogs + console logs).

## Developer Experience
- Configurable logging (levels: info/debug).
- Testable core modules (RAG, edit parsing, indexing).
- CI hooks (lint/type-check); release notes.

---

## Suggested Next Steps
1. RAG UX pass: cancelable indexer with progress; `.inkwellignore` support.
2. Citations in AI responses with clickable source links.
3. Prompt library + image workflow presets; insert-to-doc shortcut.
4. **Batch image description tool:** folder selection, customizable prompts, template-from-doc support.
5. Outline view and broken-link detector.
6. Git integration basics (commit, diff, push).

## Open Questions
- Preferred LLM providers and models to prioritize?
- Per-project settings vs global defaults (how much to persist in project)?
- Export pipelines (single best target first: Hugo/Jekyll/Docs-as-code?).
- Desired citation format (inline footnotes vs endnotes)?
