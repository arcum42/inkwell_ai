"""Shared utilities for tool implementations."""

from typing import Optional, List


def _import_ddgs():
    """Import a DDG search implementation and return a DDGS class or None.
    Tries `ddgs` first (fast), then `duckduckgo_search`.
    """
    try:
        from ddgs import DDGS as _DDGS  # type: ignore
        return _DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS as _DDGS  # type: ignore
            return _DDGS
        except Exception:
            return None


def ddg_available() -> bool:
    """Return True if a DDG search backend is importable."""
    return _import_ddgs() is not None


def ddg_text(query: str, max_results: int = 5) -> Optional[List[dict]]:
    """Run a DuckDuckGo text search and return results list or None on error."""
    DDGS = _import_ddgs()
    if DDGS is None:
        return None
    try:
        return DDGS().text(query, max_results=max_results)
    except Exception:
        return None


def ddg_images(query: str, max_results: int = 10) -> Optional[List[dict]]:
    """Run a DuckDuckGo image search and return results list or None on error."""
    DDGS = _import_ddgs()
    if DDGS is None:
        return None
    try:
        return DDGS().images(query, max_results=max_results)
    except Exception:
        return None


# --- HTML fetching/cleaning helpers ---

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)


def read_and_clean_url(url: str, max_length: int = 10000, timeout: int = 10) -> str:
    """Fetch a web page and return cleaned text up to max_length characters.

    This uses requests + BeautifulSoup internally and catches all exceptions,
    returning an error string on failure.
    """
    try:
        import requests  # local import to avoid hard dependency if unused
        import bs4  # type: ignore

        headers = {"User-Agent": _USER_AGENT}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text[:max_length]
    except Exception as e:
        return f"Error reading URL: {e}"