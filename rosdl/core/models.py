"""Datové typy sdílené celým jádrem. Bez závislosti na Qt."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from functools import total_ordering

# Architektury tak, jak je MikroTik reálně publikuje (ověřeno, viz docs/ENDPOINTS.md).
ARCHITECTURES: tuple[str, ...] = (
    "arm",
    "arm64",
    "mipsbe",
    "mmips",
    "smips",
    "ppc",
    "tile",
    "x86",
)

ARCH_LABELS: dict[str, str] = {
    "arm": "ARM (hAP ac², RB4011, CCR1009…)",
    "arm64": "ARM64 (CCR2004, hAP ax³, RB5009…)",
    "mipsbe": "MIPSBE (hEX, RB9xx, RB2011…)",
    "mmips": "MMIPS (hAP lite, hEX S, RB750Gr3…)",
    "smips": "SMIPS (hAP lite TC, mAP lite)",
    "ppc": "PowerPC (RB1100, RB800 – starší)",
    "tile": "Tile (CCR10xx, CCR11xx, CCR12xx)",
    "x86": "x86 / CHR (PC, virtuální stroje)",
}


class Channel(str, Enum):
    STABLE = "stable"
    LONG_TERM = "long-term"
    TESTING = "testing"
    DEVELOPMENT = "development"

    @property
    def label(self) -> str:
        return {
            Channel.STABLE: "Stable",
            Channel.LONG_TERM: "Long-term",
            Channel.TESTING: "Testing",
            Channel.DEVELOPMENT: "Development",
        }[self]


#: v6 publikuje jen stable a long-term. `NEWEST6.testing` sice vrací HTTP 200,
#: ale s obsahem `7.12.1` – zbytkem po v7. Viz docs/ENDPOINTS.md §2.
CHANNELS_BY_MAJOR: dict[int, tuple[Channel, ...]] = {
    7: (Channel.STABLE, Channel.LONG_TERM, Channel.TESTING, Channel.DEVELOPMENT),
    6: (Channel.STABLE, Channel.LONG_TERM),
}


class PackageKind(str, Enum):
    MAIN = "main"
    EXTRA = "extra"
    ARCHIVE = "archive"


_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?"
    r"(?:(?P<pre_kind>beta|rc)(?P<pre_num>\d+))?$"
)

#: Předrelease se řadí před finální verzi; beta před rc.
_PRE_ORDER = {"beta": 0, "rc": 1, None: 2}


@total_ordering
@dataclass(frozen=True)
class Version:
    """Verze RouterOS, např. ``7.24.4``, ``7.25beta5``, ``6.49.22``."""

    major: int
    minor: int
    patch: int | None = None
    pre_kind: str | None = None  # "beta" | "rc" | None
    pre_num: int | None = None

    @classmethod
    def parse(cls, text: str) -> Version:
        m = _VERSION_RE.match(text.strip())
        if not m:
            raise ValueError(f"Neplatný tvar verze: {text!r}")
        g = m.groupdict()
        return cls(
            major=int(g["major"]),
            minor=int(g["minor"]),
            patch=int(g["patch"]) if g["patch"] is not None else None,
            pre_kind=g["pre_kind"],
            pre_num=int(g["pre_num"]) if g["pre_num"] is not None else None,
        )

    @classmethod
    def try_parse(cls, text: str) -> Version | None:
        try:
            return cls.parse(text)
        except ValueError:
            return None

    def __str__(self) -> str:
        out = f"{self.major}.{self.minor}"
        if self.patch is not None:
            out += f".{self.patch}"
        if self.pre_kind is not None:
            out += f"{self.pre_kind}{self.pre_num}"
        return out

    @property
    def is_prerelease(self) -> bool:
        return self.pre_kind is not None

    def _key(self) -> tuple[int, int, int, int, int]:
        return (
            self.major,
            self.minor,
            self.patch or 0,
            _PRE_ORDER[self.pre_kind],
            self.pre_num or 0,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()


@dataclass(frozen=True)
class RemoteFile:
    """Jeden soubor ke stažení."""

    name: str
    url: str
    kind: PackageKind
    arch: str
    version: Version
    #: Velikost známá předem (ze ZIP Central Directory nebo z HEAD), jinak None.
    size: int | None = None
    #: Krátký název balíčku bez verze a architektury (``container``, ``routeros``…).
    package: str = ""

    @property
    def sha256_url(self) -> str:
        return self.url + ".sha256"


@dataclass(frozen=True)
class PackageEntry:
    """Extra balíček nalezený pro danou verzi a architekturu."""

    package: str
    arch: str
    filename: str
    size: int | None = None


@dataclass
class ArchPackages:
    """Výsledek zjišťování extras pro jednu architekturu."""

    arch: str
    version: Version
    entries: dict[str, PackageEntry] = field(default_factory=dict)
    #: "zip" = přečteno z all_packages archivu, "head" = záložní HEAD sondáž.
    source: str = "zip"

    @property
    def packages(self) -> list[str]:
        return sorted(self.entries)
