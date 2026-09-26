"""Motivy: barvy na jednom místě, přepínání za běhu, tmavý titulkový pruh.

Všechny barvy jsou tady – ve zbytku GUI se nesmí objevit natvrdo zapsaný
hexadecimální kód. Widgety, které potřebují víc než QPalette (log, progress
bar, seznamy), berou barvy ze stylesheetu složeného z týchž tokenů.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

ThemeMode = Literal["system", "light", "dark"]
MODE_LABELS: dict[ThemeMode, str] = {
    "system": "Systém",
    "light": "Světlý",
    "dark": "Tmavý",
}


@dataclass(frozen=True)
class Tokens:
    """Barevná sada jednoho motivu."""

    dark: bool
    window: str
    window_text: str
    base: str
    alternate_base: str
    text: str
    disabled_text: str
    button: str
    button_text: str
    border: str
    accent: str
    accent_text: str
    accent_hover: str
    tooltip_base: str
    tooltip_text: str
    selection_bg: str
    selection_text: str
    progress_chunk: str
    log_bg: str
    log_info: str
    log_success: str
    log_warning: str
    log_error: str
    muted_text: str


LIGHT = Tokens(
    dark=False,
    window="#f4f5f7",
    window_text="#1b1d21",
    base="#ffffff",
    alternate_base="#f7f8fa",
    text="#1b1d21",
    disabled_text="#9aa0a6",
    button="#eceef1",
    button_text="#1b1d21",
    border="#ccd0d6",
    accent="#1668c8",
    accent_text="#ffffff",
    accent_hover="#1a79e6",
    tooltip_base="#ffffff",
    tooltip_text="#1b1d21",
    selection_bg="#1668c8",
    selection_text="#ffffff",
    progress_chunk="#1668c8",
    log_bg="#ffffff",
    log_info="#40454d",
    log_success="#1a7a3c",
    log_warning="#8a5a00",
    log_error="#b3261e",
    muted_text="#6b7280",
)

DARK = Tokens(
    dark=True,
    window="#1e2024",
    window_text="#e6e8ea",
    base="#26292e",
    alternate_base="#2b2f35",
    text="#e6e8ea",
    disabled_text="#71767d",
    button="#2f333a",
    button_text="#e6e8ea",
    border="#3c414a",
    accent="#4b93f0",
    accent_text="#10141a",
    accent_hover="#68a6f5",
    tooltip_base="#33373e",
    tooltip_text="#e6e8ea",
    selection_bg="#33619b",
    selection_text="#ffffff",
    progress_chunk="#4b93f0",
    log_bg="#1a1c20",
    log_info="#c4c9cf",
    log_success="#6ed08c",
    log_warning="#e6b352",
    log_error="#ff7a72",
    muted_text="#9aa1aa",
)


# --------------------------------------------------------------------------- #
# Ikony – jedna SVG sada obarvená podle motivu
# --------------------------------------------------------------------------- #
_ICON_SVG: dict[str, str] = {
    "download": (
        '<path d="M12 3v10m0 0 4-4m-4 4-4-4" stroke="{c}" stroke-width="2" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="{c}" '
        'stroke-width="2" fill="none" stroke-linecap="round"/>'
    ),
    "cancel": (
        '<path d="M6 6l12 12M18 6L6 18" stroke="{c}" stroke-width="2" '
        'stroke-linecap="round"/>'
    ),
    "folder": (
        '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 '
        '1-2-2z" stroke="{c}" stroke-width="2" fill="none" stroke-linejoin="round"/>'
    ),
    "refresh": (
        '<path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5" stroke="{c}" stroke-width="2" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "check-all": (
        '<path d="M4 12l4 4L20 5" stroke="{c}" stroke-width="2" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M4 19h10" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
    ),
    "check-none": (
        '<rect x="4" y="5" width="16" height="14" rx="2" stroke="{c}" '
        'stroke-width="2" fill="none"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="9" stroke="{c}" stroke-width="2" fill="none"/>'
        '<path d="M12 11v5M12 7.5v.01" stroke="{c}" stroke-width="2" '
        'stroke-linecap="round"/>'
    ),
    "app": (
        '<path d="M12 2 3 7v10l9 5 9-5V7z" stroke="{c}" stroke-width="1.8" '
        'fill="none" stroke-linejoin="round"/>'
        '<path d="M12 22V12M3 7l9 5 9-5" stroke="{c}" stroke-width="1.8" '
        'fill="none" stroke-linejoin="round"/>'
    ),
}


def make_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Vyrobí ikonu obarvenou danou barvou. V tmavém motivu je tak vždy vidět."""
    body = _ICON_SVG.get(name)
    if body is None:
        return QIcon()
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}">{body.format(c=color)}</svg>'
    )
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# --------------------------------------------------------------------------- #
# Paleta a stylesheet
# --------------------------------------------------------------------------- #
def build_palette(t: Tokens) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    p.setColor(role.Window, QColor(t.window))
    p.setColor(role.WindowText, QColor(t.window_text))
    p.setColor(role.Base, QColor(t.base))
    p.setColor(role.AlternateBase, QColor(t.alternate_base))
    p.setColor(role.Text, QColor(t.text))
    p.setColor(role.Button, QColor(t.button))
    p.setColor(role.ButtonText, QColor(t.button_text))
    p.setColor(role.BrightText, QColor(t.log_error))
    p.setColor(role.ToolTipBase, QColor(t.tooltip_base))
    p.setColor(role.ToolTipText, QColor(t.tooltip_text))
    p.setColor(role.Highlight, QColor(t.selection_bg))
    p.setColor(role.HighlightedText, QColor(t.selection_text))
    p.setColor(role.Link, QColor(t.accent))
    p.setColor(role.LinkVisited, QColor(t.accent_hover))
    p.setColor(role.PlaceholderText, QColor(t.muted_text))

    for disabled_role in (role.Text, role.ButtonText, role.WindowText):
        p.setColor(group.Disabled, disabled_role, QColor(t.disabled_text))
    p.setColor(group.Disabled, role.Base, QColor(t.window))
    p.setColor(group.Disabled, role.Highlight, QColor(t.border))
    p.setColor(group.Disabled, role.HighlightedText, QColor(t.disabled_text))
    return p


