"""Drobné znovupoužitelné widgety."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..i18n import t
from .theme import Tokens

SIZE_ROLE = Qt.ItemDataRole.UserRole + 1
NOTE_ROLE = Qt.ItemDataRole.UserRole + 2


class PackageDelegate(QStyledItemDelegate):
    """Vykreslí velikost zarovnanou doprava a poznámku tlumenou barvou.

    Bez toho by se velikosti srovnávaly mezerami, což u proporcionálního
    písma nikdy nevyjde.
    """

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._muted = QColor("#808080")
        self._warn = QColor("#a07000")

    def set_colors(self, muted: str, warning: str) -> None:
        self._muted = QColor(muted)
        self._warn = QColor(warning)

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        super().paint(painter, option, index)
        size_text = index.data(SIZE_ROLE) or ""
        note = index.data(NOTE_ROLE) or ""
        if not size_text and not note:
            return

        painter.save()
        metrics = option.fontMetrics
        right = option.rect.adjusted(0, 0, -8, 0)
        if size_text:
            painter.setPen(self._muted)
            painter.drawText(
                right,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                size_text,
            )
            right = right.adjusted(
                0, 0, -(metrics.horizontalAdvance(size_text) + 14), 0
            )
        if note:
            painter.setPen(self._warn)
            painter.drawText(
                right,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                note,
            )
        painter.restore()


class CheckableList(QListWidget):
    """Seznam s zaškrtávacími poli a signálem při každé změně výběru."""

    selection_changed = Signal()

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setUniformItemSizes(False)
        self.itemChanged.connect(self._on_item_changed)
        self._muted = False

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        if not self._muted:
            self.selection_changed.emit()

    def add_item(
        self,
        key: str,
        text: str,
        *,
        checked: bool = False,
        tooltip: str = "",
        enabled: bool = True,
        size_text: str = "",
        note: str = "",
    ) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, key)
        if size_text:
            item.setData(SIZE_ROLE, size_text)
        if note:
            item.setData(NOTE_ROLE, note)
        flags = Qt.ItemFlag.ItemIsUserCheckable
        if enabled:
            flags |= Qt.ItemFlag.ItemIsEnabled
        item.setFlags(flags)
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        if tooltip:
            item.setToolTip(tooltip)
        self.addItem(item)
        return item

    def keys(self) -> list[str]:
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())
        ]

    def checked_keys(self) -> list[str]:
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]

    def set_tooltip(self, key: str, tooltip: str) -> None:
        """Přepíše nápovědu u položky. Po změně jazyka je jiná."""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                item.setToolTip(tooltip)
                return

    def set_checked(self, keys: Iterable[str]) -> None:
        wanted = set(keys)
        with self.quiet():
            for i in range(self.count()):
                item = self.item(i)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.data(Qt.ItemDataRole.UserRole) in wanted
                    else Qt.CheckState.Unchecked
                )
        self.selection_changed.emit()

    def set_all(self, checked: bool, *, only_visible: bool = True) -> None:
        with self.quiet():
            for i in range(self.count()):
                item = self.item(i)
                if only_visible and item.isHidden():
                    continue
                if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                    continue
                item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        self.selection_changed.emit()

    def apply_filter(self, needle: str) -> int:
        """Skryje položky, které neodpovídají filtru. Vrací počet viditelných."""
        needle = needle.strip().lower()
        visible = 0
        for i in range(self.count()):
            item = self.item(i)
            match = not needle or needle in item.text().lower()
            item.setHidden(not match)
            visible += int(match)
        return visible

    def quiet(self) -> "_Quiet":
        return _Quiet(self)


class _Quiet:
    """Blok, ve kterém hromadné změny nevyvolávají signál za každou položku."""

    def __init__(self, widget: CheckableList) -> None:
        self._widget = widget

    def __enter__(self) -> None:
        self._widget._muted = True

    def __exit__(self, *exc: object) -> None:
        self._widget._muted = False


class LogView(QPlainTextEdit):
    """Log s barvami podle úrovně, čitelnými ve světlém i tmavém motivu."""

    MAX_BLOCKS = 2000

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self._tokens: Tokens | None = None
        self._entries: list[tuple[str, str]] = []

    def set_tokens(self, tokens: Tokens) -> None:
        self._tokens = tokens
        self._rebuild()

    def _color(self, level: str) -> str:
        t = self._tokens
        if t is None:
            return "#808080"
        return {
            "info": t.log_info,
            "success": t.log_success,
            "warning": t.log_warning,
            "error": t.log_error,
        }.get(level, t.log_info)

    def append_entry(self, level: str, message: str) -> None:
        self._entries.append((level, message))
        if len(self._entries) > self.MAX_BLOCKS:
            del self._entries[: len(self._entries) - self.MAX_BLOCKS]
        self._append_html(level, message)

    def _append_html(self, level: str, message: str) -> None:
        escaped = (
            message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        prefix = {"warning": "⚠ ", "error": "✖ ", "success": "✔ "}.get(level, "")
        self.appendHtml(
            f'<span style="color:{self._color(level)};white-space:pre-wrap">'
            f"{prefix}{escaped}</span>"
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def _rebuild(self) -> None:
        """Po přepnutí motivu se log přebarví, aby zůstal čitelný."""
        entries = list(self._entries)
        self.clear()
        for level, message in entries:
            self._append_html(level, message)

    def clear_log(self) -> None:
        self._entries.clear()
        self.clear()


class ProgressDelegate(QStyledItemDelegate):
    """Vykreslí ve sloupci skutečný progress bar podle hodnoty v UserRole."""

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        value = index.data(Qt.ItemDataRole.UserRole)
        if value is None:
            super().paint(painter, option, index)
            return

        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(3, 4, -3, -4)
        bar.minimum = 0
        bar.maximum = 100
        bar.progress = max(0, min(100, int(value)))
        bar.text = f"{bar.progress} %"
        bar.textVisible = True
        bar.textAlignment = Qt.AlignmentFlag.AlignCenter
        bar.state = QStyle.StateFlag.State_Enabled
        style = QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter)


class TransferTable(QTreeWidget):
    """Seznam souborů ve frontě: stav a vlastní ukazatel průběhu u každého."""

    COL_NAME, COL_SIZE, COL_STATUS, COL_PROGRESS = range(4)

    STATUSES = (
        "pending",
        "verifying",
        "downloading",
        "done",
        "skipped",
        "failed",
        "cancelled",
    )

    @staticmethod
    def status_text(status: str) -> str:
        """Název stavu v aktuálním jazyce; neznámý stav se vypíše, jak přišel."""
        key = f"transfer.{status}"
        label = t(key)
        return status if label == key else label

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._rows: dict[str, QTreeWidgetItem] = {}
        self._colors: dict[str, QColor] = {}
        self.retranslate()
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.setItemDelegateForColumn(self.COL_PROGRESS, ProgressDelegate(self))
        header = self.header()
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        for column in (self.COL_SIZE, self.COL_STATUS):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            self.COL_PROGRESS, QHeaderView.ResizeMode.Fixed
        )
        header.resizeSection(self.COL_PROGRESS, 190)

    def set_colors(self, *, done: str, failed: str, muted: str) -> None:
        self._colors = {
            "done": QColor(done),
            "skipped": QColor(muted),
            "failed": QColor(failed),
            "cancelled": QColor(muted),
        }
        for key, item in self._rows.items():
            status = item.data(self.COL_STATUS, Qt.ItemDataRole.UserRole)
            if status:
                self._paint_status(item, status)

    def set_rows(self, rows: Iterable[tuple[str, str, str]]) -> None:
        """``rows`` = (klíč, název souboru, velikost).

        Nesmí se jmenovat ``reset`` – to je virtuální slot QTreeWidget,
        který Qt volá samo zevnitř ``clear()``.
        """
        self.clear()
        self._rows.clear()
        for key, name, size in rows:
            item = QTreeWidgetItem([name, size, self.status_text("pending"), ""])
            item.setTextAlignment(self.COL_SIZE, Qt.AlignmentFlag.AlignRight
                                  | Qt.AlignmentFlag.AlignVCenter)
            item.setData(self.COL_PROGRESS, Qt.ItemDataRole.UserRole, 0)
            item.setData(self.COL_STATUS, Qt.ItemDataRole.UserRole, "pending")
            self.addTopLevelItem(item)
            self._rows[key] = item

    def set_progress(self, key: str, percent: float) -> None:
        item = self._rows.get(key)
        if item is not None:
            item.setData(self.COL_PROGRESS, Qt.ItemDataRole.UserRole, percent)

    def set_status(self, key: str, status: str) -> None:
        item = self._rows.get(key)
        if item is None:
            return
        item.setText(self.COL_STATUS, self.status_text(status))
        item.setData(self.COL_STATUS, Qt.ItemDataRole.UserRole, status)
        if status in ("done", "skipped"):
            item.setData(self.COL_PROGRESS, Qt.ItemDataRole.UserRole, 100)
        self._paint_status(item, status)
        if status == "downloading":
            self.scrollToItem(item)

    def retranslate(self) -> None:
        """Přepíše hlavičku a stavy do nového jazyka, bez ztráty průběhu."""
        self.setHeaderLabels(
            [
                t("transfer.file"),
                t("transfer.size"),
                t("transfer.status"),
                t("transfer.progress"),
            ]
        )
        for item in self._rows.values():
            status = item.data(self.COL_STATUS, Qt.ItemDataRole.UserRole)
            if status:
                item.setText(self.COL_STATUS, self.status_text(status))

    def _paint_status(self, item: QTreeWidgetItem, status: str) -> None:
        color = self._colors.get(status)
        if color is not None:
            item.setForeground(self.COL_STATUS, color)
