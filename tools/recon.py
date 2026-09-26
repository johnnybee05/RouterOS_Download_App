"""Průzkumný skript, kterým byla ověřena zjištění v docs/ENDPOINTS.md.

Není součástí aplikace – slouží k tomu, aby se dala zjištění kdykoli zopakovat
(např. až MikroTik něco změní). Závislost: pouze `requests`.

Použití:
    python tools/recon.py newest                 # NEWEST* endpointy
    python tools/recon.py arch 7.24.4            # které architektury existují
    python tools/recon.py arch 6.49.22
    python tools/recon.py zip <url all_packages> # obsah ZIPu přes HTTP Range
    python tools/recon.py versions 7             # enumerace verzí přes CHANGELOG
    python tools/recon.py sha256 7.24.4 calea-7.24.4-arm64.npk
    python tools/recon.py all                    # vše podstatné
"""

from __future__ import annotations

import struct
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

DOWNLOAD = "https://download.mikrotik.com/routeros"
UPGRADE = "https://upgrade.mikrotik.com/routeros"
UA = "RosDownloader-recon/0.1 (+https://github.com/)"
ARCHS = ["x86", "arm", "arm64", "mipsbe", "mmips", "smips", "ppc", "tile"]

S = requests.Session()
S.headers["User-Agent"] = UA


# --------------------------------------------------------------------------- #
# NEWEST
# --------------------------------------------------------------------------- #
def newest() -> None:
    for prefix in ("NEWESTa7", "NEWEST7", "NEWEST6", "NEWESTa6"):
        for channel in ("stable", "long-term", "testing", "development"):
            url = f"{UPGRADE}/{prefix}.{channel}"
            r = S.get(url, timeout=20)
            body = r.text.strip() if r.ok else ""
            print(f"{r.status_code}  {prefix}.{channel:<12} {body}")
        print()


# --------------------------------------------------------------------------- #
# Architektury
# --------------------------------------------------------------------------- #
def main_candidates(version: str, arch: str) -> list[str]:
    """Všechny tvary jména hlavního balíčku, které mají smysl zkusit."""
    if version.startswith("6."):
        return [
            f"routeros-{arch}-{version}.npk",
            f"routeros-powerpc-{version}.npk" if arch == "ppc" else "",
            f"routeros-{version}.npk" if arch == "x86" else "",
        ]
    return [
        f"routeros-{version}-{arch}.npk",
        f"routeros-{version}.npk" if arch == "x86" else "",
    ]


def arch_report(version: str) -> None:
    def check(name: str) -> tuple[str, int, int]:
        r = S.head(f"{DOWNLOAD}/{version}/{name}", timeout=20)
        return name, r.status_code, int(r.headers.get("Content-Length", 0))

    names = [n for a in ARCHS for n in main_candidates(version, a) if n]
    names += [f"all_packages-{a}-{version}.zip" for a in ARCHS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, code, size in pool.map(check, names):
            mark = "OK " if code == 200 else "   "
            print(f"{mark}{code}  {size:>12}  {name}")


# --------------------------------------------------------------------------- #
# ZIP central directory přes HTTP Range
# --------------------------------------------------------------------------- #
EOCD_SIG = b"PK\x05\x06"
EOCD64_LOCATOR_SIG = b"PK\x06\x07"
CD_SIG = b"PK\x01\x02"


def zip_listing(url: str, tail_bytes: int = 65536) -> list[dict]:
    head = S.head(url, timeout=30)
    head.raise_for_status()
    size = int(head.headers["Content-Length"])
    start = max(0, size - tail_bytes)
    tail = S.get(url, headers={"Range": f"bytes={start}-"}, timeout=30).content

    i = tail.rfind(EOCD_SIG)
    if i < 0:
        raise ValueError("EOCD nenalezena v posledních %d B" % tail_bytes)
    _, _, _, entries, cd_size, cd_off, _ = struct.unpack_from("<HHHHIIH", tail, i + 4)
    if tail.rfind(EOCD64_LOCATOR_SIG) >= 0:
        print("  ! archiv používá ZIP64 – potřeba rozšířené parsování")

    if start <= cd_off and cd_off + cd_size <= start + len(tail):
        cd = tail[cd_off - start : cd_off - start + cd_size]
    else:
        cd = S.get(
            url, headers={"Range": f"bytes={cd_off}-{cd_off + cd_size - 1}"}, timeout=30
        ).content

    out: list[dict] = []
    off = 0
    while len(out) < entries and cd[off : off + 4] == CD_SIG:
        (
            _, _, _, method, _, _, _, csize, usize, nlen, elen, clen, _, _, _, _
        ) = struct.unpack_from("<HHHHHHIIIHHHHHII", cd, off + 4)
        out.append(
            {
                "name": cd[off + 46 : off + 46 + nlen].decode("utf-8", "replace"),
                "size": usize,          # nekomprimovaná = skutečná velikost .npk
                "csize": csize,
                "method": method,
            }
        )
        off += 46 + nlen + elen + clen
    return out


# --------------------------------------------------------------------------- #
# Enumerace verzí přes CHANGELOG
# --------------------------------------------------------------------------- #
def changelog_exists(version: str) -> bool:
    return S.head(f"{UPGRADE}/{version}/CHANGELOG", timeout=20).status_code == 200


def versions(major: str, max_minor: int = 30, max_patch: int = 12) -> list[str]:
    cand = [f"{major}.{m}" for m in range(max_minor + 1)]
    cand += [
        f"{major}.{m}.{p}"
        for m in range(max_minor + 1)
        for p in range(1, max_patch + 1)
    ]
    with ThreadPoolExecutor(max_workers=10) as pool:
        found = [v for v, ok in zip(cand, pool.map(changelog_exists, cand)) if ok]
    return sorted(found, key=lambda v: [int(x) for x in v.split(".")])


# --------------------------------------------------------------------------- #
def sha256_sidecar(version: str, filename: str) -> None:
    r = S.get(f"{DOWNLOAD}/{version}/{filename}.sha256", timeout=20)
    print(f"{r.status_code}  {r.text.strip()!r}")


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "all":
        print("=== NEWEST ===");           newest()
        print("=== 7.24.4 ===");           arch_report("7.24.4")
        print("=== 6.49.22 ===");          arch_report("6.49.22")
        print("=== zip 7.24.4/arm64 ===")
        for e in zip_listing(f"{DOWNLOAD}/7.24.4/all_packages-arm64-7.24.4.zip"):
            print(f"  {e['name']:<44} {e['size']:>10}  method={e['method']}")
        return 0

    cmd, *rest = argv
    if cmd == "newest":
        newest()
    elif cmd == "arch":
        arch_report(rest[0])
    elif cmd == "zip":
        for e in zip_listing(rest[0]):
            print(f"{e['name']:<44} {e['size']:>10}  csize={e['csize']:>10} method={e['method']}")
    elif cmd == "versions":
        print(" ".join(versions(rest[0])))
    elif cmd == "sha256":
        sha256_sidecar(rest[0], rest[1])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
