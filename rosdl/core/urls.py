"""Sestavování URL podle skutečných pravidel MikroTiku.

Pravidla jsou ověřená HTTP dotazy, ne odhadnutá – detaily a důkazy v docs/ENDPOINTS.md.
Tři místa, kde se dá snadno chybovat a která proto mají vlastní testy:

* v7 hlavní balíček pro **x86 nemá** příponu architektury,
* v6 hlavní balíček pro **x86 příponu má**,
* v6 hlavní balíček pro PowerPC používá token ``powerpc``, zatímco archiv
  a extra balíčky téže architektury používají ``ppc``.
"""

from __future__ import annotations

from .models import Channel, Version

DOWNLOAD_HOST = "https://download.mikrotik.com"
UPGRADE_HOST = "https://upgrade.mikrotik.com"

#: Zrcadla se stejným obsahem; použijí se, když primární host selže.
MIRROR_HOSTS: tuple[str, ...] = (DOWNLOAD_HOST, UPGRADE_HOST, "https://cdn.mikrotik.com")


def base_url(version: Version | str, host: str = DOWNLOAD_HOST) -> str:
    return f"{host}/routeros/{version}"


def file_url(version: Version | str, filename: str, host: str = DOWNLOAD_HOST) -> str:
    return f"{base_url(version, host)}/{filename}"


def sha256_url(url: str) -> str:
    return url + ".sha256"


def changelog_url(version: Version | str, host: str = UPGRADE_HOST) -> str:
    return f"{base_url(version, host)}/CHANGELOG"


# --------------------------------------------------------------------------- #
# Nejnovější verze v kanálu
# --------------------------------------------------------------------------- #
def newest_url(major: int, channel: Channel | str, host: str = UPGRADE_HOST) -> str:
    """URL souboru s nejnovější verzí kanálu.

    Pro v7 je to ``NEWESTa7.<kanál>``; starší ``NEWEST7.*`` se od 7.12.1 (2023)
    neaktualizuje a nepoužíváme ho vůbec.
    """
    ch = Channel(channel).value
    prefix = "NEWESTa7" if int(major) >= 7 else "NEWEST6"
    return f"{host}/routeros/{prefix}.{ch}"


# --------------------------------------------------------------------------- #
# Názvy souborů
# --------------------------------------------------------------------------- #
def _arch_suffix(arch: str) -> str:
    """Přípona architektury u balíčku. x86 ji nemá – jeho soubory jsou bez ní."""
    return "" if arch == "x86" else f"-{arch}"


def main_arch_token(version: Version, arch: str) -> str:
    """Token architektury v názvu **hlavního** balíčku v6.

    Jen tady se PowerPC jmenuje ``powerpc``; archiv i extras používají ``ppc``.
    """
    if version.major <= 6 and arch == "ppc":
        return "powerpc"
    return arch


def main_package_name(version: Version, arch: str) -> str:
    """Název hlavního balíčku (``routeros``) pro danou verzi a architekturu."""
    if version.major >= 7:
        return f"routeros-{version}{_arch_suffix(arch)}.npk"
    # v6 má obrácené pořadí a x86 příponu NEmá vynechanou.
    return f"routeros-{main_arch_token(version, arch)}-{version}.npk"


def extra_package_name(package: str, version: Version, arch: str) -> str:
    """Název extra balíčku. Pořadí ``<pkg>-<verze>-<arch>`` platí pro v6 i v7."""
    return f"{package}-{version}{_arch_suffix(arch)}.npk"


def all_packages_zip_name(version: Version, arch: str) -> str:
    """Název archivu se všemi balíčky. Tady se ``x86`` v názvu používá vždy."""
    return f"all_packages-{arch}-{version}.zip"


# --------------------------------------------------------------------------- #
# Zpětný převod: název souboru -> jméno balíčku
# --------------------------------------------------------------------------- #
def package_from_filename(filename: str, version: Version, arch: str) -> str | None:
    """Z názvu souboru v archivu vytáhne krátké jméno balíčku.

    ``container-7.24.4-arm64.npk`` -> ``container``,
    ``container-7.24.4.npk``       -> ``container`` (x86).
    Vrací None, pokud jméno neodpovídá očekávanému tvaru.
    """
    if not filename.endswith(".npk"):
        return None
    stem = filename[: -len(".npk")]
    suffix = f"-{version}{_arch_suffix(arch)}"
    if not stem.endswith(suffix):
        return None
    package = stem[: -len(suffix)]
    return package or None
