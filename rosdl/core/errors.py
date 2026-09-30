"""Chyby jádra se srozumitelnými hláškami pro GUI i CLI.

Text se skládá v okamžiku vzniku výjimky, v jazyce, který tehdy platil.
Zprávy už zapsané v logu tak zůstanou tak, jak je uživatel viděl.
"""

from __future__ import annotations

from ..i18n import t


class RosdlError(Exception):
    """Základ pro všechny chyby aplikace."""


class NetworkError(RosdlError):
    """Síť selhala (timeout, DNS, TLS, přerušené spojení)."""


class NotFoundError(RosdlError):
    """HTTP 404 – požadovaný soubor na serveru není."""

    def __init__(self, url: str, message: str | None = None) -> None:
        self.url = url
        super().__init__(message or t("err.not_found", url=url))


class PackageNotAvailableError(NotFoundError):
    """404 na balíček – pro danou verzi nebo architekturu neexistuje."""

    def __init__(self, package: str, version: object, arch: str, url: str) -> None:
        self.package = package
        self.arch = arch
        super().__init__(
            url,
            t(
                "err.package_unavailable",
                package=package,
                version=version,
                arch=arch,
            ),
        )


class HttpError(RosdlError):
    """Jiná než 404 chybová HTTP odpověď."""

    def __init__(self, url: str, status: int) -> None:
        self.url = url
        self.status = status
        super().__init__(t("err.http_status", status=status, url=url))


class ChecksumMismatch(RosdlError):
    """Stažený soubor nesouhlasí s očekávaným SHA256."""

    def __init__(self, path: object, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            t("err.checksum_mismatch", path=path, expected=expected, actual=actual)
        )


class SizeMismatch(RosdlError):
    """Stažený soubor má jinou velikost, než server ohlásil."""

    def __init__(self, path: object, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            t("err.size_mismatch", path=path, expected=expected, actual=actual)
        )


class ZipIndexError(RosdlError):
    """Central Directory archivu se nepodařilo přečíst."""


class UpdateError(RosdlError):
    """Aktualizaci aplikace se nepodařilo zjistit, stáhnout nebo nasadit."""


class Cancelled(RosdlError):
    """Operaci zrušil uživatel."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or t("err.cancelled"))
