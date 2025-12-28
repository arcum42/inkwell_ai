"""Tools package providing individual tool implementations and registration.

This package splits the previous monolithic core/tools.py into separate modules.
It preserves the auto-registration behavior by registering default tools on import.
"""

from .web_reader import WebReader
from .web_search import WebSearcher
from .wikipedia_tool import WikiTool
from .image_search import ImageSearcher
from .image_gen_tool import ImageGenTool
from .imageboard_base import ImageboardTool
from .derpibooru_tool import DerpibooruTool
from .tantabus_tool import TantabusTool
from .e621_tool import E621Tool
from .registry import register_default_tools

__all__ = [
    "WebReader",
    "WebSearcher",
    "WikiTool",
    "ImageSearcher",
    "ImageGenTool",
    "ImageboardTool",
    "DerpibooruTool",
    "TantabusTool",
    "E621Tool",
    "register_default_tools",
]


# Preserve previous behavior: auto-register tools on package import
register_default_tools()
