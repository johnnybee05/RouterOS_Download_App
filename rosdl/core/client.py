"""Klient pro zjišťování verzí, changelogu a seznamu balíčků."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from . import urls
from .cache import JsonCache
from .errors import NotFoundError, RosdlError, ZipIndexError
from .http import CancelToken, Http
from .models import (
    ArchPackages,
    Channel,
    PackageEntry,
    PackageKind,
    RemoteFile,
    Version,
)
from .zipindex import read_remote_zip_index

#: Kandidáti pro záložní HEAD sondáž, když archiv chybí. Sjednocení všeho,
#: co MikroTik kdy publikoval jako samostatný balíček ve v6 i v7.
CANDIDATE_PACKAGES: tuple[str, ...] = (
    "advanced-tools",
    "calea",
    "container",
    "dhcp",
    "dude",
    "extra-nic",
    "gps",
    "hotspot",
    "iot",
    "iot-bt-extra",
    "ipv6",
    "kvm",
    "lcd",
    "lora",
    "mpls",
    "multicast",
    "netinstall",
    "ntp",
    "openflow",
    "ppp",
    "rose-storage",
    "routing",
    "security",
    "switch-marvell",
    "system",
    "tr069-client",
    "ups",
    "user-manager",
    "wifi-qcom",
    "wifi-qcom-ac",
    "wifi-qcom-be",
    "wireless",
    "zerotier",
)

MAX_PARALLEL_PROBES = 8
VERSIONS_CACHE_TTL = 24 * 3600.0
PACKAGES_CACHE_TTL = 7 * 24 * 3600.0

_NEWEST_RE = re.compile(r"^\s*(?P<version>\S+)(?:\s+(?P<ts>\d+))?\s*$")


@dataclass(frozen=True)
class NewestInfo:
    version: Version
    released: datetime | None

    @property
    def released_text(self) -> str:
        return self.released.strftime("%d.%m.%Y") if self.released else "—"


def parse_newest(text: str, expected_major: int) -> NewestInfo:
    """Rozparsuje odpověď ``NEWEST*`` ve tvaru ``7.24.4 1789558341``.

    Kontrola majoru není kosmetická: ``NEWEST6.testing`` vrací HTTP 200
    s obsahem ``7.12.1``, tedy zbytek po v7. Bez této kontroly by uživatel
    dostal v režimu v6 verzi v7.
    """
    match = _NEWEST_RE.match(text)
    if not match:
        raise RosdlError(f"Nečekaný tvar odpovědi NEWEST: {text!r}")

    version = Version.try_parse(match.group("version"))
    if version is None:
        raise RosdlError(f"Nečekaný tvar verze v odpovědi NEWEST: {text!r}")
    if version.major != expected_major:
        raise RosdlError(
            f"Kanál vrátil verzi {version} (major {version.major}), "
            f"očekáván major {expected_major}. Kanál pro tuto řadu neexistuje."
        )

    ts = match.group("ts")
    released = (
        datetime.fromtimestamp(int(ts), tz=UTC) if ts and int(ts) > 0 else None
    )
    return NewestInfo(version=version, released=released)


class MikrotikClient:
    """Vše, co se dá o RouterOS zjistit přes HTTP. Bez závislosti na Qt."""

    def __init__(
        self,
        http: Http | None = None,
        *,
        versions_cache: JsonCache | None = None,
        packages_cache: JsonCache | None = None,
    ) -> None:
        self.http = http or Http()
        self._versions_cache = versions_cache
        self._packages_cache = packages_cache

    @property
    def versions_cache(self) -> JsonCache:
        if self._versions_cache is None:
            self._versions_cache = JsonCache("versions.json", VERSIONS_CACHE_TTL)
        return self._versions_cache

    @property
    def packages_cache(self) -> JsonCache:
        if self._packages_cache is None:
            self._packages_cache = JsonCache("packages.json", PACKAGES_CACHE_TTL)
        return self._packages_cache

    def close(self) -> None:
        self.http.close()

    # ------------------------------------------------------------------ #
    # Verze
    # ------------------------------------------------------------------ #
    def newest(
        self, major: int, channel: Channel, *, token: CancelToken | None = None
    ) -> NewestInfo:
        url = urls.newest_url(major, channel)
        return parse_newest(self.http.get_text(url, token=token), major)

    def version_exists(
        self, version: Version | str, *, token: CancelToken | None = None
    ) -> bool:
        return self.http.exists(urls.changelog_url(version), token=token)

    def changelog(
        self, version: Version | str, *, token: CancelToken | None = None
    ) -> str:
        try:
            return self.http.get_text(urls.changelog_url(version), token=token)
        except NotFoundError:
            return f"Pro verzi {version} není changelog k dispozici."

    def list_versions(
        self,
        major: int,
        newest: Version,
        *,
        token: CancelToken | None = None,
        use_cache: bool = True,
        progress: Callable[[int, int], None] | None = None,
    ) -> list[Version]:
        """Zjistí historii verzí sondáží na ``CHANGELOG``.

        MikroTik nikde nepublikuje strojově čitelný seznam verzí – stránka
        download je Livewire aplikace, která ho dotahuje až AJAXem. Sondáž
        přes CHANGELOG je proto jediná spolehlivá cesta bez prohlížeče.
        Výsledek se cachuje, klíč obsahuje nejnovější verzi, takže nové
        vydání cache automaticky zneplatní.
        """
        key = f"{major}:{newest}"
        if use_cache:
            cached = self.versions_cache.get(key)
            if isinstance(cached, list):
                parsed = [Version.try_parse(v) for v in cached]
                found = [v for v in parsed if v is not None]
                if found:
                    return sorted(found, reverse=True)

        candidates = list(_version_candidates(major, newest))
        total = len(candidates)
        done = 0
        found_versions: list[Version] = []

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_PROBES) as pool:
            for version, exists in zip(
                candidates,
                pool.map(lambda v: self.version_exists(v, token=token), candidates),
            ):
                done += 1
                if progress is not None:
                    progress(done, total)
                if exists:
                    found_versions.append(version)

        if newest not in found_versions:
            found_versions.append(newest)
        found_versions.sort(reverse=True)
        self.versions_cache.set(key, [str(v) for v in found_versions])
        return found_versions

    # ------------------------------------------------------------------ #
    # Balíčky
    # ------------------------------------------------------------------ #
    def main_file(self, version: Version, arch: str) -> RemoteFile:
        name = urls.main_package_name(version, arch)
        return RemoteFile(
            name=name,
            url=urls.file_url(version, name),
            kind=PackageKind.MAIN,
            arch=arch,
            version=version,
            package="routeros",
        )

    def archive_file(self, version: Version, arch: str) -> RemoteFile:
        name = urls.all_packages_zip_name(version, arch)
        return RemoteFile(
            name=name,
            url=urls.file_url(version, name),
            kind=PackageKind.ARCHIVE,
            arch=arch,
            version=version,
            package="all_packages",
        )

    def extra_file(self, entry: PackageEntry, version: Version) -> RemoteFile:
        return RemoteFile(
            name=entry.filename,
            url=urls.file_url(version, entry.filename),
            kind=PackageKind.EXTRA,
            arch=entry.arch,
            version=version,
            size=entry.size,
            package=entry.package,
        )

    def list_packages(
        self,
        version: Version,
        arch: str,
        *,
        token: CancelToken | None = None,
        use_cache: bool = True,
    ) -> ArchPackages:
        """Zjistí extra balíčky pro verzi a architekturu.

        Primárně přečte Central Directory archivu ``all_packages`` přes Range
        (jeden HEAD + jeden Range místo desítek HEAD). Když archiv chybí nebo
        je nečitelný, spadne na paralelní HEAD sondáž kandidátů.
        """
        key = f"{version}:{arch}"
        if use_cache:
            cached = self.packages_cache.get(key)
            restored = _restore_packages(cached, version, arch)
            if restored is not None:
                return restored

        try:
            result = self._packages_from_zip(version, arch, token=token)
        except (ZipIndexError, NotFoundError):
            result = self._packages_from_probes(version, arch, token=token)

        self.packages_cache.set(key, _dump_packages(result))
        return result

    def _packages_from_zip(
        self, version: Version, arch: str, *, token: CancelToken | None
    ) -> ArchPackages:
        url = urls.file_url(version, urls.all_packages_zip_name(version, arch))
        entries: dict[str, PackageEntry] = {}
        for item in read_remote_zip_index(self.http, url, token=token):
            package = urls.package_from_filename(item.name, version, arch)
            if package is None or package == "routeros":
                continue
            entries[package] = PackageEntry(
                package=package, arch=arch, filename=item.name, size=item.size
            )
        return ArchPackages(arch=arch, version=version, entries=entries, source="zip")

    def _packages_from_probes(
        self, version: Version, arch: str, *, token: CancelToken | None
    ) -> ArchPackages:
        names = {
            pkg: urls.extra_package_name(pkg, version, arch)
            for pkg in CANDIDATE_PACKAGES
        }

        def probe(item: tuple[str, str]) -> tuple[str, str, int | None]:
            package, filename = item
            info = self.http.head(urls.file_url(version, filename), token=token)
            return package, filename, info.size if info.ok else None

        entries: dict[str, PackageEntry] = {}
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_PROBES) as pool:
            for package, filename, size in pool.map(probe, names.items()):
                if size is not None:
                    entries[package] = PackageEntry(
                        package=package, arch=arch, filename=filename, size=size
                    )
        return ArchPackages(arch=arch, version=version, entries=entries, source="head")

    # ------------------------------------------------------------------ #
    def fill_sizes(
        self, remotes: Sequence[RemoteFile], *, token: CancelToken | None = None
    ) -> list[RemoteFile]:
        """Doplní chybějící velikosti přes HEAD, aby celkový průběh seděl.

        Velikosti extras přicházejí zdarma z archivu; hlavní balíček a ZIP je
        nemají, takže se na ně pošle HEAD (paralelně, max 8).
        """
        missing = [r for r in remotes if r.size is None]
        if not missing:
            return list(remotes)

        def probe(remote: RemoteFile) -> tuple[str, int | None]:
            info = self.http.head(remote.url, token=token)
            return remote.url, info.size if info.ok else None

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_PROBES) as pool:
            sizes = dict(pool.map(probe, missing))

        return [
            replace(r, size=sizes[r.url])
            if r.size is None and sizes.get(r.url) is not None
            else r
            for r in remotes
        ]

    def fetch_sha256(
        self, remote: RemoteFile, *, token: CancelToken | None = None
    ) -> str | None:
        """Stáhne sidecar ``.sha256``. None = server ho pro soubor nemá."""
        try:
            text = self.http.get_text(remote.sha256_url, token=token)
        except NotFoundError:
            return None
        return parse_sha256_sidecar(text)


def parse_sha256_sidecar(text: str) -> str | None:
    """Z obsahu ``<hash>  <název souboru>`` vytáhne hash."""
    for line in text.splitlines():
        parts = line.split()
        if parts and len(parts[0]) == 64:
            candidate = parts[0].lower()
            if all(c in "0123456789abcdef" for c in candidate):
                return candidate
    return None


# ---------------------------------------------------------------------- #
# Pomocné funkce
# ---------------------------------------------------------------------- #
#: Nejvyšší známý patch je 7.20.8, nejvyšší beta 7.25beta5 – s rezervou.
MAX_PATCH = 12
MAX_PRERELEASE = 10
#: Předrelease se sondují jen u nejnovější a předchozí minor verze; starší
#: bety MikroTik ze serveru odstraňuje a sondovat je všechny by bylo zbytečné.
PRERELEASE_MINORS = 2


def _version_candidates(major: int, newest: Version) -> Iterable[Version]:
    """Kandidáti pro sondáž: každá minor od nejnovější dolů + její patche.

    Minor verze jdou od nejnovější dolů k ``.0``. U dvou nejnovějších minorů
    se navíc sondují bety a rc, aby byl použitelný kanál development – ten
    jako nejnovější hlásí např. ``7.25beta5``.
    """
    for minor in range(newest.minor, -1, -1):
        yield Version(major=major, minor=minor)
        for patch in range(1, MAX_PATCH + 1):
            yield Version(major=major, minor=minor, patch=patch)
        if newest.minor - minor < PRERELEASE_MINORS:
            for kind in ("beta", "rc"):
                for num in range(1, MAX_PRERELEASE + 1):
                    yield Version(
                        major=major, minor=minor, pre_kind=kind, pre_num=num
                    )


def filter_for_channel(
    versions: Sequence[Version], channel: Channel
) -> list[Version]:
    """Bety a rc dávají smysl jen v kanálech testing a development."""
    if channel in (Channel.DEVELOPMENT, Channel.TESTING):
        return list(versions)
    return [v for v in versions if not v.is_prerelease]


def _dump_packages(result: ArchPackages) -> dict[str, object]:
    return {
        "source": result.source,
        "entries": [
            {"package": e.package, "filename": e.filename, "size": e.size}
            for e in result.entries.values()
        ],
    }


def _restore_packages(
    raw: object, version: Version, arch: str
) -> ArchPackages | None:
    if not isinstance(raw, dict):
        return None
    items = raw.get("entries")
    if not isinstance(items, list):
        return None
    entries: dict[str, PackageEntry] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        package = item.get("package")
        filename = item.get("filename")
        if not isinstance(package, str) or not isinstance(filename, str):
            continue
        size = item.get("size")
        entries[package] = PackageEntry(
            package=package,
            arch=arch,
            filename=filename,
            size=size if isinstance(size, int) else None,
        )
    if not entries:
        return None
    source = raw.get("source")
    return ArchPackages(
        arch=arch,
        version=version,
        entries=entries,
        source=source if isinstance(source, str) else "zip",
    )
