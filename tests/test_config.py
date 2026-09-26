"""Nastavení a JSON cache."""

from __future__ import annotations

import json
from pathlib import Path

from rosdl.core.cache import JsonCache
from rosdl.core.config import Settings


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings(
        major=6,
        channel="long-term",
        architectures=["arm", "x86"],
        extras=["container"],
        theme="dark",
    )
    settings.save(path)

    loaded = Settings.load(path)
    assert loaded.major == 6
    assert loaded.channel == "long-term"
    assert loaded.architectures == ["arm", "x86"]
    assert loaded.theme == "dark"


def test_defaults_when_file_missing(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "chybi.json")
    assert settings.major == 7
    assert settings.channel == "stable"
    assert settings.theme == "system"
    assert settings.include_main is True


def test_broken_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{tohle není JSON", encoding="utf-8")
    assert Settings.load(path).major == 7


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"major": 6, "neznamy_klic": 1}), encoding="utf-8")
    assert Settings.load(path).major == 6


def test_invalid_values_are_normalized(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "major": 5,
                "channel": "nesmysl",
                "theme": "duhovy",
                "architectures": "arm64",
                "extras": ["b", "a", "a"],
                "target_dir": "",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings.load(path)

    assert settings.major == 7
    assert settings.channel == "stable"
    assert settings.theme == "system"
    assert settings.architectures == ["arm64"]
    assert settings.extras == ["a", "b"]
    assert settings.target_dir


# --------------------------------------------------------------------------- #
def test_cache_stores_and_reads(tmp_path: Path) -> None:
    cache = JsonCache("c.json", ttl_seconds=3600, directory=tmp_path)
    cache.set("klic", {"a": 1})
    assert cache.get("klic") == {"a": 1}

    fresh = JsonCache("c.json", ttl_seconds=3600, directory=tmp_path)
    assert fresh.get("klic") == {"a": 1}


def test_cache_expires(tmp_path: Path) -> None:
    cache = JsonCache("c.json", ttl_seconds=0.0001, directory=tmp_path)
    cache.set("klic", 1)
    import time

    time.sleep(0.01)
    assert cache.get("klic") is None


def test_cache_invalidate(tmp_path: Path) -> None:
    cache = JsonCache("c.json", ttl_seconds=3600, directory=tmp_path)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == 2
    cache.invalidate()
    assert cache.get("b") is None


def test_cache_survives_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / "c.json").write_text("rozbito", encoding="utf-8")
    cache = JsonCache("c.json", ttl_seconds=3600, directory=tmp_path)
    assert cache.get("cokoliv") is None
    cache.set("a", 1)
    assert cache.get("a") == 1
