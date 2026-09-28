"""Okno s nabídkou aktualizace: popis vydání, stažení, ověření."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core import Http, ReleaseInfo, is_frozen
from ..core.util import human_size
from .theme import ThemeManager, Tokens
from .workers import UpdateDownloadWorker


class UpdateDialog(QDialog):
    """Nabídne novou verzi. Po úspěšném stažení se zavře s ``Accepted``
    a v :attr:`downloaded` má cestu k ověřenému souboru; volající ho pak
    nasadí. Když uživatel vydání odmítne, je :attr:`skipped` True."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        release: ReleaseInfo,
        current: str,
        http: Http,
        theme: ThemeManager,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self.release = release
        self.downloaded: Path | None = None
        self.skipped = False

        self._http = http
        self._theme = theme
        self._pool = pool or QThreadPool.globalInstance()
        self._worker: UpdateDownloadWorker | None = None
        #: Ve zdrojácích není co vyměňovat – tam se jen odkáže na GitHub.
        self._can_install = is_frozen() and release.has_asset

        self.setWindowTitle("Aktualizace aplikace")
        self.setMinimumSize(620, 520)
        self._build_ui(current)
        self._apply_tokens(theme.tokens)
        theme.changed.connect(self._apply_tokens)

    # ------------------------------------------------------------------ #
    def _build_ui(self, current: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(8)

        head = QHBoxLayout()
        self.label_icon = QLabel()
        self.label_icon.setFixedWidth(28)
        self.label_title = QLabel(f"K dispozici je verze {self.release.version}")
        font = self.label_title.font()
        font.setPointSizeF(font.pointSizeF() + 3)
        font.setBold(True)
        self.label_title.setFont(font)
        head.addWidget(self.label_icon)
        head.addWidget(self.label_title, 1)
        root.addLayout(head)

        parts = [f"používáš {current}"]
        if self.release.published is not None:
            parts.append(f"vydáno {self.release.published_text}")
        if self.release.asset_size is not None:
            parts.append(human_size(self.release.asset_size))
        self.label_meta = QLabel(" · ".join(parts))
        self.label_meta.setObjectName("muted")
        root.addWidget(self.label_meta)

        self.text_notes = QTextBrowser()
        self.text_notes.setObjectName("changelog")
        self.text_notes.setOpenExternalLinks(True)
        # Popis vydání je Markdown, Qt ho umí vykreslit samo.
        self.text_notes.setMarkdown(self.release.notes or "*Bez popisu.*")
        root.addWidget(self.text_notes, 1)

        if not self._can_install:
            note = QLabel(self._cannot_install_reason())
            note.setObjectName("muted")
            note.setWordWrap(True)
            root.addWidget(note)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.label_status = QLabel()
        self.label_status.setObjectName("muted")
        self.label_status.setVisible(False)
        self.label_status.setWordWrap(True)
        root.addWidget(self.label_status)

        buttons = QHBoxLayout()
        self.button_skip = QPushButton("Přeskočit tuto verzi")
        self.button_skip.setToolTip(
            "Na tuhle verzi už aplikace sama neupozorní. Ručně ji zkontroluješ "
            "přes Nápověda → Zkontrolovat aktualizace."
        )
        self.button_skip.clicked.connect(self._on_skip)

        self.button_page = QPushButton("Otevřít na GitHubu")
        self.button_page.clicked.connect(self._open_page)

        self.button_close = QPushButton("Zavřít")
        self.button_close.clicked.connect(self.reject)

        self.button_install = QPushButton("Stáhnout a nainstalovat")
        self.button_install.setDefault(True)
        self.button_install.setEnabled(self._can_install)
        self.button_install.clicked.connect(self._on_install)

        buttons.addWidget(self.button_skip)
        buttons.addStretch(1)
        buttons.addWidget(self.button_page)
        buttons.addWidget(self.button_close)
        buttons.addWidget(self.button_install)
        root.addLayout(buttons)

    def _cannot_install_reason(self) -> str:
        if not self.release.has_asset:
            return (
                "Vydání neobsahuje soubor .exe – stáhni si ho ze stránky vydání "
                "na GitHubu."
            )
        return (
            "Aplikace běží ze zdrojáků, ne z .exe – výměnu za sebe udělat "
            "nemůže. Aktualizuj přes „git pull“, nebo si stáhni .exe z GitHubu."
        )

    @Slot(object)
    def _apply_tokens(self, tokens: Tokens) -> None:
        self.label_title.setStyleSheet(f"color:{tokens.accent}")
        self.label_icon.setPixmap(
            self._theme.icon("update", accent=True).pixmap(20, 20)
        )

    # ------------------------------------------------------------------ #
    def _open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.release.page_url))

    def _on_skip(self) -> None:
        self.skipped = True
        self.reject()

    def _on_install(self) -> None:
        if self._worker is not None:
            return
        self.button_install.setEnabled(False)
        self.button_skip.setEnabled(False)
        self.button_close.setText("Zrušit stahování")
        self.progress.setRange(0, 0)  # než dorazí první hlášení o průběhu
        self.progress.setVisible(True)
        self._set_status(f"Stahuji {self.release.asset_name}…")

        worker = UpdateDownloadWorker(self._http, self.release)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_downloaded)
        worker.signals.failed.connect(self._on_failed)
        self._worker = worker
        self._pool.start(worker)

    def _set_status(self, text: str) -> None:
        self.label_status.setText(text)
        self.label_status.setVisible(bool(text))

    @Slot(int, int)
    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.progress.setFormat(
                f"{human_size(done)} z {human_size(total)} (%p %)"
            )
        else:
            self.progress.setRange(0, 0)
            self.progress.setFormat(human_size(done))

    @Slot(object)
    def _on_downloaded(self, path: object) -> None:
        self._worker = None
        self.downloaded = Path(str(path))
        self._set_status("Staženo a ověřeno.")
        self.accept()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.progress.setVisible(False)
        self._set_status(message)
        self.button_install.setEnabled(self._can_install)
        self.button_install.setText("Zkusit znovu")
        self.button_skip.setEnabled(True)
        self.button_close.setText("Zavřít")

    # ------------------------------------------------------------------ #
    def reject(self) -> None:
        """Zavření během stahování ho nejdřív zruší."""
        worker = self._worker
        if worker is not None:
            self._worker = None
            worker.cancel()
            self._set_status("Stahování zrušeno.")
            self.progress.setVisible(False)
            self.button_install.setEnabled(self._can_install)
            self.button_skip.setEnabled(True)
            self.button_close.setText("Zavřít")
            return
        super().reject()
