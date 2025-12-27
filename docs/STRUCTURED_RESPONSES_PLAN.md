# Structured Responses (JSON Schema) Plan

## Goals
- Introduce opt-in structured responses using JSON Schema.
- Default OFF globally; enabled only for LM Studio Native SDK initially.
- Provide graceful fallback for providers/models that cannot handle structured output.
- Allow per-request schema selection (generic and tool-specific) with clear UI affordances.
- Reduce ad-hoc text parsing for patches/updates by delivering typed sections.

## Design Overview
- Capabilities: Add `supports_structured_output` to providers; true only for LM Studio Native SDK in the first cut.
- Switches: Global settings toggle + per-request override in chat; pipeline must carry `structured_enabled` and `schema_id` to the provider call.
- Schemas: Central registry of named JSON Schemas with provider allowlists; tools can supply schemas for their calls.
- UX: User can pick schema (or none), see schema badge in responses, and toggle parsed vs raw JSON.
- Fallbacks: If disabled/unsupported/invalid, revert to standard text responses with a warning badge, never crash.

## Work Items by Layer

### Core: Provider and Registry
- Add `supports_structured_output` to `LLMProvider` base; set true in `LMStudioNativeProvider` only.
- Create `core/llm/schemas.py` registry with APIs: `register_schema(schema_id, body, providers=None, description=None, version=None)`, `get_schema(schema_id)`, `list_schemas(allowed_provider=None)`.
- Seed starter schemas:
  - `basic_answer`: `answer` (string, required), `notes` (string, optional).
  - `diff_patch`: `summary` (string), `edits` (array of objects: `path`, `before`, `after`, optional `warnings`).
  - `tool_result`: `request`, `result`, optional `citations` (array of strings).
  - `chat_split`: `analysis`, `answer`, optional `actions` (array of strings) to separate discussion vs answer.
- Allow tools to register schemas (e.g., tool class static method returning schema id or definition).

### Core: LM Studio Native Structured Request
- Map schema to SDK `response_format` per https://lmstudio.ai/docs/python/llm-prediction/structured-response.
- Extend `LMStudioNativeProvider.chat()`/`chat_stream()` to accept optional `schema_id`/`schema_body` and inject `response_format` when `supports_structured_output` and toggle/schema are set.
- Keep streaming disabled when structured mode is active unless the SDK explicitly supports streaming + structured (phase 2 later).

### Pipeline: Controllers and Workers
- Thread new options through `ChatController` → `ChatWorker` → provider call: `structured_enabled: bool`, `schema_id: Optional[str]`.
- Persist last-selected schema per provider/model in `QSettings` for convenience.
- When in ask/edit modes, allow different defaults (e.g., `chat_split` for ask, `diff_patch` for edit) but keep user override.
- On response: detect structured payload, parse JSON, optionally validate against schema, and store both raw and parsed forms for rendering.
- Failure handling: if parsing/validation fails, fall back to raw text and emit a warning in the chat transcript.

### UI/UX
- Settings dialog: global checkbox "Enable structured responses (JSON schema)" with tooltip explaining provider support and fallback.
- Chat composer advanced section: schema dropdown (None, Basic Answer, Diff/Patch, Tool Result, Chat Split, plus tool-provided entries when relevant).
- Response bubble: show a schema badge, a toggle for parsed vs raw JSON, and a warning badge on validation failure.
- Optional: per-message toggle to disable structured output quickly.

### Persistence & Metadata
- Store `structured_enabled` and `schema_id` in `QSettings`; include schema id in saved chat metadata for reproducibility.
- Log schema id/provider/validation outcome to debug console for troubleshooting.

### Edge Cases & Fallbacks
- Provider without support or global toggle off: ignore schema and call provider normally.
- Selected schema not allowed for the current provider: ignore and warn user; list only allowed schemas in dropdown to reduce this case.
- Malformed JSON or validation failure: show warning, render raw text, keep conversation flowing.
- Streaming: initially disable with structured mode; revisit once LM Studio SDK streaming + structured is confirmed stable.

### Tests
- Registry tests: registration, retrieval, provider allowlist filtering, and duplicate handling.
- LM Studio Native tests: request with schema returns JSON matching schema; failure path returns warning + raw text.
- Controller/worker tests: toggle honored, schema id propagated, fallback on unsupported provider.
- UI tests (where applicable): settings toggle persistence; schema dropdown wiring.

### Documentation
- Update docs: how to enable structured responses, current provider support (LM Studio Native only), built-in schemas, and fallback behavior.
- Include example response payloads for each starter schema.

### Future Extensions
- Streaming structured responses once confirmed stable in SDK.
- Per-tool schemas auto-selected by tool calls; tool UI hints showing expected schema.
- Project-level schema overrides (e.g., `.inkwell/config.json`) and user-added schemas in the registry.
- Structured diffs piped directly into DiffDialog without ad-hoc string parsing.

## Execution Checklist (Prep for Implementation)
- [ ] Add capability flag to providers and wire global/per-request toggles through controller/worker.
- [ ] Build schema registry with starter schemas and provider allowlists.
- [ ] Implement LM Studio Native request path for `response_format` and response parsing.
- [ ] Add UI hooks: settings checkbox, chat schema dropdown, response badges/toggles.
- [ ] Add validation/fallback logic and metadata logging.
- [ ] Cover with targeted tests and update docs.
