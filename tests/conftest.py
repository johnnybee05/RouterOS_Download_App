"""Sdílené fixtures: falešný HTTP server postavený na httpx.MockTransport."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Callable

import httpx
import pytest

from rosdl.core.http import Http


class BrokenStream(httpx.SyncByteStream):
    """Tělo odpovědi, které po ``fail_after`` bajtech spadne jako síť."""

    CHUNK = 64 * 1024

    def __init__(self, data: bytes, fail_after: int) -> None:
        self._data = data
        self._fail_after = fail_after

    def __iter__(self):  # noqa: ANN204
        sent = 0
        for start in range(0, len(self._data), self.CHUNK):
            part = self._data[start : start + self.CHUNK]
            if sent + len(part) > self._fail_after:
                remaining = self._fail_after - sent
                if remaining > 0:
                    yield part[:remaining]
                raise httpx.ReadError("spojení spadlo uprostřed přenosu")
            sent += len(part)
            yield part

    def close(self) -> None:
        return


class FakeServer:
    """Mapuje URL -> obsah a umí Range, HEAD, 404 i vynucené chyby.

    Chová se jako download.mikrotik.com: ``Accept-Ranges: bytes``,
    ``Content-Length``, 404 s prázdným tělem.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.requests: list[httpx.Request] = []
        #: URL -> kolikrát ještě vrátit chybu, než se soubor začne servírovat.
        self.fail_times: dict[str, int] = {}
        #: URL -> (po kolika bajtech utnout stream, kolikrát to ještě udělat).
        self.break_stream: dict[str, list[int]] = {}
        self.fail_status = 503
        self.support_ranges = True

    def break_stream_after(self, url: str, nbytes: int, times: int = 1) -> None:
        """Prvních ``times`` GETů utne po ``nbytes`` bajtech."""
        self.break_stream[url] = [nbytes, times]

    # -- naplnění ---------------------------------------------------- #
    def add(self, url: str, content: bytes | str) -> None:
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.files[url] = data

    def add_with_sha256(self, url: str, content: bytes) -> str:
        self.add(url, content)
        digest = hashlib.sha256(content).hexdigest()
        name = url.rsplit("/", 1)[-1]
        self.add(url + ".sha256", f"{digest}  {name}\n")
        return digest

    # -- transport ---------------------------------------------------- #
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)

        remaining = self.fail_times.get(url, 0)
        if remaining:
            self.fail_times[url] = remaining - 1
            return httpx.Response(self.fail_status, content=b"")

        data = self.files.get(url)
        if data is None:
            return httpx.Response(404, content=b"")

        headers = {"Content-Type": "application/octet-stream"}
        if self.support_ranges:
            headers["Accept-Ranges"] = "bytes"

        broken = self.break_stream.get(url)
        if broken is not None and broken[1] > 0 and request.method == "GET":
            broken[1] -= 1
            return httpx.Response(
                200,
                headers={**headers, "Content-Length": str(len(data))},
                stream=BrokenStream(data, broken[0]),
            )

        rng = request.headers.get("Range")
        if rng and self.support_ranges and rng.startswith("bytes="):
            spec = rng[len("bytes=") :]
            start_text, _, end_text = spec.partition("-")
            start = int(start_text) if start_text else 0
            end = int(end_text) if end_text else len(data) - 1
            end = min(end, len(data) - 1)
            chunk = data[start : end + 1]
            headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
            if request.method == "HEAD":
                return httpx.Response(206, headers=headers)
            return httpx.Response(206, content=chunk, headers=headers)

        if request.method == "HEAD":
            headers["Content-Length"] = str(len(data))
            return httpx.Response(200, headers=headers)
        return httpx.Response(200, content=data, headers=headers)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def http(self, **kwargs: object) -> Http:
        return Http(client=self.client(), **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()


@pytest.fixture
def http(server: FakeServer) -> Http:
    return server.http()


def make_zip(
    entries: dict[str, bytes],
    *,
    compress: bool = False,
    comment: bytes = b"",
) -> bytes:
    """Vyrobí skutečný ZIP, aby se testoval opravdový formát, ne atrapa."""
    buffer = io.BytesIO()
    method = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(buffer, "w", compression=method) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        if comment:
            zf.comment = comment
    return buffer.getvalue()


def make_zip64(entries: dict[str, bytes]) -> bytes:
    """Vyrobí archiv se ZIP64 koncovými strukturami.

    ``zipfile`` je zapíše až nad 65 535 položkami nebo 4 GB, což se do testu
    nevejde, takže se klasický EOCD nahradí ZIP64 EOCD + lokátorem + EOCD
    se značkami 0xFFFF / 0xFFFFFFFF. Je to přesně to, co by přišlo ze sítě.
    """
    import struct

    data = make_zip(entries)
    eocd_at = data.rfind(b"PK\x05\x06")
    (_d, _dc, ents_disk, ents_total, cd_size, cd_offset, _clen) = struct.unpack_from(
        "<HHHHIIH", data, eocd_at + 4
    )
    body = data[:eocd_at]

    zip64_eocd_at = len(body)
    zip64_eocd = struct.pack(
        "<4sQHHIIQQQQ",
        b"PK\x06\x06",
        44,  # velikost záznamu bez prvních 12 bajtů
        45,
        45,
        0,
        0,
        ents_disk,
        ents_total,
        cd_size,
        cd_offset,
    )
    locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, zip64_eocd_at, 1)
    eocd = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",
        0xFFFF,
        0xFFFF,
        0xFFFF,
        0xFFFF,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0,
    )
    return body + zip64_eocd + locator + eocd


#: Typová nápověda pro testy, které si server staví samy.
ServerFactory = Callable[[], FakeServer]
