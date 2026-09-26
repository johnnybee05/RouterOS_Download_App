"""Čtení seznamu souborů ze vzdáleného ZIPu přes HTTP Range.

Stáhne se jen konec archivu (End of Central Directory + Central Directory),
takže seznam ~20 balíčků stojí ~66 KiB místo 50 MB celého archivu.

Důležité: velikost balíčku se bere z **nekomprimované** velikosti (``size``).
Novější archivy MikroTiku jsou STORED, starší (např. 7.13.5) DEFLATE, takže
komprimovaná velikost neodpovídá velikosti samostatně staženého .npk.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .errors import ZipIndexError
from .http import CancelToken, Http

EOCD_SIG = b"PK\x05\x06"
EOCD64_SIG = b"PK\x06\x06"
EOCD64_LOCATOR_SIG = b"PK\x06\x07"
CD_SIG = b"PK\x01\x02"

EOCD_FIXED_SIZE = 22
MAX_COMMENT = 0xFFFF
#: Stačí na EOCD i s maximálním komentářem; v praxi je komentář prázdný.
DEFAULT_TAIL = EOCD_FIXED_SIZE + MAX_COMMENT + 1024

ZIP64_MARKER_32 = 0xFFFFFFFF
ZIP64_MARKER_16 = 0xFFFF


@dataclass(frozen=True)
class ZipEntry:
    name: str
    size: int  # nekomprimovaná velikost = skutečná velikost souboru
    compressed_size: int
    crc32: int
    method: int

    @property
    def is_stored(self) -> bool:
        return self.method == 0


@dataclass(frozen=True)
class _Eocd:
    entries: int
    cd_size: int
    cd_offset: int


def _find_eocd(tail: bytes, tail_offset: int) -> _Eocd:
    idx = tail.rfind(EOCD_SIG)
    if idx < 0 or idx + EOCD_FIXED_SIZE > len(tail):
        raise ZipIndexError(
            "V konci archivu nebyl nalezen End of Central Directory záznam."
        )
    (
        _disk,
        _cd_disk,
        _entries_disk,
        entries,
        cd_size,
        cd_offset,
        _comment_len,
    ) = struct.unpack_from("<HHHHIIH", tail, idx + 4)

    needs_zip64 = (
        entries == ZIP64_MARKER_16
        or cd_size == ZIP64_MARKER_32
        or cd_offset == ZIP64_MARKER_32
    )
    if not needs_zip64:
        return _Eocd(entries=entries, cd_size=cd_size, cd_offset=cd_offset)

    return _read_zip64_eocd(tail, tail_offset)


def _read_zip64_eocd(tail: bytes, tail_offset: int) -> _Eocd:
    loc = tail.rfind(EOCD64_LOCATOR_SIG)
    if loc < 0:
        raise ZipIndexError("Archiv hlásí ZIP64, ale lokátor ZIP64 EOCD chybí.")
    (_disk, z64_offset, _total) = struct.unpack_from("<IQI", tail, loc + 4)

    rel = z64_offset - tail_offset
    if rel < 0 or rel + 56 > len(tail):
        raise ZipIndexError(
            "ZIP64 EOCD leží mimo stažený konec archivu – archiv je nestandardní."
        )
    if tail[rel : rel + 4] != EOCD64_SIG:
        raise ZipIndexError("Na pozici ZIP64 EOCD není očekávaná signatura.")
    entries, cd_size, cd_offset = struct.unpack_from("<QQQ", tail, rel + 32)
    return _Eocd(entries=int(entries), cd_size=int(cd_size), cd_offset=int(cd_offset))


def _zip64_sizes(extra: bytes, usize: int, csize: int) -> tuple[int, int]:
    """Z extra pole 0x0001 doplní velikosti, které se nevešly do 32 bitů."""
    if usize != ZIP64_MARKER_32 and csize != ZIP64_MARKER_32:
        return usize, csize
    off = 0
    while off + 4 <= len(extra):
        header_id, data_size = struct.unpack_from("<HH", extra, off)
        body = extra[off + 4 : off + 4 + data_size]
        if header_id == 0x0001:
            pos = 0
            if usize == ZIP64_MARKER_32 and pos + 8 <= len(body):
                usize = struct.unpack_from("<Q", body, pos)[0]
                pos += 8
            if csize == ZIP64_MARKER_32 and pos + 8 <= len(body):
                csize = struct.unpack_from("<Q", body, pos)[0]
            break
        off += 4 + data_size
    return usize, csize


def parse_central_directory(data: bytes, expected_entries: int) -> list[ZipEntry]:
    """Rozparsuje Central Directory. Čistá funkce – testuje se bez sítě."""
    entries: list[ZipEntry] = []
    off = 0
    while len(entries) < expected_entries:
        if off + 46 > len(data) or data[off : off + 4] != CD_SIG:
            break
        (
            _ver_made,
            _ver_need,
            _flags,
            method,
            _mtime,
            _mdate,
            crc32,
            csize,
            usize,
            name_len,
            extra_len,
            comment_len,
            _disk_start,
            _int_attr,
            _ext_attr,
            _local_offset,
        ) = struct.unpack_from("<HHHHHHIIIHHHHHII", data, off + 4)

        name_at = off + 46
        name = data[name_at : name_at + name_len].decode("utf-8", "replace")
        extra = data[name_at + name_len : name_at + name_len + extra_len]
        usize, csize = _zip64_sizes(extra, usize, csize)

        entries.append(
            ZipEntry(
                name=name,
                size=usize,
                compressed_size=csize,
                crc32=crc32,
                method=method,
            )
        )
        off = name_at + name_len + extra_len + comment_len

    if len(entries) != expected_entries:
        raise ZipIndexError(
            f"Central Directory je neúplná: přečteno {len(entries)} "
            f"z {expected_entries} záznamů."
        )
    return entries


def read_remote_zip_index(
    http: Http,
    url: str,
    *,
    size: int | None = None,
    tail_bytes: int = DEFAULT_TAIL,
    token: CancelToken | None = None,
) -> list[ZipEntry]:
    """Vrátí seznam souborů v archivu bez jeho stažení.

    Vyhodí ``NotFoundError`` když archiv neexistuje, ``ZipIndexError`` když
    server neumí Range nebo je Central Directory nečitelná.
    """
    if size is None:
        info = http.head(url, token=token)
        if not info.ok:
            raise ZipIndexError(f"Archiv není dostupný (HTTP {info.status}): {url}")
        if info.size is None:
            raise ZipIndexError(f"Server neuvedl velikost archivu: {url}")
        if not info.accept_ranges:
            raise ZipIndexError(f"Server nepodporuje Range požadavky: {url}")
        size = info.size

    tail_start = max(0, size - tail_bytes)
    tail = http.get_range(url, tail_start, token=token)
    if len(tail) >= size and tail_start != 0:
        # Server Range ignoroval a poslal celý soubor – pak je offset 0.
        tail_start = 0
    eocd = _find_eocd(tail, tail_start)

    cd_end = eocd.cd_offset + eocd.cd_size
    if tail_start <= eocd.cd_offset and cd_end <= tail_start + len(tail):
        cd = tail[eocd.cd_offset - tail_start : cd_end - tail_start]
    else:
        cd = http.get_range(url, eocd.cd_offset, cd_end - 1, token=token)
        if len(cd) != eocd.cd_size:
            raise ZipIndexError(
                f"Server vrátil {len(cd)} B místo {eocd.cd_size} B "
                "Central Directory – Range není respektován."
            )

    return parse_central_directory(cd, eocd.entries)
