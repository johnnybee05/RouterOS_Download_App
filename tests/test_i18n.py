"""Překlady: úplnost katalogů, plurály, formáty a volba jazyka.

Nejcennější je tady test parity klíčů – překlad se přidává ručně a zapomenout
jeden klíč je nejsnazší chyba, kterou lze v i18n udělat.
"""

from __future__ import annotations

import string

import pytest

from rosdl import i18n
from rosdl.core.config import Settings, resolve_language
from rosdl.core.models import arch_label
from rosdl.core.util import (
    architectures_count,
    files_count,
    human_duration,
    human_size,
    human_speed,
    packages_count,
    versions_count,
)

CATALOGS = {code: i18n._catalog(code) for code in i18n.available_languages()}


def _placeholders(value: str | dict[str, str]) -> set[str]:
    texts = value.values() if isinstance(value, dict) else [value]
    names: set[str] = set()
    for text in texts:
        for _, field, _, _ in string.Formatter().parse(text):
            if field:
                names.add(field)
    return names


# --------------------------------------------------------------------------- #
# Katalogy
# --------------------------------------------------------------------------- #
def test_every_language_has_a_catalog() -> None:
    assert set(CATALOGS) == set(i18n.LANGUAGES)


@pytest.mark.parametrize("code", sorted(i18n.available_languages()))
def test_catalogs_have_the_same_keys(code: str) -> None:
    """Chybějící klíč by se v aplikaci projevil až výpisem samotného klíče."""
    reference = CATALOGS[i18n.FALLBACK_LANGUAGE].MESSAGES
    assert set(CATALOGS[code].MESSAGES) == set(reference)


@pytest.mark.parametrize("code", sorted(i18n.available_languages()))
def test_placeholders_match_the_fallback(code: str) -> None:
    """Přebytečný ``{placeholder}`` v překladu = ``KeyError`` za běhu."""
    reference = CATALOGS[i18n.FALLBACK_LANGUAGE].MESSAGES
    mismatched = {
        key: (_placeholders(value), _placeholders(reference[key]))
        for key, value in CATALOGS[code].MESSAGES.items()
        if _placeholders(value) != _placeholders(reference[key])
    }
    assert mismatched == {}


@pytest.mark.parametrize("code", sorted(i18n.available_languages()))
def test_plural_entries_cover_every_form(code: str) -> None:
    """Každý plurál musí mít tvar pro 1, 2 i 5 – jinak by se sáhlo vedle."""
    catalog = CATALOGS[code]
    plural_keys = [
        key for key, value in catalog.MESSAGES.items() if isinstance(value, dict)
    ]
    assert plural_keys, "katalog nemá žádný plurál – něco se rozpadlo"
    for key in plural_keys:
        forms = catalog.MESSAGES[key]
        needed = {catalog.plural_form(n) for n in (0, 1, 2, 5, 11, 101)}
        assert needed <= set(forms), f"{code}/{key}: chybí {needed - set(forms)}"


# --------------------------------------------------------------------------- #
# Vyhledávání a náhradní jazyk
# --------------------------------------------------------------------------- #
def test_unknown_key_returns_itself() -> None:
    assert i18n.t("nic.takoveho.neexistuje") == "nic.takoveho.neexistuje"


def test_missing_key_falls_back_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    czech = dict(CATALOGS["cs"].MESSAGES)
    czech.pop("ui.download")
    monkeypatch.setattr(CATALOGS["cs"], "MESSAGES", czech)
    i18n.set_language("cs")
    assert i18n.t("ui.download") == "Download"


