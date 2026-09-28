"""Parsování a řazení verzí + odpovědí NEWEST."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from rosdl.core.client import (
    parse_changelog_date,
    parse_newest,
    parse_sha256_sidecar,
)
from rosdl.core.errors import RosdlError
from rosdl.core.models import Version


# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("7.24.4", (7, 24, 4, None, None)),
        ("7.16", (7, 16, None, None, None)),
        ("6.49.22", (6, 49, 22, None, None)),
        ("7.25beta5", (7, 25, None, "beta", 5)),
        ("7.24rc1", (7, 24, None, "rc", 1)),
        ("  7.24.4  ", (7, 24, 4, None, None)),
    ],
)
def test_version_parse(text: str, parts: tuple) -> None:
    v = Version.parse(text)
    assert (v.major, v.minor, v.patch, v.pre_kind, v.pre_num) == parts


@pytest.mark.parametrize(
    "text", ["", "7", "7.", "x.y", "7.24.4.1", "7.24alpha1", "7.24beta", "7,24"]
)
def test_version_parse_rejects_garbage(text: str) -> None:
    assert Version.try_parse(text) is None
    with pytest.raises(ValueError):
        Version.parse(text)


@pytest.mark.parametrize(
    "text", ["7.24.4", "7.16", "7.25beta5", "7.24rc1", "6.49.22", "6.0"]
)
def test_version_str_roundtrip(text: str) -> None:
    assert str(Version.parse(text)) == text


def test_version_ordering() -> None:
    order = [
        "6.49.22",
        "7.1",
        "7.1.5",
        "7.9",
        "7.10",
        "7.24beta1",
        "7.24rc1",
        "7.24",
        "7.24.1",
        "7.24.4",
        "7.25beta3",
        "7.25beta5",
        "7.25",
    ]
    versions = [Version.parse(t) for t in order]
    assert sorted(versions) == versions, "řazení neodpovídá očekávanému pořadí"


def test_prerelease_sorts_before_release() -> None:
    assert Version.parse("7.25beta5") < Version.parse("7.25")
    assert Version.parse("7.25beta5") < Version.parse("7.25rc1")
    assert Version.parse("7.24.4") > Version.parse("7.24")


def test_is_prerelease() -> None:
    assert Version.parse("7.25beta5").is_prerelease
    assert Version.parse("7.24rc1").is_prerelease
    assert not Version.parse("7.24.4").is_prerelease


# --------------------------------------------------------------------------- #
# NEWEST
# --------------------------------------------------------------------------- #
def test_parse_newest_stable() -> None:
    info = parse_newest("7.24.4 1789558341", 7)
    assert str(info.version) == "7.24.4"
    assert info.released == datetime(2026, 9, 16, 11, 32, 21, tzinfo=UTC)


def test_parse_newest_development_beta() -> None:
    info = parse_newest("7.25beta5 1789557101\n", 7)
    assert str(info.version) == "7.25beta5"
    assert info.version.is_prerelease


def test_parse_newest_v6() -> None:
    info = parse_newest("6.49.22 1789563951", 6)
    assert str(info.version) == "6.49.22"


def test_parse_newest_rejects_wrong_major() -> None:
    """``NEWEST6.testing`` reálně vrací HTTP 200 s obsahem ``7.12.1``.

    Bez kontroly majoru by uživatel v režimu v6 dostal verzi v7.
    """
    with pytest.raises(RosdlError, match="major"):
        parse_newest("7.12.1 1700221125", 6)


def test_parse_newest_rejects_placeholder() -> None:
    """``NEWEST7.long-term`` vrací ``0.00`` – to není verze."""
    with pytest.raises(RosdlError):
        parse_newest("0.00", 7)


@pytest.mark.parametrize("text", ["", "   ", "nope", "7.24.4 extra junk"])
def test_parse_newest_rejects_garbage(text: str) -> None:
    with pytest.raises(RosdlError):
        parse_newest(text, 7)


def test_parse_newest_without_timestamp() -> None:
    info = parse_newest("7.24.4", 7)
    assert info.released is None
    assert info.released_text == "—"


# --------------------------------------------------------------------------- #
# SHA256 sidecar
# --------------------------------------------------------------------------- #
def test_parse_sha256_sidecar() -> None:
    text = (
        "627b9a58820b3b7a754992e1330341ffb61f8e61aa72e186bcbc2c55ebc06793  "
        "routeros-7.24.4-arm64.npk\n"
    )
    assert parse_sha256_sidecar(text) == (
        "627b9a58820b3b7a754992e1330341ffb61f8e61aa72e186bcbc2c55ebc06793"
    )


def test_parse_sha256_sidecar_uppercase() -> None:
    digest = "A" * 64
    assert parse_sha256_sidecar(f"{digest}  soubor.npk") == "a" * 64


@pytest.mark.parametrize("text", ["", "není to hash", "abc  soubor.npk", "zz" * 32])
def test_parse_sha256_sidecar_rejects_garbage(text: str) -> None:
    assert parse_sha256_sidecar(text) is None


# --------------------------------------------------------------------------- #
# Datum vydání z changelogu
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        # Novější vydání používají ISO datum bez času.
        ("What's new in 7.24.4 (2026-09-16):", date(2026, 9, 16)),
        ("What's new in 6.49.22 (2026-09-16):", date(2026, 9, 16)),
        ("What's new in 7.25beta5 (2026-09-16):", date(2026, 9, 16)),
        # Převažující tvar v archivu: anglická zkratka měsíce a čas.
        ("What's new in 6.49.12 (2024-Jan-22 15:04):", date(2024, 1, 22)),
        ("What's new in 7.16 (2024-Sep-20 16:00):", date(2024, 9, 20)),
        ("What's new in 7.24rc1 (2026-Jul-01 16:53):", date(2026, 7, 1)),
        ("What's new in 6.0 (2013-May-17 14:04):", date(2013, 5, 17)),
        ("What's new in 6.20 (2014-Oct-01 10:06):", date(2014, 10, 1)),
        ("What's new in 6.48.6 (2021-Dec-03 12:15):", date(2021, 12, 3)),
        # Starší v6 mívá před číslem verze ještě "v".
        ("What's new in v6.40 (2017-Jul-21 08:45):", date(2017, 7, 21)),
        # Koncová mezera za dvojtečkou se v archivu také vyskytuje.
        ("What's new in 6.49.1 (2021-Nov-17 10:06): ", date(2021, 11, 17)),
    ],
)
def test_parse_changelog_date(header: str, expected: date) -> None:
    assert parse_changelog_date(header) == expected


def test_changelog_date_after_preamble() -> None:
    """7.13.5 má před hlavičkou odstavec „Notice – …“, nesmí se přehlédnout."""
    text = (
        "Notice - Starting from RouterOS version 7.13, significant changes "
        "have been made to the RouterOS wireless packages.\n\n"
        "1. When upgrading by using \"check-for-updates\"...\n\n"
        "What's new in 7.13.5 (2024-Feb-16 19:35):\n\n"
        "*) bridge - fixed something;\n"
    )
    assert parse_changelog_date(text) == date(2024, 2, 16)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Pro verzi 7.99.9 není changelog k dispozici.",
        "What's new in 7.1 (kdovíkdy):",
        "What's new in 7.1 (2026-Xxx-05 10:00):",  # neexistující měsíc
        "What's new in 7.1 (2026-13-45):",  # neexistující datum
        "What's new in 7.1:",  # hlavička bez závorky
    ],
)
def test_parse_changelog_date_returns_none_instead_of_guessing(text: str) -> None:
    """Radši žádné datum než špatné – popisek pak ukáže „neuvedeno“."""
    assert parse_changelog_date(text) is None
