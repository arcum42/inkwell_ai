"""LM Studio Native SDK model source."""

from __future__ import annotations

from typing import List, Optional, Tuple
import requests
import lmstudio as lms

from core.llm import LMStudioNativeProvider
from .base import ProviderModel, ProviderModelSource


class LMStudioNativeModelSource(ProviderModelSource):
    provider_name = "LM Studio (Native SDK)"
    supports_load_unload = True

    def __init__(self, base_url: str = "localhost:1234"):
        # SDK expects host:port without scheme; REST endpoints need scheme
        self.base_url = base_url.rstrip("/")
        self.provider = LMStudioNativeProvider(base_url=self.base_url)

    def list_models(self, refresh: bool = False) -> List[ProviderModel]:
        models: List[ProviderModel] = []
        try:
            loaded = set(self.provider.get_loaded_models(refresh=refresh) or [])
        except Exception:
            loaded = set()

        try:
            # Use native SDK list_downloaded_models() instead of REST API
            downloaded = lms.list_downloaded_models()
            
            for model in downloaded:
                # Access the _data attribute which contains all model metadata
                data = getattr(model, "_data", None)
                if data is None:
                    continue
                
                # Extract model identifier
                model_key = getattr(data, "model_key", "")
                model_path = getattr(data, "path", "")
                model_id = model_key or model_path.split("/")[-1]
                
                if not model_id:
                    continue
                
                # Get official vision and tools fields (Phase 3 enhancement)
                supports_vision = bool(getattr(data, "vision", False))
                supports_tools = bool(getattr(data, "trained_for_tool_use", False))
                
                # Structured output support: heuristic based on model size
                # Most models >1B support structured output; SDK doesn't expose this explicitly yet
                supports_structured_output = self._detect_supports_structured_output(
                    getattr(data, "params_string", None)
                )
                
                # Get other metadata
                display_name = getattr(data, "display_name", model_id)
                context_len = getattr(data, "max_context_length", None)
                architecture = getattr(data, "architecture", None)
                params = getattr(data, "params_string", None)
                
                # Check if model is loaded
                is_loaded = model_id in loaded or model_key in loaded
                
                models.append(
                    ProviderModel(
                        provider=self.provider_name,
                        name=model_id,
                        display_name=display_name,
                        is_loaded=is_loaded,
                        supports_vision=supports_vision,
                        supports_tools=supports_tools,
                        supports_structured_output=supports_structured_output,
                        base_model=architecture,  # Use architecture as base_model
                        context_length=context_len,
                        raw_metadata={
                            "model_key": model_key,
                            "path": model_path,
                            "architecture": architecture,
                            "params": params,
                            "format": getattr(data, "format", None),
                            "size_bytes": getattr(data, "size_bytes", None),
                        },
                    )
                )
        except Exception as exc:
            print(f"Error listing LM Studio native models: {exc}")
            import traceback
            traceback.print_exc()
        return models

    def load_model(self, model_name: str) -> Tuple[bool, Optional[str]]:
        try:
            # lms.llm(model_name) will load if not loaded already
            lms.llm(model_name)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def unload_model(self, model_name: str) -> Tuple[bool, Optional[str]]:
        try:
            handle = lms.llm(model_name)
            if hasattr(handle, "unload"):
                handle.unload()
                return True, None
            return False, "Unload not supported by LM Studio SDK version"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _parse_capability(capabilities, key: str) -> Optional[bool]:
        if capabilities is None:
            return None
        if isinstance(capabilities, list):
            return any(str(c).lower() == key for c in capabilities)
        if isinstance(capabilities, dict):
            if key in capabilities:
                return bool(capabilities.get(key))
            return None
        return None

    @staticmethod
    def _parse_loaded(entry: dict) -> Optional[bool]:
        for k in ("loaded", "isLoaded", "is_loaded", "default", "isDefault"):
            if k in entry:
                try:
                    return bool(entry.get(k))
                except Exception:
                    return None
        state = str(entry.get("state") or entry.get("status") or "").lower()
        if state in {"loaded", "ready", "active", "running"}:
            return True
        if state in {"unloaded", "idle", "stopped"}:
            return False
        return None

    @staticmethod
    def _get_model_id(entry: dict) -> Optional[str]:
        if not isinstance(entry, dict):
            return None
        return entry.get("id") or entry.get("model") or entry.get("name")

    @staticmethod
    def _normalize_url(base_url: str) -> str:
        if base_url.startswith("http://") or base_url.startswith("https://"):
            return base_url.rstrip("/")
        return f"http://{base_url}"

    @staticmethod
    def _detect_supports_structured_output(params_string: Optional[str]) -> Optional[bool]:
        """Detect if model likely supports structured output based on parameter size.
        
        Most models >1B parameters support structured output in LM Studio.
        SDK doesn't expose this capability explicitly yet.
        
        Args:
            params_string: Parameter count string like "7B", "70B", etc.
            
        Returns:
            True if model likely supports structured output (>1B)
            False if model is very small
            None if uncertain
        """
        if not params_string:
            return None
        
        params_lower = str(params_string).lower()
        
        try:
            # Parse strings like "7B", "70B", "1.5B"
            param_b = float(params_lower.replace('b', '').strip())
            # Heuristic: models with <0.5B are too small for reliable structured output
            if param_b < 0.5:
                return False
            # Models with >1B generally support it well
            return param_b >= 1.0
        except Exception:
            return None
