"""Uživatelské nastavení v ``%APPDATA%\\RosDownloader\\settings.json``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .cache import app_dir, read_json, write_json_atomic
from .models import Channel

SETTINGS_FILE = "settings.json"
THEMES = ("system", "light", "dark")


def default_target_dir() -> str:
    return str(Path.home() / "Downloads" / "RouterOS")


@dataclass
class Settings:
    """Poslední volby uživatele. Neznámé klíče v souboru se ignorují."""

    major: int = 7
    channel: str = Channel.STABLE.value
    version: str = ""
    architectures: list[str] = field(default_factory=lambda: ["arm64"])
    include_main: bool = True
    extras: list[str] = field(default_factory=list)
    include_all_packages_zip: bool = False
    target_dir: str = field(default_factory=default_target_dir)
    subfolder_version: bool = True
    subfolder_arch: bool = True
    verify_sha256: bool = True
    theme: str = "system"
    window_geometry: str = ""
    #: Tichý dotaz na GitHub chvíli po startu, jestli nevyšla novější verze.
    check_updates_on_start: bool = True
    #: Verze, kterou uživatel odmítl – na tu se už sám neupozorňuje.
    skipped_update: str = ""

    # ------------------------------------------------------------------ #
    @classmethod
    def path(cls) -> Path:
        return app_dir() / SETTINGS_FILE

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        raw = read_json(path or cls.path())
        if not isinstance(raw, dict):
            return cls()
        known = {f.name: f for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for name, value in raw.items():
            spec = known.get(name)
            if spec is None:
                continue
            kwargs[name] = value
        settings = cls(**kwargs)
        settings.normalize()
        return settings

    def save(self, path: Path | None = None) -> None:
        self.normalize()
        write_json_atomic(path or self.path(), asdict(self))

    def normalize(self) -> None:
        """Opraví hodnoty, které mohly přijít z ručně upraveného souboru."""
        if self.major not in (6, 7):
            self.major = 7
        if self.channel not in {c.value for c in Channel}:
            self.channel = Channel.STABLE.value
        if self.theme not in THEMES:
            self.theme = "system"
        if not isinstance(self.architectures, list):
            self.architectures = ["arm64"]
        self.architectures = [a for a in self.architectures if isinstance(a, str)]
        if not isinstance(self.extras, list):
            self.extras = []
        self.extras = sorted({e for e in self.extras if isinstance(e, str)})
        if not self.target_dir:
            self.target_dir = default_target_dir()
        self.check_updates_on_start = bool(self.check_updates_on_start)
        if not isinstance(self.skipped_update, str):
            self.skipped_update = ""
