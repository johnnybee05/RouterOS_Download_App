"""Aktualizace aplikace z GitHub Releases.

Tři samostatné kroky, aby se každý dal otestovat zvlášť:

1. :func:`check_for_update` – zeptá se API na poslední vydání a porovná verze,
2. :func:`download_update` – stáhne ``.exe`` a ověří ho proti SHA256,
3. :func:`install_update` + :func:`relaunch` – zamění běžící soubor a restartuje.

Bez Qt, aby šlo všechno vyzkoušet proti falešnému serveru z ``conftest.py``.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering
from pathlib import Path

import httpx

from .cache import APP_NAME
from .client import format_date
from .errors import (
    Cancelled,
    ChecksumMismatch,
    HttpError,
    NetworkError,
    NotFoundError,
    SizeMismatch,
    UpdateError,
)
from .http import BACKOFF, CancelToken, Http

REPO = "johnnybee05/RouterOS_Download_App"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{REPO}/releases"

#: Verzovaná hlavička podle dokumentace GitHubu – bez ní se chování API
#: může časem změnit pod rukama.
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

#: Přesně takhle se soubor jmenuje v releasech. Když ho GitHub nevrátí,
#: vezme se první jiný ``.exe``.
ASSET_NAME = "RosDownloader.exe"

CHUNK_SIZE = 256 * 1024
DOWNLOAD_ATTEMPTS = 3
PART_SUFFIX = ".part"
BACKUP_SUFFIX = ".old"

#: Kdyby GitHub u přílohy ``digest`` neposlal, vytáhne se otisk z popisu
#: vydání – releasy ho uvádějí jako ``SHA256: <64 hex>``.
_SHA256_IN_BODY_RE = re.compile(r"\bSHA-?256\b\s*[:=]?\s*([0-9a-fA-F]{64})")

_APP_VERSION_RE = re.compile(
    r"^v?(?P<release>\d+(?:\.\d+)*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)

#: Na kolik složek se čísla verze doplní nulami, aby ``1.1`` a ``1.1.0``
#: vyšly stejně.
_VERSION_WIDTH = 4


@total_ordering
@dataclass(frozen=True, eq=False)
class AppVersion:
    """Verze aplikace: ``1.0.3``, ``v1.1``, ``2.0.0-beta.1`` (semver)."""

    release: tuple[int, ...]
    pre: tuple[str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> AppVersion:
        m = _APP_VERSION_RE.match(text.strip())
        if not m:
            raise ValueError(f"Neplatný tvar verze: {text!r}")
        pre = m.group("pre")
        return cls(
            release=tuple(int(p) for p in m.group("release").split(".")),
            pre=tuple(pre.split(".")) if pre else (),
        )

    @classmethod
    def try_parse(cls, text: str) -> AppVersion | None:
        try:
            return cls.parse(text)
        except ValueError:
            return None

    def __str__(self) -> str:
        out = ".".join(str(p) for p in self.release)
        return f"{out}-{'.'.join(self.pre)}" if self.pre else out

    @property
    def is_prerelease(self) -> bool:
        return bool(self.pre)

    def _key(self) -> tuple[object, ...]:
        width = max(_VERSION_WIDTH, len(self.release))
        numbers = tuple(
            self.release[i] if i < len(self.release) else 0 for i in range(width)
        )
        # Předrelease se řadí před finální verzi; uvnitř číslo před slovem,
        # přesně jak to popisuje semver.
        marks = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in self.pre)
        return (numbers, 0 if self.pre else 1, marks)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AppVersion):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AppVersion):
            return NotImplemented
        return self._key() < other._key()


@dataclass(frozen=True)
class ReleaseInfo:
    """Jedno vydání na GitHubu i s přílohou, kterou umíme nasadit."""

    tag: str
    name: str = ""
    notes: str = ""
    page_url: str = RELEASES_PAGE_URL
    version: AppVersion | None = None
    published: datetime | None = None
    prerelease: bool = False
    asset_name: str | None = None
    asset_url: str | None = None
    asset_size: int | None = None
    asset_sha256: str | None = None

    @property
    def has_asset(self) -> bool:
        return bool(self.asset_url)

    @property
    def title(self) -> str:
        return self.name or self.tag

    @property
    def published_text(self) -> str:
        return format_date(self.published)


# --------------------------------------------------------------------------- #
# Dotaz na API
# --------------------------------------------------------------------------- #
def _pick_asset(assets: object) -> dict | None:
    """Vybere přílohu, kterou umíme nasadit – tedy ``.exe``."""
    if not isinstance(assets, list):
        return None
    exes = [
        a
        for a in assets
        if isinstance(a, dict) and str(a.get("name", "")).lower().endswith(".exe")
    ]
    for asset in exes:
        if str(asset.get("name", "")).lower() == ASSET_NAME.lower():
            return asset
    return exes[0] if exes else None


def _asset_sha256(asset: dict | None, body: str) -> str | None:
    """Otisk z pole ``digest``; starší releasy ho mají jen v popisu."""
    if asset is not None:
        digest = str(asset.get("digest") or "")
        if digest.lower().startswith("sha256:"):
            candidate = digest.split(":", 1)[1].strip().lower()
            if len(candidate) == 64:
                return candidate
    found = _SHA256_IN_BODY_RE.search(body)
    return found.group(1).lower() if found else None


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_release(payload: object) -> ReleaseInfo:
    """Odpověď API na ``ReleaseInfo``. Chybějící pole se berou jako neznámá."""
    if not isinstance(payload, dict):
        raise UpdateError("GitHub vrátil odpověď, které nerozumím.")
    tag = str(payload.get("tag_name") or "")
    if not tag:
        raise UpdateError("Vydání na GitHubu nemá značku verze.")
    body = str(payload.get("body") or "")
    asset = _pick_asset(payload.get("assets"))
    size = asset.get("size") if asset else None
    return ReleaseInfo(
        tag=tag,
        name=str(payload.get("name") or ""),
        notes=body,
        page_url=str(payload.get("html_url") or f"{RELEASES_PAGE_URL}/tag/{tag}"),
        version=AppVersion.try_parse(tag),
        published=_parse_stamp(payload.get("published_at")),
        prerelease=bool(payload.get("prerelease")),
        asset_name=str(asset.get("name")) if asset else None,
        asset_url=str(asset.get("browser_download_url")) if asset else None,
        asset_size=size if isinstance(size, int) else None,
        asset_sha256=_asset_sha256(asset, body),
    )


def fetch_latest(http: Http, *, token: CancelToken | None = None) -> ReleaseInfo:
    """Poslední vydání projektu. Předrelease a rozepsané GitHub nevrací."""
    try:
        resp = http.request("GET", LATEST_RELEASE_URL, headers=API_HEADERS, token=token)
    except NotFoundError as exc:
        raise UpdateError("Projekt zatím nemá žádné vydání.") from exc
    except HttpError as exc:
        if exc.status in (403, 429):
            raise UpdateError(
                "GitHub teď další dotaz nepřijal – u nepřihlášených platí limit "
                "60 dotazů za hodinu. Zkus to za chvíli."
            ) from exc
        raise
    try:
        payload = resp.json()
    except ValueError as exc:
        raise UpdateError("GitHub vrátil odpověď, které nerozumím.") from exc
    return parse_release(payload)


def check_for_update(
    http: Http, current: str, *, token: CancelToken | None = None
) -> ReleaseInfo | None:
    """Vydání novější než ``current``, nebo ``None`` když je vše aktuální."""
    release = fetch_latest(http, token=token)
    running = AppVersion.try_parse(current)
    if running is None or release.version is None:
        # Neporovnatelné verze raději nehlásit jako aktualizaci.
        return None
    return release if release.version > running else None


# --------------------------------------------------------------------------- #
# Stažení
# --------------------------------------------------------------------------- #
ProgressFn = Callable[[int, int | None], None]


def is_frozen() -> bool:
    """True jen v ``.exe`` od PyInstalleru – jinde nemá co vyměňovat."""
    return bool(getattr(sys, "frozen", False))


def current_exe() -> Path:
    return Path(sys.executable).resolve()


def _writable(folder: Path) -> bool:
    try:
        handle, name = tempfile.mkstemp(dir=str(folder), prefix=".rosdl-wtest")
    except OSError:
        return False
    os.close(handle)
    Path(name).unlink(missing_ok=True)
    return True


def download_dir(exe: Path | None = None) -> Path:
    """Kam stahovat: vedle ``.exe``, aby byla výměna na stejném svazku
    okamžitá. Když se tam zapsat nedá (Program Files), použije se %TEMP%."""
    exe = exe or current_exe()
    if exe.parent.is_dir() and _writable(exe.parent):
        return exe.parent
    folder = Path(tempfile.gettempdir()) / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _download_name(release: ReleaseInfo) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]", "-", release.tag)
    return f"{APP_NAME}-{safe}.exe"


def _stream_to_part(
    http: Http,
    url: str,
    part: Path,
    progress: ProgressFn | None,
    token: CancelToken | None,
) -> tuple[str, int]:
    """Stáhne celý soubor do ``part``. Vrací (SHA256, počet bajtů)."""
    digest = hashlib.sha256()
    written = 0
    resp = http.stream_get(url, token=token)
    try:
        header = resp.headers.get("content-length")
        total = int(header) if header and header.isdigit() else None
        if progress is not None:
            progress(0, total)
        with part.open("wb") as fh:
            for chunk in resp.iter_bytes(CHUNK_SIZE):
                if token is not None:
                    token.raise_if_cancelled()
                fh.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                if progress is not None:
                    progress(written, total)
    except httpx.HTTPError as exc:
        # Pád spojení uprostřed těla neprojde přes Http.request, takže by
        # jinak probublal ven jako cizí výjimka a shodil celou aktualizaci.
        raise NetworkError(f"Přenos se přerušil: {exc}") from exc
    finally:
        resp.close()
    return digest.hexdigest(), written


def download_update(
    http: Http,
    release: ReleaseInfo,
    *,
    directory: Path | None = None,
    progress: ProgressFn | None = None,
    token: CancelToken | None = None,
    attempts: int = DOWNLOAD_ATTEMPTS,
) -> Path:
    """Stáhne ``.exe`` vydání a ověří ho. Vrací cestu k hotovému souboru."""
    if not release.asset_url:
        raise UpdateError(
            "Vydání neobsahuje soubor .exe – stáhni ho ručně ze stránky vydání."
        )
    folder = directory or download_dir()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / _download_name(release)
    part = dest.with_name(dest.name + PART_SUFFIX)

    last: NetworkError | None = None
    for attempt in range(attempts):
        if token is not None:
            token.raise_if_cancelled()
        if attempt:
            delay = BACKOFF[min(attempt - 1, len(BACKOFF) - 1)]
            if token is not None:
                if token.wait(delay):
                    raise Cancelled("Operace byla zrušena.")
            else:
                time.sleep(delay)
        try:
            actual, written = _stream_to_part(
                http, release.asset_url, part, progress, token
            )
        except NetworkError as exc:
            # Navazovat nemá smysl: vydání je jeden soubor a GitHub podepsané
            # odkazy přesměrovává, takže se stahuje znovu od začátku.
            last = exc
            part.unlink(missing_ok=True)
            continue
        except BaseException:
            part.unlink(missing_ok=True)
            raise

        if release.asset_size is not None and written != release.asset_size:
            part.unlink(missing_ok=True)
            raise SizeMismatch(dest.name, release.asset_size, written)
        if release.asset_sha256 is not None and actual != release.asset_sha256:
            part.unlink(missing_ok=True)
            raise ChecksumMismatch(dest.name, release.asset_sha256, actual)

        dest.unlink(missing_ok=True)
        part.replace(dest)
        return dest

    raise last if last is not None else NetworkError(release.asset_url)


# --------------------------------------------------------------------------- #
# Výměna běžícího souboru
# --------------------------------------------------------------------------- #
def backup_path(exe: Path) -> Path:
    return exe.with_name(exe.name + BACKUP_SUFFIX)


def cleanup_backups(exe: Path | None = None) -> None:
    """Smaže zbytky po minulé aktualizaci. Volá se chvíli po startu, kdy už
    předchozí proces skončil a soubor nedrží."""
    exe = exe or current_exe()
    for leftover in exe.parent.glob(exe.name + "*" + BACKUP_SUFFIX):
        try:
            leftover.unlink()
        except OSError:
            pass  # Ještě běží starý proces; smaže se při příštím spuštění.


def install_update(new_file: Path, exe: Path | None = None) -> Path:
    """Zamění běžící ``.exe`` za stažený. Vrací cestu k odložené záloze.

    Windows běžící soubor nesmaže, **přejmenovat** ho ale dovolí – originál
    se odsune stranou jako ``.old`` a na jeho místo přijde nová verze.
    Když se výměna v půlce nepovede, původní soubor se vrátí zpátky.
    """
    exe = exe or current_exe()
    if not new_file.is_file():
        raise UpdateError(f"Stažený soubor chybí: {new_file}")

    backup = backup_path(exe)
    if backup.exists():
        try:
            backup.unlink()
        except OSError:
            # Zbytek po minulé aktualizaci ještě někdo drží – uhneme vedle.
            backup = exe.with_name(f"{exe.name}.{int(time.time())}{BACKUP_SUFFIX}")

    try:
        exe.rename(backup)
    except OSError as exc:
        raise UpdateError(
            f"Nepodařilo se odsunout původní soubor ({exc}).\n"
            "Spusť aplikaci ze složky, kam smíš zapisovat, nebo si novou verzi "
            "stáhni ručně ze stránky vydání."
        ) from exc

    try:
        os.replace(new_file, exe)
    except OSError:
        # Přes hranici svazku os.replace neumí – tam se musí kopírovat.
        try:
            shutil.move(str(new_file), str(exe))
        except OSError as exc:
            backup.rename(exe)
            raise UpdateError(
                f"Novou verzi se nepodařilo nasadit ({exc}). Původní zůstala."
            ) from exc
    return backup


#: Nový proces nesmí viset na konzoli ani na skupině toho starého, jinak by
#: ho ukončení původní aplikace vzalo s sebou.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def relaunch(exe: Path | None = None) -> None:
    """Spustí aplikaci znovu, odpojenou od končícího procesu."""
    exe = exe or current_exe()
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True, **kwargs)
    except OSError as exc:
        raise UpdateError(f"Novou verzi se nepodařilo spustit: {exc}") from exc
