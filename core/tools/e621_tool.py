from typing import Any, Dict, List, Optional, Tuple

from .imageboard_base import ImageboardTool


class E621Tool(ImageboardTool):
    @property
    def name(self) -> str:
        return "E621"

    @property
    def description(self) -> str:
        return "Search E621 for furry content - ONLY use when user explicitly asks to FIND/SEARCH furry content: :::TOOL:E621:tag1, tag2, ...:::"

    BOARD_NAME = "E621"
    BOARD_SLUG = "e621"
    API_BASE = "https://e621.net"
    REQUIRES_KEY = True

    def has_dialog(self) -> bool:
        """This tool has a UI dialog for direct invocation."""
        return True
    
    def show_dialog(self, parent=None) -> Optional[Tuple[str, Optional[Any]]]:
        """Show search dialog for E621."""
        try:
            from gui.dialogs.imageboard_search_dialog import ImageboardSearchDialog
            dialog = ImageboardSearchDialog(self.BOARD_NAME, parent)
            if dialog.exec():
                query = dialog.get_query()
                sort = dialog.get_sort()
                return (query, {"sort": sort})
        except Exception as e:
            print(f"Error showing E621 dialog: {e}")
        return None

    def get_configurable_settings(self) -> Dict[str, Any]:
        """Override base settings to add sort option."""
        settings = super().get_configurable_settings()
        settings["sort"] = {
            "default": "score",
            "type": "str",
            "description": "Sort results: score (highest rated), newest, oldest, random, note_count"
        }
        return settings

    def search(self, query: str, max_results: int = 10, rating: str = "safe", use_api_key: bool = True, sort: str = "score", page: int = 1) -> Tuple[str, Optional[List[dict]]]:
        # e621 uses tags parameter; rating is specified as a tag: rating:s/q/e
        tags = [t.strip() for t in query.replace(",", " ").split() if t.strip()]
        # Normalize artist directive: artist:Name With Spaces -> artist:name_with_spaces
        normalized_tags: List[str] = []
        for t in tags:
            if t.lower().startswith("artist:"):
                name = t.split(":", 1)[1]
                slug = name.strip().lower().replace(" ", "_")
                normalized_tags.append(f"artist:{slug}")
            else:
                normalized_tags.append(t)
        tags = normalized_tags
        rating_tag = None
        if rating:
            r = rating.lower()
            if r in ("safe", "s"):
                rating_tag = "rating:s"
            elif r in ("questionable", "q"):
                rating_tag = "rating:q"
            elif r in ("explicit", "e"):
                rating_tag = "rating:e"
        if rating_tag:
            tags.append(rating_tag)
        tag_str = " ".join(tags)

        params: Dict[str, Any] = {
            "tags": tag_str,
            "page": max(1, int(page)),  # Use provided page number
            "limit": max(1, min(int(max_results), 320)),
            "order": sort,  # Add sort field (e621 calls it 'order')
        }

        # Auth: HTTP Basic (username, api_key) optional but recommended
        auth: Optional[Tuple[str, str]] = None
        if use_api_key:
            try:
                from PySide6.QtCore import QSettings
                s = QSettings("InkwellAI", "InkwellAI")
                user = (s.value("e621_username", "") or "").strip()
                key = (s.value("e621_api_key", "") or "").strip()
                if user and key:
                    auth = (user, key)
            except Exception:
                auth = None

        headers = {
            # e621 requires a descriptive User-Agent
            "User-Agent": "InkwellAI/1.0 (https://github.com/arcum42/inkwell_ai)"
        }

        url = f"{self.API_BASE}/posts.json"
        data = self._make_request(url, params, headers=headers, auth=auth)
        if not data or "posts" not in data:
            return ("Unable to fetch images from E621.", None)

        images: List[dict] = []
        for post in data.get("posts", []):
            file = post.get("file") or {}
            preview = post.get("preview") or {}
            sample = post.get("sample") or {}
            full_url = file.get("url") or sample.get("url")
            thumb_url = preview.get("url") or sample.get("url") or full_url

            # tags grouped by category; flatten
            tags_list: List[str] = []
            tags_obj = post.get("tags") or {}
            for cat, vals in tags_obj.items():
                if isinstance(vals, list):
                    for t in vals:
                        if isinstance(t, str):
                            tags_list.append(t)

            score_obj = post.get("score") or {}
            up = int(score_obj.get("up") or 0)
            down = int(score_obj.get("down") or 0)
            total = int(score_obj.get("total") or (up - down))

            srcs = post.get("sources") or []
            source_url = srcs[0] if srcs else ""

            images.append({
                "id": post.get("id"),
                "url": full_url,
                "image": full_url,
                "thumbnail": thumb_url or full_url,
                "title": str(post.get("id") or "image"),
                "description": "",
                "tags": tags_list,
                "uploader": "",
                "score": total,
                "upvotes": up,
                "downvotes": down,
                "created_at": post.get("created_at") or "",
                "source_url": source_url,
            })

        if not images:
            return ("No images found.", None)
        return (f"Found {len(images)} images. Asking user to select...", images)
