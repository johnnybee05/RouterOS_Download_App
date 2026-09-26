"""Tenká vrstva nad httpx: opakování pokusů, timeouty, proxy, User-Agent.

Vše je synchronní. Souběžnost řeší volající přes ThreadPoolExecutor (CLI)
nebo QThreadPool (GUI), takže jádro nepotřebuje asyncio ani Qt.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

from .errors import Cancelled, HttpError, NetworkError, NotFoundError

USER_AGENT = "RosDownloader/1.0 (+https://mikrotik.com/download)"

DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)
DEFAULT_ATTEMPTS = 3
#: Prodleva před 2. a 3. pokusem (sekundy). Krátká – soubory jsou velké,
#: ale server je spolehlivý, takže dlouhé čekání jen zdržuje uživatele.
BACKOFF = (1.0, 3.0)

#: Stavy, u kterých má smysl zkusit to znovu. 404 mezi nimi záměrně není.
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HeadInfo:
    status: int
    size: int | None
    accept_ranges: bool
    etag: str | None = None
    last_modified: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200


class CancelToken:
    """Sdílený příznak zrušení. Bez Qt, aby šel použít i z CLI a z testů."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise Cancelled("Operace byla zrušena.")

    def wait(self, seconds: float) -> bool:
        """Čeká, ale probudí se okamžitě při zrušení. True = bylo zrušeno."""
        return self._event.wait(seconds)


class Http:
    """Klient s opakováním pokusů. Je thread-safe (httpx.Client to zvládá)."""

    def __init__(
        self,
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        attempts: int = DEFAULT_ATTEMPTS,
        client: httpx.Client | None = None,
    ) -> None:
        self.attempts = attempts
        # trust_env=True (výchozí) -> httpx převezme systémovou proxy
        # z HTTP(S)_PROXY / NO_PROXY i z nastavení Windows.
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            trust_env=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Http:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------------------------------------------- #
    def _attempt_loop(
        self, token: CancelToken | None
    ) -> Iterator[tuple[int, bool]]:
        """Generátor (číslo pokusu, je_poslední) s prodlevou mezi pokusy."""
        for i in range(self.attempts):
            if token is not None:
                token.raise_if_cancelled()
            if i:
                delay = BACKOFF[min(i - 1, len(BACKOFF) - 1)]
                if token is not None:
                    if token.wait(delay):
                        raise Cancelled("Operace byla zrušena.")
                else:
                    time.sleep(delay)
            yield i, i == self.attempts - 1

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        token: CancelToken | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Provede požadavek s opakováním. 404 vyhodí NotFoundError hned."""
        last_exc: Exception | None = None
        for _, is_last in self._attempt_loop(token):
            try:
                if stream:
                    # Volající musí response zavřít (nebo použít stream_get()).
                    req = self._client.build_request(method, url, headers=headers)
                    resp = self._client.send(req, stream=True)
                else:
                    resp = self._client.request(method, url, headers=headers)
            except httpx.HTTPError as exc:
                last_exc = exc
                if is_last:
                    raise NetworkError(f"Spojení selhalo: {url}\n{exc}") from exc
                continue

            if resp.status_code == 404:
                resp.close()
                raise NotFoundError(url)
            if resp.status_code in RETRYABLE_STATUS and not is_last:
                resp.close()
                last_exc = HttpError(url, resp.status_code)
                continue
            if resp.status_code >= 400:
                status = resp.status_code
                resp.close()
                raise HttpError(url, status)
            return resp

        raise NetworkError(f"Spojení selhalo: {url}") from last_exc

    # ----------------------------------------------------------------- #
    def head(self, url: str, *, token: CancelToken | None = None) -> HeadInfo:
        """HEAD, který nevyhazuje na 404 – vrátí HeadInfo se status 404."""
        try:
            resp = self.request("HEAD", url, token=token)
        except NotFoundError:
            return HeadInfo(status=404, size=None, accept_ranges=False)
        length = resp.headers.get("content-length")
        return HeadInfo(
            status=resp.status_code,
            size=int(length) if length and length.isdigit() else None,
            accept_ranges="bytes" in resp.headers.get("accept-ranges", "").lower(),
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
        )

    def exists(self, url: str, *, token: CancelToken | None = None) -> bool:
        return self.head(url, token=token).ok

    def get_text(self, url: str, *, token: CancelToken | None = None) -> str:
        resp = self.request("GET", url, token=token)
        return resp.text

    def get_bytes(self, url: str, *, token: CancelToken | None = None) -> bytes:
        resp = self.request("GET", url, token=token)
        return resp.content

    def get_range(
        self,
        url: str,
        start: int,
        end: int | None = None,
        *,
        token: CancelToken | None = None,
    ) -> bytes:
        """Stáhne bajty ``start..end`` včetně. ``end=None`` = do konce souboru."""
        rng = f"bytes={start}-" + ("" if end is None else str(end))
        resp = self.request("GET", url, headers={"Range": rng}, token=token)
        return resp.content

    def stream_get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        token: CancelToken | None = None,
    ) -> httpx.Response:
        """Streamovaná odpověď; volající ji musí zavřít (``with resp:``)."""
        return self.request("GET", url, headers=headers, token=token, stream=True)