def test_broken_placeholder_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Překlep v překladu smí ukázat ošklivý text, ne shodit aplikaci."""
    czech = dict(CATALOGS["cs"].MESSAGES)
    czech["ui.released_on"] = "vydáno {datum}"  # správně je {date}
    monkeypatch.setattr(CATALOGS["cs"], "MESSAGES", czech)
    i18n.set_language("cs")
    assert i18n.t("ui.released_on", date="1.1.2026") == "vydáno {datum}"


def test_language_change_notifies_listeners() -> None:
    seen: list[str] = []
    i18n.on_language_changed(seen.append)
    try:
        i18n.set_language("en")
        i18n.set_language("cs")
        assert seen == ["en", "cs"]
    finally:
        i18n._listeners.remove(seen.append)


# --------------------------------------------------------------------------- #
# Plurály a formáty
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 soubor"), (2, "2 soubory"), (4, "4 soubory"), (5, "5 souborů"),
     (0, "0 souborů"), (21, "21 souborů")],
)
def test_czech_plurals(count: int, expected: str) -> None:
    i18n.set_language("cs")
    assert files_count(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"), [(0, "0 files"), (1, "1 file"), (5, "5 files")]
)
def test_english_plurals(count: int, expected: str) -> None:
    i18n.set_language("en")
    assert files_count(count) == expected


def test_other_counters_follow_the_language() -> None:
    i18n.set_language("cs")
    assert packages_count(3) == "3 balíčky"
    assert versions_count(7) == "7 verzí"
    assert architectures_count(2) == "2 architektury"
    i18n.set_language("en")
    assert packages_count(3) == "3 packages"
    assert versions_count(7) == "7 versions"
    assert architectures_count(2) == "2 architectures"


def test_decimal_separator_follows_the_language() -> None:
    i18n.set_language("cs")
    assert human_size(13_934_949) == "13,3 MB"
    assert human_speed(1_536_000) == "1,5 MB/s"
    i18n.set_language("en")
    assert human_size(13_934_949) == "13.3 MB"
    assert human_speed(1_536_000) == "1.5 MB/s"


def test_bytes_and_unknown_size_are_translated() -> None:
    i18n.set_language("cs")
    assert human_size(512) == "512 B"
    assert human_size(None) == "—"
    assert human_duration(float("inf")) == "—"


def test_date_format_differs() -> None:
    from datetime import date

    from rosdl.core.client import format_date

    i18n.set_language("cs")
    assert format_date(date(2026, 9, 16)) == "16.09.2026"
    i18n.set_language("en")
    assert format_date(date(2026, 9, 16)) == "2026-09-16"


def test_arch_labels_are_translated() -> None:
    i18n.set_language("cs")
    assert "virtuální stroje" in arch_label("x86")
    i18n.set_language("en")
    assert "virtual machines" in arch_label("x86")
    assert arch_label("neznámá") == ""


# --------------------------------------------------------------------------- #
# Detekce a normalizace
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("cs", "cs"),
        ("cs_CZ", "cs"),
        ("cs-CZ", "cs"),
        ("cs_CZ.UTF-8", "cs"),
        ("EN-us", "en"),
        ("de", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize(value: str | None, expected: str | None) -> None:
    assert i18n.normalize(value) == expected


def test_env_overrides_system_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROSDL_LANG", "en")
    assert i18n.detect_system_language() == "en"
    monkeypatch.setenv("ROSDL_LANG", "cs_CZ")
    assert i18n.detect_system_language() == "cs"


def test_unknown_system_language_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ROSDL_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(i18n, "_windows_ui_language", lambda: "de-DE")
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("German_Germany", "1252"))
    assert i18n.detect_system_language() == "en"


# --------------------------------------------------------------------------- #
# Nastavení
# --------------------------------------------------------------------------- #
def test_settings_keep_a_known_language() -> None:
    settings = Settings(language="en")
    settings.normalize()
    assert settings.language == "en"


def test_settings_reduce_a_regional_code() -> None:
    settings = Settings(language="cs_CZ")
    settings.normalize()
    assert settings.language == "cs"


def test_settings_drop_an_unsupported_language() -> None:
    """Prázdno znamená „podle systému“ – lepší než mlčky psát německy."""
    settings = Settings(language="de")
    settings.normalize()
    assert settings.language == ""


def test_settings_default_to_automatic() -> None:
    assert Settings().language == ""


def test_resolve_language_prefers_the_stored_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(i18n, "detect_system_language", lambda: "cs")
    monkeypatch.setattr(
        "rosdl.core.config.detect_system_language", lambda: "cs"
    )
    assert resolve_language("en") == "en"
    assert resolve_language("") == "cs"


def test_settings_roundtrip_keeps_the_language(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "settings.json"
    Settings(language="en").save(path)
    assert Settings.load(path).language == "en"
