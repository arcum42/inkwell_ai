from typing import Any, Dict, List, Optional, Tuple

import requests

from core.tool_base import Tool


class ImageboardTool(Tool):
    """Base class for imageboard-style image search tools.

    Subclasses must implement `search()` to call their API and normalize
    responses to the common image result format used by the app.
    """

    BOARD_NAME = "imageboard"
    BOARD_SLUG = "imageboard"
    API_BASE = ""
    REQUIRES_KEY = False

    @property
    def requires_libraries(self) -> list:
        return ["requests"]

    def get_configurable_settings(self) -> Dict[str, Any]:
        return {
            "max_images": {"default": 10, "type": "int", "description": "Maximum images to return (1-50)"},
            "rating": {
                "default": "safe",
                "type": "str",
                "description": "Content rating filter: safe, questionable, explicit, all",
            },
            "use_api_key": {
                "default": False,
                "type": "bool",
                "description": "Use stored API key for higher rate limits",
            },
            "artist": {
                "default": "",
                "type": "str",
                "description": "Optional artist name filter (e.g., artist:john_doe)",
            },
        }

    def execute(self, query: str, settings: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[Any]]:
        max_images = self.get_default_max_images()
        rating = self.get_default_rating()
        use_api_key = False
        extra_settings = {}

        if settings:
            max_images = int(settings.get("max_images", max_images))
            rating = settings.get("rating", rating)
            use_api_key = bool(settings.get("use_api_key", use_api_key))
            artist = (settings.get("artist") or "").strip()
            # Pass any other settings through to subclass
            extra_settings = {k: v for k, v in settings.items() 
                            if k not in ("max_images", "rating", "use_api_key", "artist")}
        else:
            artist = ""

        # If artist setting provided, append a directive to the query
        if artist:
            # Avoid duplicating if already present in query
            directive = f"artist:{artist}"
            if directive not in query:
                query = f"{query} {directive}".strip()

        return self.search(query, max_results=max_images, rating=rating, use_api_key=use_api_key, **extra_settings)

    def get_stored_api_key(self) -> Optional[str]:
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("InkwellAI", "InkwellAI")
            key_name = f"{self.BOARD_SLUG}_api_key"
            key = (settings.value(key_name, "") or "").strip()
            return key if key else None
        except Exception:
            return None

    def get_default_rating(self) -> str:
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("InkwellAI", "InkwellAI")
            key_name = f"{self.BOARD_SLUG}_default_rating"
            val = settings.value(key_name, "safe")
            return val if isinstance(val, str) else "safe"
        except Exception:
            return "safe"

    def get_default_max_images(self) -> int:
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("InkwellAI", "InkwellAI")
            key_name = f"{self.BOARD_SLUG}_max_images"
            val = settings.value(key_name, 10)
            try:
                iv = int(val) if not isinstance(val, int) else val
            except Exception:
                iv = 10
            return max(1, iv)
        except Exception:
            return 10

    def _make_request(self, url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None,
                      auth: Optional[Tuple[str, str]] = None) -> Optional[Dict[str, Any]]:
        try:
            print(f"DEBUG [{self.BOARD_NAME}]: Making request to {url}")
            print(f"DEBUG [{self.BOARD_NAME}]: Params: {params}")
            print(f"DEBUG [{self.BOARD_NAME}]: Headers: {headers}")
            print(f"DEBUG [{self.BOARD_NAME}]: Auth provided: {auth is not None}")
            resp = requests.get(url, params=params, headers=headers or {}, timeout=15, auth=auth)
            print(f"DEBUG [{self.BOARD_NAME}]: Response status: {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                print(f"DEBUG [{self.BOARD_NAME}]: Response has keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
                return result
            else:
                print(f"DEBUG [{self.BOARD_NAME}]: Non-200 response: {resp.status_code}")
                print(f"DEBUG [{self.BOARD_NAME}]: Response text: {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"DEBUG [{self.BOARD_NAME}]: Exception during request: {e}")
            import traceback
            traceback.print_exc()
            return None

    def search(self, query: str, max_results: int = 10, rating: str = "safe", use_api_key: bool = False) -> Tuple[str, Optional[List[dict]]]:
        """Subclasses must implement actual search logic.

        Return (result_text, image_results or None).
        """
        raise NotImplementedError()
