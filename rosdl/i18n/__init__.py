"""Překlady bez závislosti na Qt.

Jádro, CLI i GUI sahají na texty přes :func:`t` a :func:`tn`. Katalogy jsou
obyčejné moduly (``cs.py``, ``en.py``), takže je PyInstaller zabalí sám –
žádná data navíc ve ``.spec``.

Angličtina je záchranná síť: chybí-li klíč v aktivním jazyce, sáhne se do ní,
a teprve pak se vrátí samotný klíč. Aplikace tak nikdy nespadne na překlepu
v názvu klíče, jen ukáže ošklivý text.
"""

from __future__ import annotations

import locale
import os
import sys
from collections.abc import Callable
from importlib import import_module
from types import ModuleType

#: Kódy jazyků a jejich názvy v nich samotných – tak, jak se nabízejí v menu.
LANGUAGES: dict[str, str] = {
    "cs": "Čeština",
    "en": "English",
}

#: Do angličtiny se padá, když jazyk systému neznáme.
FALLBACK_LANGUAGE = "en"

_catalogs: dict[str, ModuleType] = {}
_current: str = FALLBACK_LANGUAGE
_listeners: list[Callable[[str], None]] = []


# --------------------------------------------------------------------------- #
# Katalogy
# --------------------------------------------------------------------------- #
def _catalog(code: str) -> ModuleType:
    module = _catalogs.get(code)
    if module is None:
        module = import_module(f"{__name__}.{code}")
        _catalogs[code] = module
    return module


def available_languages() -> tuple[str, ...]:
    """Kódy jazyků v pořadí, v jakém se mají nabízet."""
    return tuple(LANGUAGES)


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def current_language() -> str:
    return _current


def normalize(code: str | None) -> str | None:
    """``cs_CZ.UTF-8`` -> ``cs``. None, když jazyk neumíme."""
    if not code:
        return None
    primary = code.replace("-", "_").split("_", 1)[0].split(".", 1)[0].lower()
    return primary if primary in LANGUAGES else None


def set_language(code: str | None) -> str:
    """Přepne jazyk a ohlásí to posluchačům. Vrací kód, který opravdu platí."""
    global _current
    resolved = normalize(code) or FALLBACK_LANGUAGE
    if resolved == _current:
        return resolved
    _current = resolved
    _catalog(resolved)  # ať se případná chyba v katalogu ozve hned
    for listener in list(_listeners):
        listener(resolved)
    return resolved


def on_language_changed(listener: Callable[[str], None]) -> None:
    """Zaregistruje callback volaný po každé změně jazyka."""
    _listeners.append(listener)


# --------------------------------------------------------------------------- #
# Zjištění jazyka systému
# --------------------------------------------------------------------------- #
def detect_system_language() -> str:
    """Jazyk Windows (nebo ``LANG``), když ho umíme. Jinak angličtina.

    Proměnné prostředí mají přednost před systémem – na nich se dá jazyk
    vynutit i tomu, kdo aplikaci pouští ze skriptu.
    """
    for name in ("ROSDL_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        code = normalize(os.environ.get(name))
        if code is not None:
            return code

    if sys.platform == "win32":
        code = normalize(_windows_ui_language())
        if code is not None:
            return code

    try:
        code = normalize(locale.getlocale()[0])
    except (ValueError, TypeError, IndexError, AttributeError):
        code = None
    return code or FALLBACK_LANGUAGE


def _windows_ui_language() -> str | None:
    """Jazyk rozhraní Windows, ne formát čísel a dat.

    ``locale.getlocale`` vrací formátovací locale, což je něco jiného:
    anglické Windows s českým formátem data by kvůli němu mluvila česky.
    """
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(85)
        size = ctypes.c_ulong(85)
        count = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetUserPreferredUILanguages(
            0x8,  # MUI_LANGUAGE_NAME
            ctypes.byref(count),
            buffer,
            ctypes.byref(size),
        )
        if ok and buffer[0]:
            return buffer.value or buffer[:].split("\x00", 1)[0]
    except (OSError, AttributeError, ImportError):
        pass
    return None


# --------------------------------------------------------------------------- #
# Vyhledání textu
# --------------------------------------------------------------------------- #
def _lookup(key: str) -> object | None:
    for code in (_current, FALLBACK_LANGUAGE):
        try:
            value = _catalog(code).MESSAGES.get(key)
        except (ImportError, AttributeError):
            continue
        if value is not None:
            return value
    return None


def t(key: str, /, **kwargs: object) -> str:
    """Text podle klíče, volitelně s dosazenými ``{placeholdery}``."""
    value = _lookup(key)
    if value is None:
        return key
    if isinstance(value, dict):  # plurál volaný přes t() – vezmi „other“
        value = value.get("other") or next(iter(value.values()))
    text = str(value)
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # Rozbitý placeholder v překladu nesmí shodit aplikaci.
        return text


def tn(key: str, count: int, /, **kwargs: object) -> str:
    """Text ve tvaru podle počtu: ``tn("count.files", 5)`` -> ``5 souborů``.

    Tvar vybírá katalog jazyka, ne volající – čeština má tři
    (1 / 2–4 / 5+), angličtina dvě.
    """
    value = _lookup(key)
    if value is None:
        return f"{count} {key}"
    if not isinstance(value, dict):
        return t(key, n=count, **kwargs)

    for code in (_current, FALLBACK_LANGUAGE):
        try:
            form = _catalog(code).plural_form(count)
        except (ImportError, AttributeError):
            continue
        text = value.get(form)
        if text is not None:
            break
    else:
        text = None
    if text is None:
        text = value.get("other") or next(iter(value.values()))
    try:
        return str(text).format(n=count, **kwargs)
    except (KeyError, IndexError, ValueError):
        return str(text)


def date_format() -> str:
    """``strftime`` maska pro datum v aktivním jazyce."""
    return t("format.date")


def decimal_separator() -> str:
    return t("format.decimal")


__all__ = [
    "FALLBACK_LANGUAGE",
    "LANGUAGES",
    "available_languages",
    "current_language",
    "date_format",
    "decimal_separator",
    "detect_system_language",
    "language_name",
    "normalize",
    "on_language_changed",
    "set_language",
    "t",
    "tn",
]
