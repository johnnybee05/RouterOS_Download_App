"""Klient: zjišťování balíčků z archivu, záložní sondáž, cache, changelog."""

from __future__ import annotations

from pathlib import Path

import pytest

from rosdl.core import urls
from rosdl.core.cache import JsonCache
from rosdl.core.client import MikrotikClient
from rosdl.core.errors import RosdlError
from rosdl.core.models import Channel, Version

from .conftest import FakeServer, make_zip

V7 = Version.parse("7.24.4")
V6 = Version.parse("6.49.22")

ARM64_ZIP = {
    "container-7.24.4-arm64.npk": b"C" * 1000,
    "wifi-qcom-7.24.4-arm64.npk": b"W" * 2000,
    "calea-7.24.4-arm64.npk": b"A" * 300,
}
X86_ZIP = {
    "container-7.24.4.npk": b"C" * 1100,
    "wireless-7.24.4.npk": b"R" * 900,
}


@pytest.fixture
def client(server: FakeServer, tmp_path: Path) -> MikrotikClient:
    return MikrotikClient(
        server.http(),
        versions_cache=JsonCache("versions.json", 3600, directory=tmp_path),
        packages_cache=JsonCache("packages.json", 3600, directory=tmp_path),
    )


def _add_zip(server: FakeServer, version: Version, arch: str, contents: dict) -> None:
    server.add(
        urls.file_url(version, urls.all_packages_zip_name(version, arch)),
        make_zip(contents),
    )


# --------------------------------------------------------------------------- #
# NEWEST
# --------------------------------------------------------------------------- #
def test_newest(server: FakeServer, client: MikrotikClient) -> None:
    server.add(urls.newest_url(7, Channel.STABLE), "7.24.4 1789558341")
    info = client.newest(7, Channel.STABLE)
    assert str(info.version) == "7.24.4"
    assert info.released_text == "16.09.2026"


