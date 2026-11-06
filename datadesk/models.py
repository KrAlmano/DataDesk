"""Qt table adapter and reversible in-memory document edits."""

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from .core import display_value, infer_kind
from .translations_engine import tr


@dataclass
class Document:
    frame: pd.DataFrame
    history: list[pd.DataFrame] = field(default_factory=list)
    future: list[pd.DataFrame] = field(default_factory=list)
    revision: int = 0

    def checkpoint(self):
        self.history.append(self.frame.copy(deep=True))
        self.history = self.history[-10:]
        self.future.clear()
        self.revision += 1

    def edit(self, row: int, column: str, value):
        self.checkpoint()
        # Object storage allows a deliberate edit without coercing other cells.
        self.frame[column] = self.frame[column].astype(object)
        self.frame.at[row, column] = value

    def add(self, values: dict):
        self.checkpoint()
        next_id = int(max(self.frame.index, default=-1)) + 1
        self.frame = self.frame.astype(object)
        self.frame.loc[next_id] = [values.get(c, None) for c in self.frame.columns]

    def delete(self, rows: list[int]):
        self.checkpoint()
        self.frame = self.frame.drop(index=rows)

    def undo(self):
        if not self.history:
            return
        self.future.append(self.frame.copy(deep=True))
        self.frame = self.history.pop()
        self.revision += 1

    def redo(self):
        if not self.future:
            return
        self.history.append(self.frame.copy(deep=True))
        self.frame = self.future.pop()
        self.revision += 1


class TableModel(QAbstractTableModel):
    """Only visible cells are formatted; all rows remain available to export."""

    def __init__(self, edit: Callable, parent=None):
        super().__init__(parent)
        self.frame = pd.DataFrame()
        self.edit_callback = edit
        self.kinds = {}
        self.editable = True

    def replace(self, frame, kinds=None):
        self.beginResetModel()
        self.frame = frame
        self.kinds = kinds or {c: infer_kind(frame[c]) for c in frame.columns}
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.frame) or index.column() >= len(self.frame.columns):
            return None
        value = self.frame.iat[index.row(), index.column()]
        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            if pd.api.types.is_bool(value):
                return tr("Evet") if value else tr("Hayır")
            return display_value(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role == Qt.ItemDataRole.ForegroundRole and display_value(value) == "":
            return QColor("#9aa8a7")
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if section < 0 or section >= (
            len(self.frame.columns) if orientation == Qt.Orientation.Horizontal else len(self.frame)
        ):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.frame.columns[section])
            return str(section + 1)
        if role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Horizontal:
            kinds = {
                "text": tr("Metin"),
                "number": tr("Sayı"),
                "date": tr("Tarih"),
                "boolean": tr("Mantıksal"),
            }
            kind = self.kinds.get(self.frame.columns[section], "text")
            return tr(
                "{column} · {kind}\nSıralamak için tıklayın.",
                column=self.frame.columns[section],
                kind=kinds.get(kind, kind),
            )
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and self.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if (
            role != Qt.ItemDataRole.EditRole
            or not index.isValid()
            or not self.editable
            or index.row() >= len(self.frame)
            or index.column() >= len(self.frame.columns)
        ):
            return False
        row = self.frame.index[index.row()]
        col = self.frame.columns[index.column()]
        if self.data(index, Qt.ItemDataRole.EditRole) == str(value):
            return False
        return bool(self.edit_callback(row, col, value))
