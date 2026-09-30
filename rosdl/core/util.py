"""Drobné pomocné funkce bez závislostí."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from ..i18n import decimal_separator, t, tn

_UNITS = ("B", "kB", "MB", "GB", "TB")


def human_size(value: int | None) -> str:
    """``13934949`` -> ``13,3 MB``.

    Oddělovač desetin se bere z jazyka: čeština píše čárku, angličtina tečku.
    """
    if value is None:
        return t("format.unknown")
    size = float(value)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            if unit == "B":
                return t("format.size_bytes", n=int(size))
            return f"{size:.1f} {unit}".replace(".", decimal_separator())
        size /= 1024
    return f"{size:.1f} TB".replace(".", decimal_separator())


def human_speed(bytes_per_second: float) -> str:
    if bytes_per_second <= 0:
        return t("format.unknown")
    return human_size(int(bytes_per_second)) + "/s"


def human_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds or seconds == float("inf"):
        return t("format.unknown")
    seconds = int(seconds)
    if seconds < 60:
        return t("format.duration_s", s=seconds)
    if seconds < 3600:
        return t("format.duration_ms", m=seconds // 60, s=seconds % 60)
    return t("format.duration_hm", h=seconds // 3600, m=(seconds % 3600) // 60)


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


def files_count(count: int) -> str:
    return tn("count.files", count)


def packages_count(count: int) -> str:
    return tn("count.packages", count)


def versions_count(count: int) -> str:
    return tn("count.versions", count)


def architectures_count(count: int) -> str:
    return tn("count.architectures", count)
