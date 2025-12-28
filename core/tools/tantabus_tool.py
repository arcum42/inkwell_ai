from typing import Any, Dict, List, Optional, Tuple

from .imageboard_base import ImageboardTool


class TantabusTool(ImageboardTool):
    @property
    def name(self) -> str:
        return "TANTABUS"

    @property
    def description(self) -> str:
        return "Search Tantabus for AI-generated pony images - ONLY use when user explicitly asks to FIND/SEARCH AI pony images: :::TOOL:TANTABUS:tag1, tag2, ...:::"

    BOARD_NAME = "TANTABUS"
    BOARD_SLUG = "tantabus"
    API_BASE = "https://tantabus.ai/api/v1/json"
    REQUIRES_KEY = False

    def has_dialog(self) -> bool:
        """This tool has a UI dialog for direct invocation."""
        return True
    
    def show_dialog(self, parent=None) -> Optional[Tuple[str, Optional[Any]]]:
        """Show search dialog for Tantabus."""
        try:
            from gui.dialogs.imageboard_search_dialog import ImageboardSearchDialog
            dialog = ImageboardSearchDialog(self.BOARD_NAME, parent)
            if dialog.exec():
                query = dialog.get_query()
                sort = dialog.get_sort()
                return (query, {"sort": sort})
        except Exception as e:
            print(f"Error showing Tantabus dialog: {e}")
        return None

    def get_configurable_settings(self) -> Dict[str, Any]:
        """Override base settings to add sort option."""
        settings = super().get_configurable_settings()
        settings["sort"] = {
            "default": "score",
            "type": "str",
            "description": "Sort results: score (highest rated), newest, oldest, random, trending"
        }
        return settings

    def search(self, query: str, max_results: int = 10, rating: str = "safe", use_api_key: bool = False, sort: str = "score", page: int = 1) -> Tuple[str, Optional[List[dict]]]:
        # Normalize tags and include rating unless 'all'
        tags = [t.strip() for t in query.replace(",", " ").split() if t.strip()]
        # Normalize artist directive similarly to Derpibooru
        normalized_tags: List[str] = []
        for t in tags:
            if t.lower().startswith("artist:"):
                name = t.split(":", 1)[1]
                slug = name.strip().replace(" ", "_")
                normalized_tags.append(f"artist:{slug}")
            else:
                normalized_tags.append(t)
        tags = normalized_tags
        if rating and rating.lower() != "all":
            tags.append(rating.lower())
        q = ", ".join(tags)

        params: Dict[str, Any] = {
            "q": q,
            "per_page": max(1, min(int(max_results), 50)),
            "page": max(1, int(page)),  # Use provided page number
            "sf": sort,  # Sort field: score, first_seen_at, wilson_score
            "sd": "desc",  # Sort direction: desc for descending (highest first)
        }
        api_key = self.get_stored_api_key() if use_api_key else None
        if api_key:
            params["key"] = api_key

        url = f"{self.API_BASE}/search/images"
        data = self._make_request(url, params)
        if not data or "images" not in data:
            return ("Unable to fetch images from Tantabus.", None)

        images = []
        for img in data.get("images", []):
            reps = img.get("representations") or {}
            full_url = reps.get("full") or img.get("view_url") or img.get("image")
            thumb_url = reps.get("thumb") or reps.get("thumb_small") or reps.get("small") or reps.get("medium")
            tags_list: List[str] = []
            # tantabus tags are typically a simple list of strings
            t = img.get("tags")
            if isinstance(t, list):
                for tag in t:
                    if isinstance(tag, str):
                        tags_list.append(tag)
            title = str(img.get("id") or img.get("name") or "image")
            source = None
            srcs = img.get("source_urls")
            if isinstance(srcs, list) and srcs:
                source = srcs[0]
            images.append({
                "id": img.get("id"),
                "url": full_url,
                "image": full_url,
                "thumbnail": thumb_url or full_url,
                "title": title,
                "description": img.get("description") or "",
                "tags": tags_list,
                "uploader": img.get("uploader") or "",
                "score": img.get("score") or 0,
                "upvotes": img.get("upvotes") or 0,
                "downvotes": img.get("downvotes") or 0,
                "created_at": img.get("created_at") or "",
                "source_url": source or "",
            })

        if not images:
            return ("No images found.", None)
        return (f"Found {len(images)} images. Asking user to select...", images)
