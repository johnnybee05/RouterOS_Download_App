"""Sestavování URL. Testovací hodnoty pocházejí z ověřených HTTP odpovědí
zaznamenaných v docs/ENDPOINTS.md, ne z domněnek.
"""

from __future__ import annotations

import pytest

from rosdl.core import urls
from rosdl.core.models import Channel, Version

V7 = Version.parse("7.24.4")
V6 = Version.parse("6.49.22")
V7_BETA = Version.parse("7.25beta5")


# --------------------------------------------------------------------------- #
# Hlavní balíček
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("arch", "expected"),
    [
        ("arm", "routeros-7.24.4-arm.npk"),
        ("arm64", "routeros-7.24.4-arm64.npk"),
        ("mipsbe", "routeros-7.24.4-mipsbe.npk"),
        ("mmips", "routeros-7.24.4-mmips.npk"),
        ("smips", "routeros-7.24.4-smips.npk"),
        ("ppc", "routeros-7.24.4-ppc.npk"),
        ("tile", "routeros-7.24.4-tile.npk"),
        # x86 je jediná architektura, která ve v7 příponu nemá.
        ("x86", "routeros-7.24.4.npk"),
    ],
)
def test_v7_main_package(arch: str, expected: str) -> None:
    assert urls.main_package_name(V7, arch) == expected


@pytest.mark.parametrize(
    ("arch", "expected"),
    [
        ("arm", "routeros-arm-6.49.22.npk"),
        ("arm64", "routeros-arm64-6.49.22.npk"),
        ("mipsbe", "routeros-mipsbe-6.49.22.npk"),
        ("mmips", "routeros-mmips-6.49.22.npk"),
        ("smips", "routeros-smips-6.49.22.npk"),
        ("tile", "routeros-tile-6.49.22.npk"),
        # Ve v6 x86 příponu MÁ – na rozdíl od v7.
        ("x86", "routeros-x86-6.49.22.npk"),
        # A PowerPC se ve v6 jmenuje powerpc, ne ppc.
        ("ppc", "routeros-powerpc-6.49.22.npk"),
    ],
)
def test_v6_main_package(arch: str, expected: str) -> None:
    assert urls.main_package_name(V6, arch) == expected


def test_v7_main_beta_keeps_suffix() -> None:
    assert urls.main_package_name(V7_BETA, "arm64") == "routeros-7.25beta5-arm64.npk"
    assert urls.main_package_name(V7_BETA, "x86") == "routeros-7.25beta5.npk"


def test_ppc_rename_is_v6_main_only() -> None:
    """``powerpc`` se objevuje jen v hlavním balíčku v6, nikde jinde."""
    assert urls.main_arch_token(V6, "ppc") == "powerpc"
    assert urls.main_arch_token(V7, "ppc") == "ppc"
    assert urls.extra_package_name("wireless", V6, "ppc") == "wireless-6.49.22-ppc.npk"
    assert urls.all_packages_zip_name(V6, "ppc") == "all_packages-ppc-6.49.22.zip"


# --------------------------------------------------------------------------- #
# Extra balíčky
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("version", "package", "arch", "expected"),
    [
        (V7, "container", "arm64", "container-7.24.4-arm64.npk"),
        (V7, "wifi-qcom", "arm64", "wifi-qcom-7.24.4-arm64.npk"),
        (V7, "container", "x86", "container-7.24.4.npk"),
        (V7, "hotspot", "smips", "hotspot-7.24.4-smips.npk"),
        (V6, "wireless", "arm", "wireless-6.49.22-arm.npk"),
        (V6, "advanced-tools", "x86", "advanced-tools-6.49.22.npk"),
        (V6, "system", "ppc", "system-6.49.22-ppc.npk"),
    ],
)
def test_extra_package(
    version: Version, package: str, arch: str, expected: str
) -> None:
    assert urls.extra_package_name(package, version, arch) == expected


# --------------------------------------------------------------------------- #
# Archiv
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("version", "arch", "expected"),
    [
        (V7, "arm64", "all_packages-arm64-7.24.4.zip"),
        # V názvu ZIPu se x86 používá, i když soubory uvnitř příponu nemají.
        (V7, "x86", "all_packages-x86-7.24.4.zip"),
        (V6, "x86", "all_packages-x86-6.49.22.zip"),
        (V7_BETA, "arm64", "all_packages-arm64-7.25beta5.zip"),
    ],
)
def test_all_packages_zip(version: Version, arch: str, expected: str) -> None:
    assert urls.all_packages_zip_name(version, arch) == expected


# --------------------------------------------------------------------------- #
# Zpětný převod názvu souboru na balíček
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("filename", "version", "arch", "expected"),
    [
        ("container-7.24.4-arm64.npk", V7, "arm64", "container"),
        ("wifi-qcom-be-7.24.4-arm64.npk", V7, "arm64", "wifi-qcom-be"),
        ("container-7.24.4.npk", V7, "x86", "container"),
        ("tr069-client-6.49.22-ppc.npk", V6, "ppc", "tr069-client"),
        ("routeros-7.24.4-arm64.npk", V7, "arm64", "routeros"),
        # Nesedící architektura ani přípona se nesmí tiše přijmout.
        ("container-7.24.4-arm.npk", V7, "arm64", None),
        ("container-7.24.4-arm64.txt", V7, "arm64", None),
        ("7.24.4-arm64.npk", V7, "arm64", None),
    ],
)
def test_package_from_filename(
    filename: str, version: Version, arch: str, expected: str | None
) -> None:
    assert urls.package_from_filename(filename, version, arch) == expected


def test_filename_roundtrip_all_archs() -> None:
    for arch in ("arm", "arm64", "mipsbe", "mmips", "smips", "ppc", "tile", "x86"):
        name = urls.extra_package_name("container", V7, arch)
        assert urls.package_from_filename(name, V7, arch) == "container"


# --------------------------------------------------------------------------- #
# Ostatní URL
# --------------------------------------------------------------------------- #
def test_newest_url_uses_a7_for_v7() -> None:
    assert (
        urls.newest_url(7, Channel.STABLE)
        == "https://upgrade.mikrotik.com/routeros/NEWESTa7.stable"
    )
    assert (
        urls.newest_url(7, Channel.LONG_TERM)
        == "https://upgrade.mikrotik.com/routeros/NEWESTa7.long-term"
    )
    assert (
        urls.newest_url(6, Channel.STABLE)
        == "https://upgrade.mikrotik.com/routeros/NEWEST6.stable"
    )


def test_newest_url_accepts_plain_string() -> None:
    assert urls.newest_url(7, "development").endswith("NEWESTa7.development")


def test_file_and_sha256_url() -> None:
    url = urls.file_url(V7, "routeros-7.24.4-arm64.npk")
    assert url == (
        "https://download.mikrotik.com/routeros/7.24.4/routeros-7.24.4-arm64.npk"
    )
    assert urls.sha256_url(url) == url + ".sha256"


def test_changelog_url() -> None:
    assert (
        urls.changelog_url(V7)
        == "https://upgrade.mikrotik.com/routeros/7.24.4/CHANGELOG"
    )
