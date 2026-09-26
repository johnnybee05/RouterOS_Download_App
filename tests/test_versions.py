"""Parsování a řazení verzí + odpovědí NEWEST."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rosdl.core.client import parse_newest, parse_sha256_sidecar
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
