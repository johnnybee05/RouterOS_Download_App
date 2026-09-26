"""Chyby jádra se srozumitelnými českými hláškami pro GUI i CLI."""

from __future__ import annotations


class RosdlError(Exception):
    """Základ pro všechny chyby aplikace."""


class NetworkError(RosdlError):
    """Síť selhala (timeout, DNS, TLS, přerušené spojení)."""


class NotFoundError(RosdlError):
    """HTTP 404 – požadovaný soubor na serveru není."""

    def __init__(self, url: str, message: str | None = None) -> None:
        self.url = url
        super().__init__(message or f"Soubor nenalezen (404): {url}")


class PackageNotAvailableError(NotFoundError):
    """404 na balíček – pro danou verzi nebo architekturu neexistuje."""

    def __init__(self, package: str, version: object, arch: str, url: str) -> None:
        self.package = package
        self.arch = arch
        super().__init__(
            url,
            f"Balíček „{package}“ pro verzi {version} a architekturu {arch} neexistuje.",
        )


class HttpError(RosdlError):
    """Jiná než 404 chybová HTTP odpověď."""

    def __init__(self, url: str, status: int) -> None:
        self.url = url
        self.status = status
        super().__init__(f"Server odpověděl {status}: {url}")


class ChecksumMismatch(RosdlError):
    """Stažený soubor nesouhlasí s očekávaným SHA256."""

    def __init__(self, path: object, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Kontrolní součet nesouhlasí u {path}:\n"
            f"  očekáváno {expected}\n  spočteno  {actual}"
        )


class SizeMismatch(RosdlError):
    """Stažený soubor má jinou velikost, než server ohlásil."""

    def __init__(self, path: object, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Velikost nesouhlasí u {path}: očekáváno {expected} B, staženo {actual} B."
        )


class ZipIndexError(RosdlError):
    """Central Directory archivu se nepodařilo přečíst."""


class Cancelled(RosdlError):
    """Operaci zrušil uživatel."""
