"""Hlavní okno aplikace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QThreadPool, QTimer, Slot
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QCloseEvent
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core import (
    ARCHITECTURES,
    CHANNELS_BY_MAJOR,
    RELEASES_PAGE_URL,
    ArchPackages,
    ChangelogInfo,
    Channel,
    Http,
    MikrotikClient,
    ReleaseInfo,
    RemoteFile,
    Report,
    Settings,
    Status,
    UpdateError,
    Version,
    cleanup_backups,
    install_update,
    relaunch,
)
from ..core.models import ARCH_LABELS
from ..core.downloader import DownloadTask, build_tasks, cleanup_partials
from ..core.util import (
    files_count,
    human_size,
    human_speed,
    packages_count,
    versions_count,
)
from .theme import MODE_LABELS, ThemeManager, ThemeMode, Tokens
from .update_dialog import UpdateDialog
from .widgets import CheckableList, LogView, PackageDelegate, TransferTable
from .workers import (
    ChangelogWorker,
    DownloadWorker,
    NewestWorker,
    PackagesWorker,
    SizesWorker,
    UpdateCheckWorker,
    VersionsWorker,
)

#: Jak dlouho se při zavírání čeká, než vlákna dokončí rozdělanou práci.
SHUTDOWN_WAIT_MS = 4000

#: Tichý dotaz na GitHub se odkládá, ať nepřekáží načtení verzí RouterOS.
UPDATE_CHECK_DELAY_MS = 3000

#: Úklid zálohy po minulé aktualizaci – až když předchozí proces doběhl.
UPDATE_CLEANUP_DELAY_MS = 5000


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, theme: ThemeManager) -> None:
        super().__init__()
        self.settings = settings
        self.theme = theme
        self.pool = QThreadPool.globalInstance()
        self.http = Http()
        self.client = MikrotikClient(self.http)

        self._packages: dict[str, ArchPackages] = {}
        self._version: Version | None = None
        self._download_worker: DownloadWorker | None = None
        self._sizes_worker: SizesWorker | None = None
        self._update_worker: UpdateCheckWorker | None = None
        #: Nasazená aktualizace se spustí až po zavření okna, ne dřív.
        self._pending_relaunch = False
        self._active_workers: list[object] = []
        self._speeds: dict[str, float] = {}

        #: Zaškrtnuté extras si okno drží samo, ne jen v seznamu. Seznam se
        #: překresluje při každé změně verze, architektury i motivu a volby
        #: balíčků, které v nové verzi nejsou, by se jinak ztratily.
        self._selected_extras: set[str] = set(settings.extras)
        self._changelog_text: str = ""
        self._changelog_error: str | None = None
        #: Roste při každé změně řady nebo kanálu. Výsledky workerů, které
        #: patří k starší volbě, se podle něj zahodí.
        self._selection_generation = 0

        self.setWindowTitle(f"{APP_NAME} – stahovač balíčků MikroTik RouterOS")
        self.resize(1220, 860)
        self.setMinimumSize(900, 600)

        self._build_menu()
        self._build_ui()
        self._restore_settings()

        self._speed_timer = QTimer(self)
        self._speed_timer.setInterval(500)
        self._speed_timer.timeout.connect(self._refresh_speed)

        theme.changed.connect(self._on_theme_changed)
        self._on_theme_changed(theme.tokens)

        QTimer.singleShot(0, self.refresh_channel)
        QTimer.singleShot(UPDATE_CLEANUP_DELAY_MS, cleanup_backups)
        if settings.check_updates_on_start:
            QTimer.singleShot(
                UPDATE_CHECK_DELAY_MS, lambda: self._check_updates(manual=False)
            )

    # ------------------------------------------------------------------ #
    # Sestavení GUI
    # ------------------------------------------------------------------ #
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Soubor")
        self.action_open_target = QAction("Otevřít cílovou složku", self)
        self.action_open_target.triggered.connect(self._open_target_dir)
        file_menu.addAction(self.action_open_target)
        file_menu.addSeparator()
        quit_action = QAction("Ukončit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&Zobrazení")
        theme_menu = view_menu.addMenu("Motiv")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions: dict[ThemeMode, QAction] = {}
        for mode, label in MODE_LABELS.items():
            action = QAction(label, self, checkable=True)
            action.setData(mode)
            action.triggered.connect(
                lambda _checked, m=mode: self._set_theme_mode(m)
            )
            self._theme_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[mode] = action

        help_menu = self.menuBar().addMenu("&Nápověda")
        self.action_check_updates = QAction("Zkontrolovat aktualizace…", self)
        self.action_check_updates.triggered.connect(
            lambda: self._check_updates(manual=True)
        )
        help_menu.addAction(self.action_check_updates)

        self.action_auto_updates = QAction(
            "Kontrolovat aktualizace při spuštění", self, checkable=True
        )
        self.action_auto_updates.setChecked(self.settings.check_updates_on_start)
        self.action_auto_updates.toggled.connect(self._on_auto_updates_toggled)
        help_menu.addAction(self.action_auto_updates)

        self.action_releases = QAction("Vydání na GitHubu", self)
        self.action_releases.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(RELEASES_PAGE_URL))
        )
        help_menu.addAction(self.action_releases)

        help_menu.addSeparator()
        about = QAction("O aplikaci", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        root.addWidget(self._build_selector_row())

        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self._build_left_panel())
        top.addWidget(self._build_extras_panel())
        top.addWidget(self._build_changelog_panel())
        top.setStretchFactor(0, 0)
        top.setStretchFactor(1, 1)
        top.setStretchFactor(2, 1)
        top.setSizes([270, 470, 420])

        bottom = QSplitter(Qt.Orientation.Vertical)
        bottom.addWidget(self._build_transfers_panel())
        bottom.addWidget(self._build_log_panel())
        bottom.setSizes([200, 140])

        # Svislý splitter, aby si uživatel mohl přetáhnout poměr seznamů,
        # přenosů a logu podle toho, co ho zrovna zajímá.
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(top)
        self.main_splitter.addWidget(bottom)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([430, 340])
        root.addWidget(self.main_splitter, 1)

        root.addWidget(self._build_target_row())
        root.addWidget(self._build_action_row())

        self.setCentralWidget(central)
        self.statusBar().showMessage("Připraveno")

    def _build_selector_row(self) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        self.combo_major = QComboBox()
        self.combo_major.addItem("RouterOS v7", 7)
        self.combo_major.addItem("RouterOS v6", 6)
        self.combo_major.currentIndexChanged.connect(self._on_major_changed)

        self.combo_channel = QComboBox()
        self.combo_channel.currentIndexChanged.connect(self._on_channel_changed)

        self.combo_version = QComboBox()
        self.combo_version.setEditable(True)
        self.combo_version.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_version.setMinimumWidth(150)
        self.combo_version.setToolTip(
            "Vyber verzi ze seznamu, nebo ji napiš ručně (např. 7.20.3, 7.25beta5)."
        )
        self.combo_version.activated.connect(self._on_version_picked)
        self.combo_version.lineEdit().editingFinished.connect(self._on_version_typed)

        self.button_refresh = QPushButton("Obnovit")
        self.button_refresh.setToolTip("Znovu načíst verze, balíčky a changelog")
        self.button_refresh.clicked.connect(self._on_refresh_clicked)

        self.label_release = QLabel()
        self.label_release.setObjectName("muted")

        layout.addWidget(QLabel("Řada:"))
        layout.addWidget(self.combo_major)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Kanál:"))
        layout.addWidget(self.combo_channel)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Verze:"))
        layout.addWidget(self.combo_version)
        layout.addWidget(self.button_refresh)
        layout.addSpacing(10)
        layout.addWidget(self.label_release)
        layout.addStretch(1)
        return box

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        arch_box = QGroupBox("Architektury")
        arch_layout = QVBoxLayout(arch_box)
        self.list_arch = CheckableList()
        # Všech osm architektur má být vidět naráz, bez rolování.
        self.list_arch.setMinimumHeight(8 * 28 + 8)
        for arch in ARCHITECTURES:
            self.list_arch.add_item(arch, arch, tooltip=ARCH_LABELS.get(arch, ""))
        self.list_arch.selection_changed.connect(self._on_arch_changed)
        arch_layout.addWidget(self.list_arch)
        layout.addWidget(arch_box, 1)

        pkg_box = QGroupBox("Hlavní balíček")
        pkg_layout = QVBoxLayout(pkg_box)
        self.check_main = QCheckBox("routeros (hlavní systém)")
        self.check_main.setChecked(True)
        self.check_main.toggled.connect(self._update_summary)
        self.check_zip = QCheckBox("Stáhnout celý archiv all_packages.zip")
        self.check_zip.setToolTip(
            "Jeden ZIP se všemi extra balíčky pro danou architekturu."
        )
        self.check_zip.toggled.connect(self._update_summary)
        pkg_layout.addWidget(self.check_main)
        pkg_layout.addWidget(self.check_zip)
        layout.addWidget(pkg_box)
        return panel

    def _build_extras_panel(self) -> QWidget:
        box = QGroupBox("Extra balíčky")
        layout = QVBoxLayout(box)

        tools = QHBoxLayout()
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText("Filtr podle názvu…")
        self.edit_filter.setClearButtonEnabled(True)
        self.edit_filter.textChanged.connect(self._apply_extras_filter)
        self.button_all = QPushButton("Vše")
        self.button_all.clicked.connect(lambda: self.list_extras.set_all(True))
        self.button_none = QPushButton("Nic")
        self.button_none.clicked.connect(lambda: self.list_extras.set_all(False))
        tools.addWidget(self.edit_filter, 1)
        tools.addWidget(self.button_all)
        tools.addWidget(self.button_none)
        layout.addLayout(tools)

        self.list_extras = CheckableList()
        self.extras_delegate = PackageDelegate(self.list_extras)
        self.list_extras.setItemDelegate(self.extras_delegate)
        self.list_extras.selection_changed.connect(
            self._on_extras_selection_changed
        )
        layout.addWidget(self.list_extras, 1)

        self.label_extras_note = QLabel()
        self.label_extras_note.setObjectName("muted")
        self.label_extras_note.setWordWrap(True)
        layout.addWidget(self.label_extras_note)
        return box

    def _build_changelog_panel(self) -> QWidget:
        box = QGroupBox("Changelog")
        layout = QVBoxLayout(box)
        self.text_changelog = QTextBrowser()
        self.text_changelog.setObjectName("changelog")
        self.text_changelog.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        layout.addWidget(self.text_changelog)
        return box

    def _build_target_row(self) -> QWidget:
        box = QGroupBox("Cíl")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        self.edit_target = QLineEdit()
        self.edit_target.textChanged.connect(self._update_summary)
        self.button_browse = QPushButton("Procházet…")
        self.button_browse.clicked.connect(self._choose_target_dir)
        row.addWidget(QLabel("Složka:"))
        row.addWidget(self.edit_target, 1)
        row.addWidget(self.button_browse)
        layout.addLayout(row)

        options = QHBoxLayout()
        self.check_sub_version = QCheckBox("Podsložka <verze>")
        self.check_sub_version.toggled.connect(self._update_summary)
        self.check_sub_arch = QCheckBox("Podsložka <architektura>")
        self.check_sub_arch.toggled.connect(self._update_summary)
        self.check_verify = QCheckBox("Ověřovat SHA256")
        self.check_verify.setChecked(True)
        self.check_verify.setToolTip(
            "MikroTik publikuje ke každému souboru sidecar .sha256. "
            "Bez ověření se kontroluje jen velikost."
        )
        options.addWidget(self.check_sub_version)
        options.addWidget(self.check_sub_arch)
        options.addWidget(self.check_verify)
        options.addStretch(1)
        self.label_summary = QLabel()
        self.label_summary.setObjectName("muted")
        options.addWidget(self.label_summary)
        layout.addLayout(options)
        return box

    def _build_transfers_panel(self) -> QWidget:
        box = QGroupBox("Přenosy")
        layout = QVBoxLayout(box)
        # Stahují se až tři soubory naráz, takže jeden společný ukazatel by
        # mezi nimi skákal. Každý soubor má proto vlastní řádek s průběhem.
        self.table_transfers = TransferTable()
        self.table_transfers.setMinimumHeight(90)
        layout.addWidget(self.table_transfers)
        return box

    def _build_action_row(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.progress_total = QProgressBar()
        self.progress_total.setRange(0, 100)
        # Nový QProgressBar má hodnotu -1 (= "zatím nic") a Qt v tom stavu
        # nevykreslí ani text, takže by to vypadalo jako prázdný obdélník.
        self.progress_total.setValue(0)
        self.progress_total.setFormat("Celkem – nic se nestahuje")
        layout.addWidget(self.progress_total)

        buttons = QHBoxLayout()
        self.label_speed = QLabel()
        self.label_speed.setObjectName("muted")
        self.button_download = QPushButton("Stáhnout")
        self.button_download.setObjectName("primary")
        self.button_download.setMinimumWidth(130)
        self.button_download.clicked.connect(self.start_download)
        self.button_cancel = QPushButton("Zrušit")
        self.button_cancel.setEnabled(False)
        self.button_cancel.clicked.connect(self.cancel_download)
        buttons.addWidget(self.label_speed)
        buttons.addStretch(1)
        buttons.addWidget(self.button_cancel)
        buttons.addWidget(self.button_download)
        layout.addLayout(buttons)
        return box

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self.log = LogView()
        self.log.setMinimumHeight(80)
        layout.addWidget(self.log)
        return box

    # ------------------------------------------------------------------ #
    # Nastavení
    # ------------------------------------------------------------------ #
    def _restore_settings(self) -> None:
        s = self.settings
        index = self.combo_major.findData(s.major)
        self.combo_major.blockSignals(True)
        self.combo_major.setCurrentIndex(max(0, index))
        self.combo_major.blockSignals(False)
        self._reload_channels(select=s.channel)

        self.list_arch.set_checked(s.architectures or ["arm64"])
        self.check_main.setChecked(s.include_main)
        self.check_zip.setChecked(s.include_all_packages_zip)
        self.edit_target.setText(s.target_dir)
        self.check_sub_version.setChecked(s.subfolder_version)
        self.check_sub_arch.setChecked(s.subfolder_arch)
        self.check_verify.setChecked(s.verify_sha256)
        self._theme_actions[s.theme].setChecked(True)  # type: ignore[index]

        if s.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(s.window_geometry.encode()))

    def _collect_settings(self) -> Settings:
        s = self.settings
        s.major = self.combo_major.currentData()
        s.channel = self._current_channel().value
        s.version = self.combo_version.currentText().strip()
        s.architectures = self.list_arch.checked_keys()
        s.include_main = self.check_main.isChecked()
        s.include_all_packages_zip = self.check_zip.isChecked()
        s.extras = sorted(self._selected_extras)
        s.target_dir = self.edit_target.text().strip()
        s.subfolder_version = self.check_sub_version.isChecked()
        s.subfolder_arch = self.check_sub_arch.isChecked()
        s.verify_sha256 = self.check_verify.isChecked()
        s.theme = self.theme.mode
        s.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        return s

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_worker is not None:
            answer = QMessageBox.question(
                self,
                "Probíhá stahování",
                "Stahování ještě běží. Opravdu ukončit?\n"
                "Rozdělané soubory zůstanou jako .part a příště se dopočítají.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._download_worker.cancel()

        for worker in list(self._active_workers):
            cancel = getattr(worker, "cancel", None)
            if cancel is not None:
                cancel()
        try:
            self._collect_settings().save()
        except OSError:
            pass

        # HTTP klient se smí zavřít až když vlákna opravdu skončila. Zavřít
        # ho pod rukama běžícímu přenosu znamená ReadError z půlky streamu.
        # Když se do limitu nedoberou (zatuhlé spojení čeká na read timeout),
        # klienta prostě nezavíráme – proces stejně končí.
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            drained = self.pool.waitForDone(SHUTDOWN_WAIT_MS)
        finally:
            QApplication.restoreOverrideCursor()
        if drained:
            self.http.close()

        if self._pending_relaunch:
            try:
                relaunch()
            except UpdateError as exc:
                QMessageBox.warning(
                    self,
                    "Aktualizace",
                    f"{exc}\n\nNová verze je nasazená, jen ji spusť ručně.",
                )
        event.accept()

    # ------------------------------------------------------------------ #
    # Motiv
    # ------------------------------------------------------------------ #
    def _set_theme_mode(self, mode: ThemeMode) -> None:
        self.theme.set_mode(mode)

    @Slot(object)
    def _on_theme_changed(self, tokens: Tokens) -> None:
        self.log.set_tokens(tokens)
        self.table_transfers.set_colors(
            done=tokens.log_success,
            failed=tokens.log_error,
            muted=tokens.muted_text,
        )
        self.button_refresh.setIcon(self.theme.icon("refresh"))
        self.button_browse.setIcon(self.theme.icon("folder"))
        self.button_all.setIcon(self.theme.icon("check-all"))
        self.button_none.setIcon(self.theme.icon("check-none"))
        self.button_download.setIcon(self.theme.icon("download", accent=True))
        self.button_cancel.setIcon(self.theme.icon("cancel"))
        self._render_extras()
        self._render_changelog()

    # ------------------------------------------------------------------ #
    # Volby kanálu a verze
    # ------------------------------------------------------------------ #
    def _current_major(self) -> int:
        return int(self.combo_major.currentData())

    def _current_channel(self) -> Channel:
        # PySide6 uloží str-enum do QVariant jako prostý řetězec, proto
        # se z dat vždy skládá Channel zpátky.
        data = self.combo_channel.currentData()
        try:
            return Channel(data)
        except ValueError:
            return Channel.STABLE

    def _reload_channels(self, select: str | None = None) -> None:
        wanted = select or self._current_channel().value
        self.combo_channel.blockSignals(True)
        self.combo_channel.clear()
        for channel in CHANNELS_BY_MAJOR[self._current_major()]:
            self.combo_channel.addItem(channel.label, channel.value)
        index = max(0, self.combo_channel.findData(wanted))
        self.combo_channel.setCurrentIndex(index)
        self.combo_channel.blockSignals(False)

    def _on_major_changed(self) -> None:
        self._reload_channels()
        self.refresh_channel()

    def _on_channel_changed(self) -> None:
        self.refresh_channel()

    def _on_refresh_clicked(self) -> None:
        self.client.versions_cache.invalidate()
        self.client.packages_cache.invalidate()
        self.refresh_channel()

    def _on_version_picked(self, _index: int) -> None:
        self._load_version(self.combo_version.currentText().strip())

    def _on_version_typed(self) -> None:
        text = self.combo_version.currentText().strip()
        if text and (self._version is None or str(self._version) != text):
            self._load_version(text)

    # ------------------------------------------------------------------ #
    # Načítání dat
    # ------------------------------------------------------------------ #
    def refresh_channel(self) -> None:
        major = self._current_major()
        channel = self._current_channel()
        self._selection_generation += 1
        generation = self._selection_generation
        self.statusBar().showMessage(
            f"Zjišťuji nejnovější verzi ({channel.label})…"
        )
        worker = NewestWorker(self.client, major, channel)
        worker.signals.finished.connect(
            lambda info, g=generation, ch=channel: self._on_newest_loaded(info, g, ch)
        )
        worker.signals.failed.connect(self._on_worker_failed)
        self._start(worker)

    def _is_current(self, generation: int) -> bool:
        """False, když mezitím uživatel přepnul řadu nebo kanál."""
        return generation == self._selection_generation

    def _on_newest_loaded(
        self, info, generation: int, channel: Channel  # noqa: ANN001 - NewestInfo
    ) -> None:
        if not self._is_current(generation):
            return  # odpověď patří ke kanálu, ze kterého už uživatel odešel

        # Datum z NEWEST patří nejnovější verzi kanálu. Popisek ho proto
        # nenastavuje – naplní se až podle skutečně vybrané verze
        # v _on_changelog_loaded.
        self.log.append_entry(
            "info",
            f"Nejnovější {channel.label}: {info.version} "
            f"(vydáno {info.released_text})",
        )

        self.combo_version.blockSignals(True)
        self.combo_version.clear()
        self.combo_version.addItem(str(info.version))
        self.combo_version.setCurrentIndex(0)
        self.combo_version.blockSignals(False)

        self._load_version(str(info.version))
        self._load_version_history(info.version, generation)

    def _load_version_history(self, newest: Version, generation: int) -> None:
        worker = VersionsWorker(
            self.client, self._current_major(), newest, self._current_channel()
        )
        worker.signals.finished.connect(
            lambda versions, g=generation: self._on_versions_loaded(versions, g)
        )
        worker.signals.progress.connect(self._on_versions_progress)
        worker.signals.failed.connect(
            lambda msg: self.log.append_entry(
                "warning", f"Historii verzí se nepodařilo načíst: {msg}"
            )
        )
        self._start(worker)

    @Slot(int, int)
    def _on_versions_progress(self, done: int, total: int) -> None:
        if done < total:
            self.statusBar().showMessage(f"Hledám dostupné verze… {done}/{total}")

    def _on_versions_loaded(self, versions: list[Version], generation: int) -> None:
        if not self._is_current(generation):
            return  # historie patří k jinému kanálu, combobox se nesmí přepsat
        current = self.combo_version.currentText().strip()
        self.combo_version.blockSignals(True)
        self.combo_version.clear()
        self.combo_version.addItems([str(v) for v in versions])
        index = self.combo_version.findText(current)
        if index >= 0:
            self.combo_version.setCurrentIndex(index)
        else:
            self.combo_version.setEditText(current)
        self.combo_version.blockSignals(False)
        self.statusBar().showMessage(
            f"K dispozici {versions_count(len(versions))}", 5000
        )

    def _load_version(self, text: str) -> None:
        version = Version.try_parse(text)
        if version is None:
            self.log.append_entry("error", f"Neplatný tvar verze: {text!r}")
            return
        self._version = version
        self._load_changelog(version)
        self._load_packages()

    def _load_changelog(self, version: Version) -> None:
        # Text předchozí verze se musí zahodit hned. Jinak by ho překreslení
        # při přepnutí motivu vrátilo na obrazovku pod jiným číslem verze.
        self._changelog_text = ""
        self._changelog_error = None
        self.text_changelog.setPlainText("Načítám changelog…")
        self.label_release.setText("zjišťuji datum vydání…")
        worker = ChangelogWorker(self.client, version)
        worker.signals.finished.connect(self._on_changelog_loaded)
        worker.signals.failed.connect(
            lambda msg, v=version: self._on_changelog_failed(v, msg)
        )
        self._start(worker)

    def _on_changelog_failed(self, version: Version, message: str) -> None:
        if self._version != version:
            return
        # Bez tohohle by popisek zůstal viset na „zjišťuji datum vydání…“.
        self._changelog_text = ""
        self._changelog_error = f"Chyba: {message}"
        self.label_release.setText("datum vydání se nepodařilo zjistit")
        self._render_changelog()

    @Slot(object)
    def _on_changelog_loaded(self, info: ChangelogInfo) -> None:
        if self._version != info.version:
            return  # mezitím přišla jiná volba
        self._changelog_text = info.text
        self._changelog_error = None
        self.label_release.setText(
            f"vydáno {info.released_text}"
            if info.released is not None
            else "datum vydání neuvedeno"
        )
        self._render_changelog()

    def _render_changelog(self) -> None:
        if self._changelog_error is not None:
            self.text_changelog.setPlainText(self._changelog_error)
            return
        text = self._changelog_text
        if not text:
            return  # probíhá načítání, hlášku v panelu necháme být
        tokens = self.theme.tokens
        lines = []
        for raw in text.splitlines():
            line = raw.rstrip()
            escaped = (
                line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            if line.startswith("What's new"):
                lines.append(
                    f'<div style="color:{tokens.accent};font-weight:600;'
                    f'margin-bottom:6px">{escaped}</div>'
                )
            elif line.startswith("*)"):
                lines.append(
                    f'<div style="color:{tokens.text};margin-left:8px;'
                    f'text-indent:-8px">{escaped}</div>'
                )
            elif not line:
                lines.append("<div>&nbsp;</div>")
            else:
                lines.append(f'<div style="color:{tokens.muted_text}">{escaped}</div>')
        body = "".join(lines)
        self.text_changelog.setHtml(
            '<div style="font-family:Consolas,monospace;font-size:9pt">'
            f"{body}</div>"
        )

    def _load_packages(self) -> None:
        version = self._version
        archs = self.list_arch.checked_keys()
        if version is None:
            return
        if not archs:
            self._packages = {}
            self._render_extras()
            self.statusBar().showMessage("Vyber aspoň jednu architekturu", 5000)
            return

        self.statusBar().showMessage(f"Načítám balíčky pro {version}…")
        worker = PackagesWorker(self.client, version, archs)
        worker.signals.finished.connect(self._on_packages_loaded)
        worker.signals.failed.connect(
            lambda msg, v=version: self._on_packages_failed(v, msg)
        )
        self._start(worker)

    def _on_packages_failed(self, version: Version, message: str) -> None:
        if self._version != version:
            return
        # Nechat v seznamu balíčky předchozí verze by bylo horší než prázdno –
        # uživatel by je zaškrtl a stahování by skončilo na 404.
        self._packages = {}
        self._render_extras()
        self.label_extras_note.setText(
            "Seznam balíčků se nepodařilo načíst. Zkus Obnovit."
        )
        self.log.append_entry("error", f"Balíčky pro {version}: {message}")
        self.statusBar().showMessage("Balíčky se nepodařilo načíst", 5000)

    @Slot(object)
    def _on_packages_loaded(
        self, payload: tuple[Version, dict[str, ArchPackages]]
    ) -> None:
        version, packages = payload
        # Kontrolovat jen verzi nestačí: při rychlé změně architektury běží
        # dva workery nad toutéž verzí a starší odpověď by přepsala novější.
        if self._version != version:
            return
        if set(packages) != set(self.list_arch.checked_keys()):
            return
        self._packages = packages
        sources = {p.source for p in packages.values()}
        detail = "z archivu all_packages" if sources == {"zip"} else "sondáží HEAD"
        self.log.append_entry(
            "info",
            f"{version}: načteno {packages_count(len(self._union_packages()))} "
            f"extra ({detail})",
        )
        self._render_extras()
        self.statusBar().showMessage("Připraveno", 3000)

    # ------------------------------------------------------------------ #
    # Extra balíčky
    # ------------------------------------------------------------------ #
    def _union_packages(self) -> list[str]:
        names: set[str] = set()
        for result in self._packages.values():
            names.update(result.entries)
        return sorted(names)

    @Slot()
    def _on_extras_selection_changed(self) -> None:
        """Promítne zaškrtnutí do _selected_extras, bez ztráty skrytých voleb."""
        listed = set(self.list_extras.keys())
        checked = set(self.list_extras.checked_keys())
        # Balíčky, které v aktuální verzi nebo architektuře nejsou, zůstanou
        # zapamatované – po návratu k jiné verzi se zaškrtnou zpátky.
        self._selected_extras = (self._selected_extras - listed) | checked
        self._update_summary()

    def _render_extras(self) -> None:
        previously = self._selected_extras
        archs = self.list_arch.checked_keys()
        tokens = self.theme.tokens
        self.extras_delegate.set_colors(tokens.muted_text, tokens.log_warning)

        with self.list_extras.quiet():
            self.list_extras.clear()
            for name in self._union_packages():
                available = [
                    a
                    for a in archs
                    if a in self._packages and name in self._packages[a].entries
                ]
                missing = [a for a in archs if a not in available]
                total = sum(
                    self._packages[a].entries[name].size or 0 for a in available
                )
                note = ""
                if missing:
                    note = (
                        f"chybí pro {', '.join(missing)}"
                        if len(missing) <= 2
                        else f"chybí pro {len(missing)} architektur"
                    )
                tooltip = "\n".join(
                    f"{a}: {self._packages[a].entries[name].filename} "
                    f"({human_size(self._packages[a].entries[name].size)})"
                    for a in available
                )
                if missing:
                    tooltip += "\n\nNení k dispozici pro: " + ", ".join(missing)
                self.list_extras.add_item(
                    name,
                    name,
                    checked=name in previously,
                    tooltip=tooltip,
                    size_text=human_size(total) if available else "—",
                    note=note,
                )

        self._apply_extras_filter(self.edit_filter.text())
        if not self._packages:
            self.label_extras_note.setText(
                "Vyber verzi a architekturu – seznam se načte automaticky."
            )
        else:
            self.label_extras_note.setText(
                f"{packages_count(len(self._union_packages()))} pro "
                f"{', '.join(archs) or '—'}."
            )
        self._update_summary()

    def _apply_extras_filter(self, text: str) -> None:
        visible = self.list_extras.apply_filter(text)
        if text.strip() and visible == 0:
            self.statusBar().showMessage("Filtru neodpovídá žádný balíček", 3000)

    def _on_arch_changed(self) -> None:
        self._load_packages()
        self._update_summary()

    # ------------------------------------------------------------------ #
    # Souhrn a cíl
    # ------------------------------------------------------------------ #
    def _selected_remotes(self) -> list[RemoteFile]:
        version = self._version
        if version is None:
            return []
        remotes: list[RemoteFile] = []
        extras = self.list_extras.checked_keys()
        for arch in self.list_arch.checked_keys():
            if self.check_main.isChecked():
                remotes.append(self.client.main_file(version, arch))
            if self.check_zip.isChecked():
                remotes.append(self.client.archive_file(version, arch))
            result = self._packages.get(arch)
            if result is None:
                continue
            for name in extras:
                entry = result.entries.get(name)
                if entry is not None:
                    remotes.append(self.client.extra_file(entry, version))
        return remotes

    def _update_summary(self) -> None:
        remotes = self._selected_remotes()
        known = sum(r.size or 0 for r in remotes)
        unknown = sum(1 for r in remotes if r.size is None)
        text = f"{files_count(len(remotes))}, {human_size(known)}"
        if unknown:
            text += f" + {unknown} neznámé velikosti"
        self.label_summary.setText(text)
        self.button_download.setEnabled(
            bool(remotes) and self._download_worker is None
        )

    def _choose_target_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Vyber cílovou složku", self.edit_target.text()
        )
        if directory:
            self.edit_target.setText(directory)

    def _open_target_dir(self) -> None:
        path = Path(self.edit_target.text().strip())
        if not path.exists():
            QMessageBox.information(
                self, "Složka neexistuje", f"Složka {path} zatím neexistuje."
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------ #
    # Stahování
    # ------------------------------------------------------------------ #
    def start_download(self) -> None:
        remotes = self._selected_remotes()
        if not remotes:
            QMessageBox.information(
                self, "Není co stahovat", "Zvol architekturu a aspoň jeden balíček."
            )
            return
        target = self.edit_target.text().strip()
        if not target:
            QMessageBox.warning(self, "Chybí cíl", "Zadej cílovou složku.")
            return

        self._set_busy(True)
        self.statusBar().showMessage("Zjišťuji velikosti souborů…")
        worker = SizesWorker(self.client, remotes)
        worker.signals.finished.connect(self._on_sizes_ready)
        worker.signals.failed.connect(self._on_download_failed)
        self._sizes_worker = worker
        self._start(worker)

    @Slot(object)
    def _on_sizes_ready(self, remotes: list[RemoteFile]) -> None:
        self._sizes_worker = None
        root = Path(self.edit_target.text().strip()).expanduser()
        tasks = build_tasks(
            root,
            remotes,
            per_version=self.check_sub_version.isChecked(),
            per_arch=self.check_sub_arch.isChecked(),
        )

        removed = cleanup_partials(root, keep=[t.part_path for t in tasks])
        if removed:
            self.log.append_entry(
                "info",
                f"Uklizeno {files_count(len(removed))} nedokončených .part "
                "z minulého běhu",
            )

        total = sum(t.remote.size or 0 for t in tasks)
        self.log.append_entry(
            "info",
            f"Stahuji {files_count(len(tasks))} ({human_size(total)}) do {root}",
        )
        self.progress_total.setValue(0)
        self.progress_total.setFormat("Celkem %p%")
        self.table_transfers.set_rows(
            (self._task_key(t), t.remote.name, human_size(t.remote.size))
            for t in tasks
        )

        worker = DownloadWorker(
            self.client, tasks, verify_sha256=self.check_verify.isChecked()
        )
        worker.signals.log.connect(self.log.append_entry)
        worker.signals.file_status.connect(self._on_file_status)
        worker.signals.file_progress.connect(self._on_file_progress)
        worker.signals.total_progress.connect(self._on_total_progress)
        worker.signals.finished.connect(self._on_download_finished)
        worker.signals.failed.connect(self._on_download_failed)
        self._download_worker = worker
        self._speed_timer.start()
        self.statusBar().showMessage(f"Stahuji do {root}…")
        self.pool.start(worker)

    def cancel_download(self) -> None:
        if self._sizes_worker is not None:
            self._sizes_worker.cancel()
            self._sizes_worker = None
            self._set_busy(False)
            self.statusBar().showMessage("Zrušeno", 3000)
            return
        if self._download_worker is not None:
            self.log.append_entry("warning", "Ruším stahování…")
            self._download_worker.cancel()
            self.button_cancel.setEnabled(False)

    @staticmethod
    def _task_key(task: DownloadTask) -> str:
        return str(task.dest)

    @Slot(object, object)
    def _on_file_status(self, task: DownloadTask, status: Status) -> None:
        self.table_transfers.set_status(self._task_key(task), status.value)
        if status is Status.DONE:
            self.log.append_entry("success", f"{task.remote.name} – staženo")

    @Slot(object, int, object, float)
    def _on_file_progress(
        self, task: DownloadTask, downloaded: int, total: int | None, speed: float
    ) -> None:
        if total:
            self.table_transfers.set_progress(
                self._task_key(task), downloaded * 100 / total
            )
        self._speeds[self._task_key(task)] = speed

    @Slot(int, object)
    def _on_total_progress(self, downloaded: int, total: int | None) -> None:
        if total:
            self.progress_total.setValue(min(100, int(downloaded * 100 / total)))
            self.progress_total.setFormat(
                f"Celkem %p%  ({human_size(downloaded)} z {human_size(total)})"
            )

    def _refresh_speed(self) -> None:
        """Součet rychlostí právě běžících přenosů, obnovovaný dvakrát za sekundu."""
        total = sum(self._speeds.values())
        self.label_speed.setText(human_speed(total) if total else "")

    @Slot(object)
    def _on_download_finished(self, report: Report) -> None:
        self._download_worker = None
        self._speed_timer.stop()
        self._set_busy(False)
        done = report.count(Status.DONE)
        skipped = report.count(Status.SKIPPED)
        failed = report.count(Status.FAILED)
        cancelled = report.count(Status.CANCELLED)

        if cancelled:
            self.log.append_entry(
                "warning",
                f"Zrušeno. Dokončeno {done}, nedokončené soubory zůstaly jako .part "
                "a příště se na ně naváže.",
            )
            self.statusBar().showMessage("Stahování zrušeno", 5000)
        elif failed:
            self.log.append_entry(
                "error", f"Dokončeno s chybami: {done} staženo, {failed} selhalo"
            )
            self.statusBar().showMessage("Dokončeno s chybami", 5000)
        else:
            self.log.append_entry(
                "success",
                f"Hotovo: {done} staženo, {skipped} přeskočeno",
            )
            self.statusBar().showMessage("Hotovo", 5000)
            self.progress_total.setValue(100)
        self._speeds.clear()
        self.label_speed.setText("")

    @Slot(str)
    def _on_download_failed(self, message: str) -> None:
        self._download_worker = None
        self._sizes_worker = None
        self._speed_timer.stop()
        self._set_busy(False)
        self.log.append_entry("error", message)
        self.statusBar().showMessage("Stahování selhalo", 5000)

    def _set_busy(self, busy: bool) -> None:
        self.button_download.setEnabled(not busy)
        self.button_cancel.setEnabled(busy)
        for widget in (
            self.combo_major,
            self.combo_channel,
            self.combo_version,
            self.button_refresh,
            self.list_arch,
            self.list_extras,
            self.check_main,
            self.check_zip,
            self.button_browse,
            self.check_sub_version,
            self.check_sub_arch,
            self.check_verify,
        ):
            widget.setEnabled(not busy)

    # ------------------------------------------------------------------ #
    def _start(self, worker) -> None:  # noqa: ANN001
        self._active_workers.append(worker)
        # Odebrat je potřeba po obou koncích, jinak se neúspěšné workery
        # hromadí až do zavření okna.
        for signal in (worker.signals.finished, worker.signals.failed):
            signal.connect(lambda *_, w=worker: self._forget_worker(w))
        self.pool.start(worker)

    def _forget_worker(self, worker: object) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        self.log.append_entry("error", message)
        self.statusBar().showMessage("Chyba při načítání", 5000)

    # ------------------------------------------------------------------ #
    # Aktualizace aplikace
    # ------------------------------------------------------------------ #
    def _on_auto_updates_toggled(self, checked: bool) -> None:
        self.settings.check_updates_on_start = checked

    def _check_updates(self, *, manual: bool) -> None:
        """Dotaz na GitHub. Tichá kontrola po startu mlčí, když nic není."""
        if self._update_worker is not None:
            return
        if manual:
            self.statusBar().showMessage("Zjišťuji, jestli nevyšla nová verze…")

        worker = UpdateCheckWorker(self.http, __version__)
        worker.signals.finished.connect(
            lambda release: self._on_update_checked(release, manual)
        )
        worker.signals.failed.connect(
            lambda message: self._on_update_check_failed(message, manual)
        )
        for signal in (worker.signals.finished, worker.signals.failed):
            signal.connect(self._forget_update_worker)
        self._update_worker = worker
        self._start(worker)

    def _forget_update_worker(self, *_args: object) -> None:
        self._update_worker = None

    def _on_update_check_failed(self, message: str, manual: bool) -> None:
        # Po startu se na výpadek sítě neupozorňuje – uživatel o aktualizaci
        # nežádal a jde mu o RouterOS, ne o tuhle aplikaci.
        if not manual:
            return
        self.statusBar().showMessage("Aktualizace se nepodařilo zjistit", 5000)
        QMessageBox.warning(self, "Aktualizace", message)

    def _on_update_checked(self, release: object, manual: bool) -> None:
        if release is None:
            self.statusBar().showMessage(
                f"Verze {__version__} je nejnovější", 5000
            )
            if manual:
                QMessageBox.information(
                    self,
                    "Aktualizace",
                    f"Používáš nejnovější verzi ({__version__}).",
                )
            return

        if not isinstance(release, ReleaseInfo):
            return
        if not manual and release.tag == self.settings.skipped_update:
            return  # tuhle verzi uživatel odmítl
        self.statusBar().showMessage(f"K dispozici je verze {release.version}")
        self._show_update_dialog(release)

    def _show_update_dialog(self, release: ReleaseInfo) -> None:
        if self._download_worker is not None:
            QMessageBox.information(
                self,
                "Aktualizace",
                f"K dispozici je verze {release.version}.\n\n"
                "Teď se ale nevyměňuje – běží stahování balíčků. Až doběhne, "
                "dej Nápověda → Zkontrolovat aktualizace.",
            )
            return

        dialog = UpdateDialog(
            self,
            release=release,
            current=__version__,
            http=self.http,
            theme=self.theme,
            pool=self.pool,
        )
        self.theme.register_window(dialog)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted

        if dialog.skipped:
            self.settings.skipped_update = release.tag
            self.log.append_entry(
                "info", f"Verze {release.version} přeskočena."
            )
            return
        if accepted and dialog.downloaded is not None:
            self._apply_update(dialog.downloaded, release)

    def _apply_update(self, downloaded: Path, release: ReleaseInfo) -> None:
        answer = QMessageBox.question(
            self,
            "Nainstalovat aktualizaci",
            f"Verze {release.version} je stažená a ověřená.\n\n"
            "Aplikace se teď ukončí a spustí znovu už v nové verzi. "
            "Pokračovat?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.log.append_entry(
                "info", f"Nová verze čeká připravená v {downloaded}"
            )
            return

        try:
            install_update(downloaded)
        except (UpdateError, OSError) as exc:
            QMessageBox.critical(self, "Aktualizace", str(exc))
            return
        self._pending_relaunch = True
        self.close()

    # ------------------------------------------------------------------ #
    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"O aplikaci {APP_NAME}",
            f"<b>{APP_NAME} {__version__}</b><br><br>"
            "Stahovač balíčků MikroTik RouterOS z oficiálních zdrojů "
            "(download.mikrotik.com).<br><br>"
            "Balíčky se ověřují proti SHA256 sidecarům, které MikroTik "
            "publikuje ke každému souboru.<br><br>"
            f"Nastavení a cache: {Settings.path().parent}",
        )