def build_stylesheet(t: Tokens) -> str:
    """Doladí to, co QPalette nepokrývá: rámečky, progress bar, log, tooltip."""
    return f"""
    QToolTip {{
        color: {t.tooltip_text};
        background-color: {t.tooltip_base};
        border: 1px solid {t.border};
        padding: 4px 6px;
    }}
    QGroupBox {{
        border: 1px solid {t.border};
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 8px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 4px;
        color: {t.muted_text};
    }}
    QListView, QTreeView, QPlainTextEdit, QTextEdit, QLineEdit, QComboBox {{
        border: 1px solid {t.border};
        border-radius: 4px;
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
    }}
    QListView {{
        background-color: {t.base};
        alternate-background-color: {t.alternate_base};
        outline: none;
    }}
    QListView::item {{
        padding: 3px 4px;
        border-radius: 3px;
    }}
    QListView::item:hover {{
        background-color: {t.alternate_base};
    }}
    QListView::item:selected {{
        background-color: {t.selection_bg};
        color: {t.selection_text};
    }}
    QLineEdit, QComboBox {{
        padding: 4px 6px;
        background-color: {t.base};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.base};
        border: 1px solid {t.border};
    }}
    QPushButton {{
        background-color: {t.button};
        border: 1px solid {t.border};
        border-radius: 4px;
        padding: 5px 14px;
    }}
    QPushButton:hover {{ border-color: {t.accent}; }}
    QPushButton:disabled {{ color: {t.disabled_text}; border-color: {t.border}; }}
    QPushButton#primary {{
        background-color: {t.accent};
        color: {t.accent_text};
        border: 1px solid {t.accent};
        font-weight: 600;
    }}
    QPushButton#primary:hover {{ background-color: {t.accent_hover}; }}
    QPushButton#primary:disabled {{
        background-color: {t.button};
        color: {t.disabled_text};
        border-color: {t.border};
    }}
    QProgressBar {{
        border: 1px solid {t.border};
        border-radius: 4px;
        background-color: {t.base};
        text-align: center;
        color: {t.text};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {t.progress_chunk};
        border-radius: 3px;
    }}
    QPlainTextEdit#log, QTextBrowser#changelog {{
        background-color: {t.log_bg};
        color: {t.log_info};
        border: 1px solid {t.border};
    }}
    QSplitter::handle {{ background-color: {t.border}; }}
    QSplitter::handle:horizontal {{ width: 3px; }}
    QSplitter::handle:vertical {{ height: 3px; }}
    QStatusBar {{ color: {t.muted_text}; }}
    QLabel#muted {{ color: {t.muted_text}; }}
    QMenuBar, QMenu {{ background-color: {t.window}; color: {t.window_text}; }}
    QMenu {{ border: 1px solid {t.border}; }}
    QMenu::item:selected {{ background-color: {t.selection_bg}; color: {t.selection_text}; }}
    """