def test_newest_rejects_v7_answer_on_v6_channel(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Reálné chování ``NEWEST6.testing``: HTTP 200 a obsah ``7.12.1``."""
    server.add(urls.newest_url(6, Channel.TESTING), "7.12.1 1700221125")
    with pytest.raises(RosdlError, match="major"):
        client.newest(6, Channel.TESTING)


# --------------------------------------------------------------------------- #
# Seznam balíčků
# --------------------------------------------------------------------------- #
def test_packages_from_archive(server: FakeServer, client: MikrotikClient) -> None:
    _add_zip(server, V7, "arm64", ARM64_ZIP)
    result = client.list_packages(V7, "arm64")

    assert result.source == "zip"
    assert result.packages == ["calea", "container", "wifi-qcom"]
    assert result.entries["container"].size == 1000
    assert result.entries["container"].filename == "container-7.24.4-arm64.npk"


def test_packages_x86_names_have_no_arch_suffix(
    server: FakeServer, client: MikrotikClient
) -> None:
    _add_zip(server, V7, "x86", X86_ZIP)
    result = client.list_packages(V7, "x86")

    assert result.packages == ["container", "wireless"]
    assert result.entries["container"].filename == "container-7.24.4.npk"


def test_packages_skip_main_package_inside_archive(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Kdyby archiv obsahoval i ``routeros``, nesmí se objevit mezi extras."""
    _add_zip(
        server,
        V7,
        "arm64",
        {**ARM64_ZIP, "routeros-7.24.4-arm64.npk": b"M" * 10},
    )
    assert "routeros" not in client.list_packages(V7, "arm64").packages


def test_packages_ignore_foreign_names(
    server: FakeServer, client: MikrotikClient
) -> None:
    _add_zip(
        server,
        V7,
        "arm64",
        {**ARM64_ZIP, "README.txt": b"x", "container-7.23.7-arm64.npk": b"y"},
    )
    assert client.list_packages(V7, "arm64").packages == [
        "calea",
        "container",
        "wifi-qcom",
    ]


def test_falls_back_to_head_probes_without_archive(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Bez archivu se musí sada zjistit paralelními HEAD dotazy."""
    server.add(urls.file_url(V7, "container-7.24.4-arm64.npk"), b"C" * 1000)
    server.add(urls.file_url(V7, "zerotier-7.24.4-arm64.npk"), b"Z" * 500)

    result = client.list_packages(V7, "arm64")

    assert result.source == "head"
    assert result.packages == ["container", "zerotier"]
    assert result.entries["zerotier"].size == 500


def test_packages_are_cached(server: FakeServer, client: MikrotikClient) -> None:
    _add_zip(server, V7, "arm64", ARM64_ZIP)
    first = client.list_packages(V7, "arm64")
    calls = len(server.requests)

    second = client.list_packages(V7, "arm64")
    assert len(server.requests) == calls, "druhé volání mělo přijít z cache"
    assert second.packages == first.packages
    assert second.entries["container"].size == 1000


def test_cache_can_be_bypassed(server: FakeServer, client: MikrotikClient) -> None:
    _add_zip(server, V7, "arm64", ARM64_ZIP)
    client.list_packages(V7, "arm64")
    calls = len(server.requests)
    client.list_packages(V7, "arm64", use_cache=False)
    assert len(server.requests) > calls


def test_packages_cached_per_arch_and_version(
    server: FakeServer, client: MikrotikClient
) -> None:
    _add_zip(server, V7, "arm64", ARM64_ZIP)
    _add_zip(server, V7, "x86", X86_ZIP)

    assert client.list_packages(V7, "arm64").packages != (
        client.list_packages(V7, "x86").packages
    )


# --------------------------------------------------------------------------- #
# Soubory
# --------------------------------------------------------------------------- #
def test_main_file_for_v6_ppc_uses_powerpc(client: MikrotikClient) -> None:
    remote = client.main_file(V6, "ppc")
    assert remote.name == "routeros-powerpc-6.49.22.npk"
    assert remote.url.endswith("/routeros/6.49.22/routeros-powerpc-6.49.22.npk")
    assert remote.sha256_url.endswith(".npk.sha256")


def test_extra_file_carries_size(server: FakeServer, client: MikrotikClient) -> None:
    _add_zip(server, V7, "arm64", ARM64_ZIP)
    entry = client.list_packages(V7, "arm64").entries["wifi-qcom"]
    remote = client.extra_file(entry, V7)
    assert remote.size == 2000
    assert remote.url.endswith("wifi-qcom-7.24.4-arm64.npk")


def test_fill_sizes_uses_head(server: FakeServer, client: MikrotikClient) -> None:
    server.add(urls.file_url(V7, "routeros-7.24.4-arm64.npk"), b"M" * 4242)
    [filled] = client.fill_sizes([client.main_file(V7, "arm64")])
    assert filled.size == 4242


def test_fill_sizes_leaves_missing_files_alone(
    server: FakeServer, client: MikrotikClient
) -> None:
    [filled] = client.fill_sizes([client.main_file(V7, "arm64")])
    assert filled.size is None


# --------------------------------------------------------------------------- #
# Changelog a existence verze
# --------------------------------------------------------------------------- #
def test_changelog(server: FakeServer, client: MikrotikClient) -> None:
    server.add(urls.changelog_url(V7), "What's new in 7.24.4 (2026-09-16):\n")
    assert "7.24.4" in client.changelog(V7)


def test_changelog_missing_is_friendly(client: MikrotikClient) -> None:
    text = client.changelog(V7)
    assert "není changelog" in text


def test_version_exists(server: FakeServer, client: MikrotikClient) -> None:
    server.add(urls.changelog_url(V7), "x")
    assert client.version_exists(V7)
    assert not client.version_exists(Version.parse("7.99.9"))


# --------------------------------------------------------------------------- #
# Historie verzí
# --------------------------------------------------------------------------- #
def test_list_versions_probes_changelogs(
    server: FakeServer, client: MikrotikClient
) -> None:
    for text in ("7.3", "7.3.1", "7.4", "7.4.1", "7.4.2"):
        server.add(urls.changelog_url(text), "x")

    found = client.list_versions(7, Version.parse("7.4.2"))

    assert [str(v) for v in found] == ["7.4.2", "7.4.1", "7.4", "7.3.1", "7.3"]


def test_list_versions_is_cached(server: FakeServer, client: MikrotikClient) -> None:
    server.add(urls.changelog_url("7.1"), "x")
    newest = Version.parse("7.1")
    client.list_versions(7, newest)
    calls = len(server.requests)

    again = client.list_versions(7, newest)
    assert len(server.requests) == calls
    assert [str(v) for v in again] == ["7.1"]


def test_list_versions_always_contains_newest(
    server: FakeServer, client: MikrotikClient
) -> None:
    """I když by sondáž selhala, nabízená verze z kanálu musí v seznamu být."""
    found = client.list_versions(7, Version.parse("7.24.4"))
    assert Version.parse("7.24.4") in found


def test_list_versions_finds_prereleases(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Kanál development hlásí jako nejnovější betu – ta i sousední musí projít."""
    for text in ("7.25beta3", "7.25beta5", "7.24rc1", "7.24.4"):
        server.add(urls.changelog_url(text), "x")

    found = client.list_versions(7, Version.parse("7.25beta5"))

    assert [str(v) for v in found[:4]] == [
        "7.25beta5",
        "7.25beta3",
        "7.24.4",
        "7.24rc1",
    ]


def test_filter_for_channel_hides_prereleases_in_stable() -> None:
    from rosdl.core.client import filter_for_channel

    versions = [Version.parse(t) for t in ("7.25beta5", "7.24.4", "7.24rc1")]

    assert [str(v) for v in filter_for_channel(versions, Channel.STABLE)] == ["7.24.4"]
    assert filter_for_channel(versions, Channel.DEVELOPMENT) == versions
    assert filter_for_channel(versions, Channel.TESTING) == versions


def test_changelog_info_reads_release_date(
    server: FakeServer, client: MikrotikClient
) -> None:
    server.add(
        urls.changelog_url(V6),
        "What's new in 6.49.22 (2024-Jan-22 15:04):\n\n*) system - něco;\n",
    )
    info = client.changelog_info(V6)

    assert info.version == V6
    assert info.released_text == "22.01.2024"
    assert "system" in info.text


def test_changelog_info_without_date(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Chybějící changelog nesmí vyrobit vymyšlené datum."""
    info = client.changelog_info(Version.parse("7.99.9"))

    assert info.released is None
    assert info.released_text == "—"


def test_release_date_belongs_to_selected_version(
    server: FakeServer, client: MikrotikClient
) -> None:
    """Jádro chyby: datum musí patřit vybrané verzi, ne nejnovější v kanálu."""
    server.add(urls.newest_url(6, Channel.LONG_TERM), "6.49.22 1789563951")
    server.add(urls.changelog_url("6.49.22"), "What's new in 6.49.22 (2026-09-16):")
    server.add(
        urls.changelog_url("6.49.12"), "What's new in 6.49.12 (2024-Jan-22 15:04):"
    )

    newest = client.newest(6, Channel.LONG_TERM)
    older = client.changelog_info(Version.parse("6.49.12"))

    assert newest.released_text == "16.09.2026"
    assert older.released_text == "22.01.2024"
    assert older.released_text != newest.released_text
