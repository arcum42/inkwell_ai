"""Base interfaces for provider-backed model listings.

Provides a thin abstraction around provider-specific model metadata and
optional lifecycle operations (load/unload).
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ProviderModel:
    """Normalized model metadata returned by provider sources."""

    provider: str
    name: str
    display_name: Optional[str] = None
    is_loaded: Optional[bool] = None
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    supports_structured_output: Optional[bool] = None
    base_model: Optional[str] = None
    context_length: Optional[int] = None
    raw_metadata: dict = field(default_factory=dict)


class ProviderModelSource:
    """Interface for provider-specific model enumeration and lifecycle actions."""

    provider_name: str = ""
    supports_load_unload: bool = False

    def list_models(self, refresh: bool = False) -> List[ProviderModel]:  # pragma: no cover - interface
        raise NotImplementedError

    def load_model(self, model_name: str) -> Tuple[bool, Optional[str]]:
        """Attempt to load the given model into memory.

        Returns:
            (success, message) tuple. message is optional context for UI.
        """
        return False, "Load not supported for this provider"

    def unload_model(self, model_name: str) -> Tuple[bool, Optional[str]]:
        """Attempt to unload the given model from memory.

        Returns:
            (success, message) tuple. message is optional context for UI.
        """
        return False, "Unload not supported for this provider"