# --------------------------------------------------------------------------- #
# Tmavý titulkový pruh na Windows
# --------------------------------------------------------------------------- #
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19  # Windows 10 před buildem 18985


def apply_titlebar(widget: QWidget, dark: bool) -> bool:
    """Přebarví titulkový pruh okna. Vrací True, když se to povedlo.

    Qt 6.8+ to na Windows zvládne samo podle nastavené color scheme, ale
    jen u oken vytvořených až potom. Po přepnutí motivu za běhu je potřeba
    říct to systému přímo přes DwmSetWindowAttribute.
    """
    if sys.platform != "win32":
        return False
    handle = widget.winId()
    if not handle:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False

    value = ctypes.c_int(1 if dark else 0)
    hwnd = ctypes.c_void_p(int(handle))
    for attribute in (
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
    ):
        result = dwmapi.DwmSetWindowAttribute(
            hwnd, ctypes.c_int(attribute), ctypes.byref(value), ctypes.sizeof(value)
        )
        if result == 0:
            _force_titlebar_repaint(widget)
            return True
    return False


def _force_titlebar_repaint(widget: QWidget) -> None:
    """Windows překreslí pruh až při změně velikosti – šťouchneme o pixel."""
    if not widget.isVisible():
        return
    size = widget.size()
    widget.resize(size.width(), size.height() + 1)
    widget.resize(size)


# --------------------------------------------------------------------------- #
class ThemeManager(QObject):
    """Drží zvolený motiv, aplikuje ho a hlásí změny zbytku GUI."""

    changed = Signal(object)  # Tokens

    def __init__(self, app: QApplication, mode: ThemeMode = "system") -> None:
        super().__init__(app)
        self._app = app
        self._mode: ThemeMode = mode
        self._tokens: Tokens = LIGHT
        self._windows: list[QWidget] = []

        app.setStyle("Fusion")
        hints = QGuiApplication.styleHints()
        # Qt 6.5+: reakce na změnu motivu ve Windows bez restartu aplikace.
        hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # ------------------------------------------------------------------ #
    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def tokens(self) -> Tokens:
        return self._tokens

    def register_window(self, window: QWidget) -> None:
        """Okno, kterému se má přebarvovat titulkový pruh."""
        if window not in self._windows:
            self._windows.append(window)
        apply_titlebar(window, self._tokens.dark)

    def set_mode(self, mode: ThemeMode) -> None:
        if mode not in MODE_LABELS:
            mode = "system"
        self._mode = mode
        self.apply()

    def system_is_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def resolve(self) -> Tokens:
        if self._mode == "dark":
            return DARK
        if self._mode == "light":
            return LIGHT
        return DARK if self.system_is_dark() else LIGHT

    # ------------------------------------------------------------------ #
    def apply(self) -> None:
        tokens = self.resolve()
        self._tokens = tokens

        # Qt 6.8+ umí vynutit schéma samo; u starších je to jen no-op navíc.
        hints = QGuiApplication.styleHints()
        setter = getattr(hints, "setColorScheme", None)
        if setter is not None:
            with _blocked(hints):
                setter(
                    Qt.ColorScheme.Unknown
                    if self._mode == "system"
                    else (
                        Qt.ColorScheme.Dark
                        if self._mode == "dark"
                        else Qt.ColorScheme.Light
                    )
                )

        self._app.setPalette(build_palette(tokens))
        self._app.setStyleSheet(build_stylesheet(tokens))
        for window in self._windows:
            apply_titlebar(window, tokens.dark)
        self.changed.emit(tokens)

    def _on_system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._mode == "system":
            self.apply()

    def icon(self, name: str, *, accent: bool = False) -> QIcon:
        color = self._tokens.accent if accent else self._tokens.text
        return make_icon(name, color)


class _blocked:
    """Dočasně vypne signály, aby setColorScheme nespustil vlastní přepočet."""

    def __init__(self, obj: QObject) -> None:
        self._obj = obj
        self._previous = False

    def __enter__(self) -> None:
        self._previous = self._obj.blockSignals(True)

    def __exit__(self, *exc: object) -> None:
        self._obj.blockSignals(self._previous)
