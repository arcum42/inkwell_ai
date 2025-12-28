"""Model Manager core logic.

Aggregates models across providers, manages favorites/notes, and exposes
optional lifecycle helpers (load/unload) for providers that support them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

try:  # Optional; allows running without Qt in headless contexts
    from PySide6.QtCore import QSettings
except Exception:  # pragma: no cover - optional dependency
    QSettings = None  # type: ignore

from core.model_sources import (
    ProviderModel,
    ProviderModelSource,
    OllamaModelSource,
    LMStudioNativeModelSource,
)


@dataclass
class ModelSettings:
    """Per-model generation defaults (future-facing)."""

    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    last_used: Optional[str] = None  # ISO timestamp as string to keep storage simple
    hide_structured_output_json: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "last_used": self.last_used,
            "hide_structured_output_json": self.hide_structured_output_json,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ModelSettings":
        if not data:
            return cls()
        return cls(
            system_prompt=data.get("system_prompt"),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p"),
            top_k=data.get("top_k"),
            presence_penalty=data.get("presence_penalty"),
            frequency_penalty=data.get("frequency_penalty"),
            last_used=data.get("last_used"),
            hide_structured_output_json=data.get("hide_structured_output_json", True),
        )


@dataclass
class ModelInfo:
    provider: str
    name: str
    display_name: Optional[str] = None
    is_loaded: Optional[bool] = None
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    supports_structured_output: Optional[bool] = None
    base_model: Optional[str] = None
    context_length: Optional[int] = None
    tags: Set[str] = field(default_factory=set)
    note: Optional[str] = None
    raw_metadata: dict = field(default_factory=dict)
    settings: Optional[ModelSettings] = None

    def to_export_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "name": self.name,
            "favorite": "favorite" in self.tags,
            "note": self.note,
            "settings": self.settings.to_dict() if self.settings else {},
        }


class ModelPreferenceStore:
    """Persistence helper for favorites/notes/settings.

    Uses QSettings when provided; otherwise falls back to in-memory storage for tests.
    """

    def __init__(self, settings=None):
        # settings should be Optional[QSettings] but we accept None to handle import failures
        self.settings = settings if QSettings and isinstance(settings, QSettings) else None
        self._memory: Dict[str, Any] = {}

    def get_favorite(self, provider: str, model: str) -> bool:
        key = self._full_key(provider, model, "favorite")
        if self.settings:
            return bool(self.settings.value(key, False, type=bool))
        return bool(self._memory.get(key, False))

    def set_favorite(self, provider: str, model: str, value: bool) -> None:
        key = self._full_key(provider, model, "favorite")
        if self.settings:
            self.settings.setValue(key, value)
        else:
            self._memory[key] = value

    def get_note(self, provider: str, model: str) -> str:
        key = self._full_key(provider, model, "note")
        if self.settings:
            value = self.settings.value(key, "")
            return str(value) if value else ""
        return str(self._memory.get(key, ""))

    def set_note(self, provider: str, model: str, note: str) -> None:
        key = self._full_key(provider, model, "note")
        if self.settings:
            self.settings.setValue(key, note)
        else:
            self._memory[key] = note

    def get_settings(self, provider: str, model: str) -> ModelSettings:
        key = self._full_key(provider, model, "settings")
        if self.settings:
            raw = self.settings.value(key)
        else:
            raw = self._memory.get(key)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = None
        return ModelSettings.from_dict(data if isinstance(data, dict) else None)

    def set_settings(self, provider: str, model: str, settings: ModelSettings) -> None:
        key = self._full_key(provider, model, "settings")
        serialized = json.dumps(settings.to_dict())
        if self.settings:
            self.settings.setValue(key, serialized)
        else:
            self._memory[key] = serialized

    def reset_settings(self, provider: str, model: str) -> None:
        prefix = self._full_key(provider, model, "")
        if self.settings:
            self.settings.remove(prefix)
        else:
            for k in list(self._memory.keys()):
                if k.startswith(prefix):
                    self._memory.pop(k, None)

    def iter_entries(self) -> List[Dict[str, Any]]:
        """Return stored favorites/notes/settings for export."""
        records: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if self.settings:
            for key in self.settings.allKeys():
                if not key.startswith("model_manager/"):
                    continue
                parts = key.split("/")
                if len(parts) < 4:
                    continue
                _, provider, model, *rest = parts
                if not rest:
                    continue
                record = records.setdefault((provider, model), {"provider": provider, "name": model, "favorite": False, "note": "", "settings": {}})
                leaf = rest[-1]
                val = self.settings.value(key)
                if leaf == "favorite":
                    record["favorite"] = bool(val)
                elif leaf == "note":
                    record["note"] = val or ""
                elif rest[0] == "settings":
                    try:
                        as_dict = json.loads(val) if isinstance(val, str) else val
                        if isinstance(as_dict, dict):
                            record["settings"].update(as_dict)
                    except Exception:
                        pass
        else:
            for key, val in self._memory.items():
                if not key.startswith("model_manager/"):
                    continue
                parts = key.split("/")
                if len(parts) < 4:
                    continue
                _, provider, model, *rest = parts
                record = records.setdefault((provider, model), {"provider": provider, "name": model, "favorite": False, "note": "", "settings": {}})
                leaf = rest[-1]
                if leaf == "favorite":
                    record["favorite"] = bool(val)
                elif leaf == "note":
                    record["note"] = str(val)
                elif rest[0] == "settings":
                    try:
                        as_dict = json.loads(val) if isinstance(val, str) else val
                        if isinstance(as_dict, dict):
                            record["settings"].update(as_dict)
                    except Exception:
                        pass
        return list(records.values())

    def import_entries(self, entries: List[Dict[str, Any]], merge_strategy: str = "skip_existing") -> None:
        """Import favorites/notes/settings from exported data.

        merge_strategy: "skip_existing" (default) keeps current values, "overwrite" replaces them.
        """
        for entry in entries:
            provider = entry.get("provider")
            model = entry.get("name")
            if not provider or not model:
                continue
            existing_has_fav = self.get_favorite(provider, model)
            existing_note = self.get_note(provider, model)
            if merge_strategy == "skip_existing" and (existing_has_fav or existing_note):
                continue
            self.set_favorite(provider, model, bool(entry.get("favorite")))
            self.set_note(provider, model, entry.get("note", ""))
            settings = ModelSettings.from_dict(entry.get("settings") or {})
            self.set_settings(provider, model, settings)

    @staticmethod
    def _full_key(provider: str, model: str, leaf: str) -> str:
        if leaf:
            return f"model_manager/{provider}/{model}/{leaf}"
        return f"model_manager/{provider}/{model}"


class ModelManager:
    """Aggregates models across providers and manages local preferences."""

    EXPORT_VERSION = 1

    def __init__(self, sources: List[ProviderModelSource], prefs: Optional[ModelPreferenceStore] = None):
        self.sources = sources
        self.prefs = prefs or ModelPreferenceStore()
        self._source_map = {s.provider_name: s for s in sources}

    def list_models(self, refresh: bool = False) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        for source in self.sources:
            try:
                provider_models = source.list_models(refresh=refresh)
            except Exception as exc:
                print(f"Error listing models for provider {source.provider_name}: {exc}")
                provider_models = []
            for pm in provider_models:
                favorite = self.prefs.get_favorite(pm.provider, pm.name)
                note = self.prefs.get_note(pm.provider, pm.name)
                settings = self.prefs.get_settings(pm.provider, pm.name)
                tags: Set[str] = set()
                if favorite:
                    tags.add("favorite")
                models.append(
                    ModelInfo(
                        provider=pm.provider,
                        name=pm.name,
                        display_name=pm.display_name or pm.name,
                        is_loaded=pm.is_loaded,
                        supports_vision=pm.supports_vision,
                        supports_tools=pm.supports_tools,
                        supports_structured_output=pm.supports_structured_output,
                        base_model=pm.base_model,
                        context_length=pm.context_length,
                        tags=tags,
                        note=note,
                        raw_metadata=pm.raw_metadata,
                        settings=settings,
                    )
                )
        return models

    def set_favorite(self, provider: str, model: str, value: bool) -> None:
        self.prefs.set_favorite(provider, model, value)

    def set_note(self, provider: str, model: str, note: str) -> None:
        self.prefs.set_note(provider, model, note)

    def get_settings(self, provider: str, model: str) -> ModelSettings:
        return self.prefs.get_settings(provider, model)

    def set_settings(self, provider: str, model: str, settings: ModelSettings) -> None:
        self.prefs.set_settings(provider, model, settings)

    def reset_settings(self, provider: str, model: str) -> None:
        self.prefs.reset_settings(provider, model)

    def load_model(self, provider: str, model: str) -> Tuple[bool, Optional[str]]:
        source = self._source_map.get(provider)
        if not source:
            return False, "Unknown provider"
        if not source.supports_load_unload:
            return False, "Load/unload not supported for this provider"
        return source.load_model(model)

    def unload_model(self, provider: str, model: str) -> Tuple[bool, Optional[str]]:
        source = self._source_map.get(provider)
        if not source:
            return False, "Unknown provider"
        if not source.supports_load_unload:
            return False, "Load/unload not supported for this provider"
        return source.unload_model(model)

    def export_preferences(self, file_path: str) -> None:
        payload = {
            "version": self.EXPORT_VERSION,
            "entries": self.prefs.iter_entries(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def import_preferences(self, file_path: str, merge_strategy: str = "skip_existing") -> None:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return
        entries = payload.get("entries", []) if payload.get("version") == self.EXPORT_VERSION else payload.get("entries", [])
        if isinstance(entries, list):
            self.prefs.import_entries(entries, merge_strategy=merge_strategy)


def build_default_sources(settings=None) -> List[ProviderModelSource]:
    """Helper to build provider sources using app settings values."""
    ollama_url: Optional[str] = None
    lm_studio_native_url: Optional[str] = None
    if settings and QSettings and isinstance(settings, QSettings):
        ollama_url = str(settings.value("ollama_url", "http://localhost:11434")) or "http://localhost:11434"
        lm_studio_native_url = str(settings.value("lm_studio_native_url", "localhost:1234")) or "localhost:1234"

    sources: List[ProviderModelSource] = [
        OllamaModelSource(base_url=ollama_url or "http://localhost:11434"),
        LMStudioNativeModelSource(base_url=lm_studio_native_url or "localhost:1234"),
    ]
    return sources
