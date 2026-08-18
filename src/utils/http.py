"""Shared HTTP download helper with on-disk caching.

CVM's RAD system serves large files and can be picky about clients; a
plain browser-like User-Agent via urllib has proven reliable, so we
standardize on it here instead of adding a requests dependency.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (compatible; thesis-data-acquisition/1.0)"


def get_bytes(
    url: str,
    cache_path: Path | None = None,
    force: bool = False,
    timeout: int = 120,
    retries: int = 3,
    retry_wait: float = 5.0,
    validate: "callable | None" = None,
) -> bytes:
    """Download ``url`` and return its bytes, optionally caching to ``cache_path``.

    ``validate(data) -> bool`` can reject a malformed response (e.g. an
    upstream server returning a transient text error instead of the
    expected file) so it is retried instead of cached and trusted.
    """
    if cache_path is not None and cache_path.exists() and not force:
        return cache_path.read_bytes()

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            if validate is not None and not validate(data):
                raise ValueError(f"Response failed validation (attempt {attempt}/{retries}): {data[:200]!r}")
            break
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_error = exc
            if attempt < retries:
                time.sleep(retry_wait)
    else:
        raise RuntimeError(f"Failed to download {url} after {retries} attempts") from last_error

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(data)

    return data
