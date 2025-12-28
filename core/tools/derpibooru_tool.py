from typing import Any, Dict, List, Optional, Tuple

from .imageboard_base import ImageboardTool


class DerpibooruTool(ImageboardTool):
    @property
    def name(self) -> str:
        return "DERPIBOORU"

    @property
    def description(self) -> str:
        return "Search Derpibooru for hand-drawn/non-AI pony images - ONLY use when user explicitly asks to FIND/SEARCH pony images: :::TOOL:DERPIBOORU:tag1, tag2, ...:::"

    BOARD_NAME = "DERPIBOORU"
    BOARD_SLUG = "derpibooru"
    API_BASE = "https://derpibooru.org/api/v1/json"
    REQUIRES_KEY = False

    def has_dialog(self) -> bool:
        """This tool has a UI dialog for direct invocation."""
        return True
    
    def show_dialog(self, parent=None) -> Optional[Tuple[str, Optional[Any]]]:
        """Show search dialog for Derpibooru."""
        try:
            from gui.dialogs.imageboard_search_dialog import ImageboardSearchDialog
            dialog = ImageboardSearchDialog(self.BOARD_NAME, parent)
            if dialog.exec():
                query = dialog.get_query()
                sort = dialog.get_sort()
                # Return the query with sort hint (will be used as settings)
                return (query, {"sort": sort})
        except Exception as e:
            print(f"Error showing Derpibooru dialog: {e}")
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
        print(f"DEBUG [DERPIBOORU]: Searching for query='{query}', max_results={max_results}, rating='{rating}', sort='{sort}', page={page}")
        # Normalize query: commas or spaces; append rating unless 'all'
        tags = [t.strip() for t in query.replace(",", " ").split() if t.strip()]
        # Philomena sites accept artist:uploader tags; keep 'artist:' token as-is
        # Normalize spaces in artist names to underscores for better matching
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
        print(f"DEBUG [DERPIBOORU]: Final query tags: {q}")

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
        print(f"DEBUG [DERPIBOORU]: Calling API at {url}")
        data = self._make_request(url, params)
        print(f"DEBUG [DERPIBOORU]: API returned: {data is not None}, has 'images' key: {'images' in data if data else False}")
        if not data or "images" not in data:
            return ("Unable to fetch images from Derpibooru.", None)

        images = []
        for img in data.get("images", []):
            # Derpibooru may use 'representation' (singular) on older APIs; philomena uses 'representations'
            reps = img.get("representations") or img.get("representation") or {}
            full_url = reps.get("full") or img.get("view_url") or img.get("image")
            thumb_url = reps.get("thumb") or reps.get("thumb_small") or reps.get("small") or reps.get("medium")
            tags_list: List[str] = []
            if isinstance(img.get("tags"), list):
                # Could be list of strings or dicts with 'name'
                for t in img["tags"]:
                    if isinstance(t, str):
                        tags_list.append(t)
                    elif isinstance(t, dict) and "name" in t:
                        tags_list.append(t["name"]) 
            title = str(img.get("id") or img.get("name") or "image")
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
                "source_url": img.get("source_url") or (img.get("source_urls") or [""])[0],
            })

        if not images:
            return ("No images found.", None)
        return (f"Found {len(images)} images. Asking user to select...", images)
