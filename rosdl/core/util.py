"""Drobné pomocné funkce bez závislostí."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

_UNITS = ("B", "kB", "MB", "GB", "TB")


def human_size(value: int | None) -> str:
    """``13934949`` -> ``13,3 MB``. Desetinná čárka, jak je zvykem v češtině."""
    if value is None:
        return "—"
    size = float(value)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024
    return f"{size:.1f} TB"


def human_speed(bytes_per_second: float) -> str:
    if bytes_per_second <= 0:
        return "—"
    return human_size(int(bytes_per_second)) + "/s"


def human_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds or seconds == float("inf"):
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} s"
    return f"{seconds // 3600} h {(seconds % 3600) // 60} min"


def sha256_file(
    path: Path,
    *,
    chunk_size: int = 1024 * 1024,
    should_cancel: Callable[[], bool] | None = None,
) -> str | None:
    """Spočítá SHA256 souboru. None = přerušeno zrušením."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            if should_cancel is not None and should_cancel():
                return None
            digest.update(chunk)
    return digest.hexdigest()


def plural(count: int, one: str, few: str, many: str) -> str:
    """České skloňování podle počtu: 1 soubor, 2 soubory, 5 souborů."""
    if count == 1:
        return f"{count} {one}"
    if 2 <= count <= 4:
        return f"{count} {few}"
    return f"{count} {many}"


def files_count(count: int) -> str:
    return plural(count, "soubor", "soubory", "souborů")


def packages_count(count: int) -> str:
    return plural(count, "balíček", "balíčky", "balíčků")


def versions_count(count: int) -> str:
    return plural(count, "verze", "verze", "verzí")
