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

## Phased Implementation
- Phase 0 — Groundwork: Capability flags and toggles
  - Add `supports_structured_output` in providers (LM Studio Native = true).
  - Add global toggle and per-request override; thread through controller → worker → provider.
  - Acceptance: Toggle persists; unsupported providers cleanly ignore without errors.

- Phase 1 — LM Studio Native (non‑streaming) MVP
  - Implement `response_format` wiring for LM Studio Native SDK.
  - Add schema selection in chat (None/default plus starter schemas).
  - Parse JSON response and display structured sections; provide raw JSON view.
  - Acceptance: Valid JSON mapped to UI sections; invalid JSON falls back with warning.

- Phase 2 — Validation & UX polish
  - Optional `jsonschema` validation against selected schema.
  - Response badges (schema id), warning indicators, and per-message disable.
  - Acceptance: Validation outcome shown; no crashes on malformed payloads.

- Phase 3 — Schema registry & tool integration
  - Implement `core/llm/schemas.py` registry with provider allowlists.
  - Tools can register/select their schemas automatically.
  - Acceptance: Tool request auto-selects schema; registry lists filter by provider.

- Phase 4 — Streaming structured responses (LM Studio)
  - Evaluate SDK support; buffer fragments and parse at completion.
  - Add streaming-compatible UX; preserve thinking indicators.
  - Acceptance: Streaming responses render structured at end with correct fallbacks.

## Lifecycle States (Runtime)
- Global Off: Structured disabled; all providers return standard text.
- On + Unsupported Provider: Ignore schema; warn user if schema was selected.
- On + Supported Provider + No Schema: Provider returns standard text; shows no schema badge.
- On + Supported + Schema Selected → Response
  - Valid JSON: Parsed + rendered structured sections; badge shows schema id.
  - Invalid JSON / Schema mismatch: Soft fallback to raw text with warning; log details.
- Streaming Mode (future): Accumulate fragments; parse at end; same pass/fail outcomes.

## Decision Matrix (Behavior)
- Toggle Off × Any Provider × Any Schema → Normal text, no badges.
- Toggle On × Unsupported Provider × Any Schema → Normal text, warn once.
- Toggle On × Supported Provider × No Schema → Normal text.
- Toggle On × Supported Provider × Schema Selected → Structured path, with validation + fallbacks.

## Integration Points (Prep)
- Provider capability flag: base class + LM Studio Native implementation.
- Settings UI: checkbox for global toggle; persist in QSettings.
- Chat UI: schema dropdown in advanced options; per-message disable.
- Controller/Worker: extend payload with `structured_enabled` and `schema_id`; handle parsed vs raw.
- Schema registry: `core/llm/schemas.py` with starter schemas and provider allowlists.
- Tests: provider path, registry behavior, controller wiring, validation failures.

## Risks & Mitigations
- Invalid JSON from model: Use soft fallback; show warning; keep raw text; optional retry.
- Model variability: Keep schemas simple; add descriptive prompts nudging format adherence.
- Streaming parsing: Defer to Phase 4; buffer and parse after completion; show interim plain tokens.
- UI confusion: Clear badges and tooltips; default to None schema to avoid unexpected formatting.

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
