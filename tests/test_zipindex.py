"""Čtení ZIP Central Directory přes HTTP Range (s mockovaným serverem)."""

from __future__ import annotations

import struct

import pytest

from rosdl.core.errors import ZipIndexError
from rosdl.core.zipindex import (
    parse_central_directory,
    read_remote_zip_index,
)

from .conftest import FakeServer, make_zip, make_zip64

URL = "https://download.mikrotik.com/routeros/7.24.4/all_packages-arm64-7.24.4.zip"

CONTENTS = {
    "container-7.24.4-arm64.npk": b"C" * 1187,
    "wifi-qcom-7.24.4-arm64.npk": b"W" * 11485,
    "calea-7.24.4-arm64.npk": b"A" * 206,
}


def test_reads_stored_archive(server: FakeServer) -> None:
    server.add(URL, make_zip(CONTENTS, compress=False))
    entries = read_remote_zip_index(server.http(), URL)

    assert {e.name for e in entries} == set(CONTENTS)
    by_name = {e.name: e for e in entries}
    for name, data in CONTENTS.items():
        assert by_name[name].size == len(data)
        assert by_name[name].is_stored


def test_uses_uncompressed_size_for_deflated_archive(server: FakeServer) -> None:
    """Starší archivy (7.13.5) jsou DEFLATE – velikost .npk je ta nekomprimovaná."""
    server.add(URL, make_zip(CONTENTS, compress=True))
    entries = {e.name: e for e in read_remote_zip_index(server.http(), URL)}

    for name, data in CONTENTS.items():
        assert entries[name].size == len(data)
        assert entries[name].compressed_size < len(data), "data měla jít zkomprimovat"
        assert not entries[name].is_stored


def test_downloads_only_the_tail(server: FakeServer) -> None:
    """Z 5MB archivu se nesmí stáhnout víc než pár desítek kilobajtů."""
    big = make_zip({f"pkg{i}-7.24.4-arm64.npk": bytes(50_000) for i in range(100)})
    server.add(URL, big)

    entries = read_remote_zip_index(server.http(), URL)
    assert len(entries) == 100

    ranged = [r for r in server.requests if r.headers.get("Range")]
    assert ranged, "měl proběhnout aspoň jeden Range požadavek"
    assert all(r.method in ("HEAD", "GET") for r in server.requests)
    # HEAD + jeden Range GET stačí; celý soubor se stahovat nesmí.
    assert not any(
        r.method == "GET" and "Range" not in r.headers for r in server.requests
    )


def test_second_range_when_cd_outside_tail(server: FakeServer) -> None:
    """Když se Central Directory do staženého ocasu nevejde, dotáhne se zvlášť."""
    server.add(URL, make_zip(CONTENTS))
    entries = read_remote_zip_index(server.http(), URL, tail_bytes=64)

    assert {e.name for e in entries} == set(CONTENTS)
    ranges = [r.headers["Range"] for r in server.requests if r.headers.get("Range")]
    assert len(ranges) == 2, f"čekány dva Range požadavky, byly: {ranges}"


def test_archive_with_comment(server: FakeServer) -> None:
    """EOCD se hledá odzadu; komentář za ním nesmí parsování rozbít."""
    server.add(URL, make_zip(CONTENTS, comment=b"MikroTik " * 200))
    entries = read_remote_zip_index(server.http(), URL)
    assert len(entries) == len(CONTENTS)


def test_zip64_archive(server: FakeServer) -> None:
    """Archiv se ZIP64 koncovými strukturami se musí přečíst přes ZIP64 EOCD."""
    server.add(URL, make_zip64(CONTENTS))
    entries = {e.name: e for e in read_remote_zip_index(server.http(), URL)}

    assert set(entries) == set(CONTENTS)
    for name, data in CONTENTS.items():
        assert entries[name].size == len(data)


def test_zip64_without_locator_fails_clearly(server: FakeServer) -> None:
    broken = make_zip64(CONTENTS).replace(b"PK\x06\x07", b"PK\x06\x09")
    server.add(URL, broken)
    with pytest.raises(ZipIndexError, match="lokátor"):
        read_remote_zip_index(server.http(), URL)


def test_missing_archive_is_not_found(server: FakeServer) -> None:
    with pytest.raises(ZipIndexError):
        read_remote_zip_index(server.http(), URL)


def test_server_without_range_support(server: FakeServer) -> None:
    server.add(URL, make_zip(CONTENTS))
    server.support_ranges = False
    with pytest.raises(ZipIndexError, match="Range"):
        read_remote_zip_index(server.http(), URL)


def test_truncated_central_directory() -> None:
    """Useknutá CD musí skončit chybou, ne tichým polovičním seznamem."""
    data = make_zip(CONTENTS)
    eocd_at = data.rfind(b"PK\x05\x06")
    _, _, _, entries, cd_size, cd_off, _ = struct.unpack_from(
        "<HHHHIIH", data, eocd_at + 4
    )
    cd = data[cd_off : cd_off + cd_size]

    assert parse_central_directory(cd, entries)
    with pytest.raises(ZipIndexError, match="neúplná"):
        parse_central_directory(cd[: len(cd) // 2], entries)


def test_garbage_instead_of_zip(server: FakeServer) -> None:
    server.add(URL, b"this is definitely not a ZIP" * 100)
    with pytest.raises(ZipIndexError, match="End of Central Directory"):
        read_remote_zip_index(server.http(), URL)


def test_empty_archive(server: FakeServer) -> None:
    server.add(URL, make_zip({}))
    assert read_remote_zip_index(server.http(), URL) == []
