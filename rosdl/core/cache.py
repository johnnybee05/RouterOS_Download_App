"""Jednoduchá JSON cache s TTL v %APPDATA%\\RosDownloader\\.

Používá se pro seznam verzí (drahá enumerace přes CHANGELOG) a pro seznam
extra balíčků dané verze a architektury.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from threading import RLock
from typing import Any

APP_NAME = "RosDownloader"


def app_dir() -> Path:
    """Adresář s nastavením a cache. Na Windows ``%APPDATA%\\RosDownloader``."""
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / APP_NAME
    else:  # Linux/macOS – hlavně kvůli testům a CLI
        path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_atomic(path: Path, data: Any) -> None:
    """Zápis přes dočasný soubor, aby pád aplikace nenechal půlku JSONu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any | None:
    """Načte JSON; poškozený nebo chybějící soubor tiše ignoruje."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


class JsonCache:
    """Slovníková cache ukládaná do jednoho JSON souboru, s TTL na záznam."""

    def __init__(self, filename: str, ttl_seconds: float, directory: Path | None = None):
        self.path = (directory or app_dir()) / filename
        self.ttl = ttl_seconds
        self._lock = RLock()
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        raw = read_json(self.path)
        if isinstance(raw, dict):
            entries = raw.get("entries")
            if isinstance(entries, dict):
                self._data = {k: v for k, v in entries.items() if isinstance(v, dict)}
        self._loaded = True

    def get(self, key: str) -> Any | None:
        """Vrátí hodnotu, pokud existuje a nevypršela."""
        with self._lock:
            self._ensure_loaded()
            entry = self._data.get(key)
            if entry is None:
                return None
            saved_at = entry.get("saved_at", 0)
            if self.ttl > 0 and time.time() - saved_at > self.ttl:
                return None
            return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._ensure_loaded()
            self._data[key] = {"saved_at": time.time(), "value": value}
            self._flush()

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            self._ensure_loaded()
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)
            self._flush()

    def _flush(self) -> None:
        try:
            write_json_atomic(self.path, {"version": 1, "entries": self._data})
        except OSError:
            # Cache je optimalizace, ne kritická cesta – selhání zápisu nevadí.
            pass
