"""A small file browser for a real, local DataDesk working directory."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .i18n import language, tr
from . import translations_workspace as _translations_workspace  # noqa: F401
from .widgets import ElidedLabel


TABLE_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".csv", ".tsv"}
FILE_LABELS = {
    ".xlsx": "Excel",
    ".xls": "Excel 97–2003",
    ".xlsm": "Excel (makrolu)",
    ".csv": "CSV",
    ".tsv": "TSV",
}
PATH_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


def _size_label(size):
    if size < 1024:
        return f"{size} B"
    formatted = f"{size / 1024:.1f} KB" if size < 1024**2 else f"{size / 1024**2:.1f} MB"
    return formatted.replace(".", ",") if language() == "tr" else formatted


def _modified_label(timestamp):
    pattern = "%d.%m.%Y %H:%M" if language() == "tr" else "%Y-%m-%d %H:%M"
    return datetime.fromtimestamp(timestamp).strftime(pattern)


class FileItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        return self.data(column, SORT_ROLE) < other.data(column, SORT_ROLE)


class WorkspaceBrowser(QWidget):
    """Navigate actual folders; the parent owns mutations and their dialogs.

    Every emitted path is absolute. Navigation stays inside the chosen root,
    including when a directory contains symbolic links. Changing the root or
    navigating does not create, rename, import, or otherwise modify any file.
    """

    open_requested = Signal(object)
    new_folder_requested = Signal(object)
    new_file_requested = Signal(object)
    import_requested = Signal(object)
    import_files_requested = Signal(object, object)
    rename_requested = Signal(object)
    move_requested = Signal(object)
    root_requested = Signal()
    directory_changed = Signal(object)

    def __init__(self, root=None, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaceBrowser")
        self.setMinimumWidth(0)
        self.setAcceptDrops(True)
        self._root = None
        self._current = None
        self._history = []
        self._build()
        if root is not None:
            self.set_root(root)
        else:
            self._update_controls()

    @property
    def current_directory(self):
        return self._current

    @property
    def root_directory(self):
        return self._root

    def _build(self):
        layout = QVBoxLayout(self)
        # Let resizeEvent choose which toolbar actions fit before a previous
        # font size can impose a stale minimum width on the whole browser.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        navigation = QHBoxLayout()
        navigation.setSpacing(6)
        self.back_button = self._navigation_button(tr("Önceki klasör"), "←")
        self.back_button.clicked.connect(self.go_back)
        navigation.addWidget(self.back_button)
        self.up_button = self._navigation_button(tr("Üst klasör"), "↑")
        self.up_button.clicked.connect(self.go_up)
        navigation.addWidget(self.up_button)
        self.breadcrumb = QLineEdit()
        self.breadcrumb.setObjectName("breadcrumb")
        self.breadcrumb.setReadOnly(True)
        self.breadcrumb.setAccessibleName(tr("Geçerli klasörün yolu"))
        self.breadcrumb.setPlaceholderText(tr("Çalışma klasörü"))
        self.breadcrumb.setMinimumWidth(0)
        navigation.addWidget(self.breadcrumb, 1)
        self.refresh_button = self._navigation_button(tr("Yenile"), "↻")
        self.refresh_button.clicked.connect(self.refresh)
        navigation.addWidget(self.refresh_button)
        layout.addLayout(navigation)

        self.toolbar_widget = QWidget()
        self.toolbar_widget.setObjectName("workspaceToolbar")
        toolbar = QHBoxLayout(self.toolbar_widget)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        self.folder_title = ElidedLabel(tr("Dosyalar"))
        self.folder_title.setObjectName("folderTitle")
        self.folder_title.setTextFormat(Qt.TextFormat.PlainText)
        self.folder_title.setMinimumWidth(0)
        self.folder_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self.folder_title, 1)
        self.new_file_button = QPushButton(tr("Yeni dosya"))
        self.new_file_button.clicked.connect(self._new_file)
        toolbar.addWidget(self.new_file_button)
        self.new_folder_button = QPushButton(tr("Yeni klasör"))
        self.new_folder_button.clicked.connect(self._new_folder)
        toolbar.addWidget(self.new_folder_button)
        self.import_button = QPushButton(tr("İçe aktar"))
        self.import_button.clicked.connect(self._import)
        toolbar.addWidget(self.import_button)
        self.more_button = QToolButton()
        self.more_button.setText("⋯")
        self.more_button.setAccessibleName(tr("Dosya ve klasör işlemleri"))
        self.more_button.setToolTip(tr("Dosya ve klasör işlemleri"))
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self.more_button)
        self.new_file_action = self.more_menu.addAction(tr("Yeni dosya…"), self._new_file)
        self.new_folder_action = self.more_menu.addAction(tr("Yeni klasör…"), self._new_folder)
        self.import_action = self.more_menu.addAction(tr("İçe aktar…"), self._import)
        self.more_menu.addSeparator()
        self.rename_action = self.more_menu.addAction(tr("Yeniden adlandır…"), self._rename)
        self.move_action = self.more_menu.addAction(tr("Taşı…"), self._move)
        self.more_menu.addSeparator()
        self.more_menu.addAction(tr("Çalışma klasörünü değiştir…"), self.root_requested.emit)
        self.more_button.setMenu(self.more_menu)
        toolbar.addWidget(self.more_button)
        layout.addWidget(self.toolbar_widget)

        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.file_list = QTreeWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setAccessibleName(tr("Çalışma klasöründeki dosyalar"))
        self.file_list.setHeaderLabels([tr("Ad"), tr("Tür"), tr("Değiştirilme"), tr("Boyut")])
        self.file_list.setRootIsDecorated(False)
        self.file_list.setItemsExpandable(False)
        self.file_list.setUniformRowHeights(True)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_list.setSortingEnabled(True)
        self.file_list.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._context_menu)
        self.file_list.itemActivated.connect(lambda item, _: self._open_item(item))
        self.file_list.itemSelectionChanged.connect(self._update_selection)
        self.file_list.installEventFilter(self)
        self.file_list.viewport().setAcceptDrops(False)
        header = self.file_list.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.file_list, 1)

        self.empty_label = QLabel(tr("Bir çalışma klasörü seçin."), self.file_list.viewport())
        self.empty_label.setObjectName("emptyHint")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.file_list.viewport().installEventFilter(self)

        self.footer = QLabel(tr("Excel, CSV ve TSV dosyaları"))
        self.footer.setObjectName("hint")
        self.footer.setTextFormat(Qt.TextFormat.PlainText)
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)

        self._shortcuts = []
        for sequence, callback in [("Alt+Left", self.go_back), ("Alt+Up", self.go_up), ("F5", self.refresh)]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _navigation_button(self, text, symbol):
        widget = QToolButton()
        # Text symbols follow the active foreground palette, including theme
        # changes, whereas native standard arrow icons can remain black.
        widget.setText(symbol)
        widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        widget.setAccessibleName(text)
        widget.setToolTip(text)
        return widget

    def _within_root(self, path):
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
            if self._root is None or not resolved.is_relative_to(self._root):
                return None
            return resolved
        except (OSError, RuntimeError, ValueError):
            return None

    def set_root(self, root):
        """Choose an existing directory without creating or changing any file."""
        try:
            path = Path(root).expanduser().resolve(strict=True)
            if not path.is_dir():
                raise ValueError(tr("Bir klasör seçin."))
        except (OSError, RuntimeError, ValueError):
            self._error(tr("Çalışma klasörü bulunamadı veya açılamıyor."))
            return False
        self._root = path
        self._current = path
        self._history.clear()
        self.refresh()
        self.directory_changed.emit(path)
        return True

    def navigate(self, path):
        if self._root is None:
            return False
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self._current / candidate
        resolved = self._within_root(candidate)
        if resolved is None or not resolved.is_dir():
            self._error(tr("Bu klasöre erişilemiyor. Çalışma klasörünüzün içinden bir klasör seçin."))
            return False
        if resolved != self._current:
            self._history.append(self._current)
            self._current = resolved
        self.refresh()
        self.directory_changed.emit(resolved)
        return True

    def go_back(self):
        while self._history:
            path = self._history.pop()
            resolved = self._within_root(path)
            if resolved is not None and resolved.is_dir():
                self._current = resolved
                self.refresh()
                self.directory_changed.emit(resolved)
                return
        self._update_controls()

    def go_up(self):
        if self._current is not None and self._current != self._root:
            self.navigate(self._current.parent)

    def refresh(self):
        if self._root is None or self._current is None:
            self._update_controls()
            return
        selected = self.selected_path()
        self.error_label.hide()
        resolved = self._within_root(self._current)
        # A folder can disappear or be replaced by an escaping symbolic link
        # while the app is open. Fall back to the nearest existing safe parent.
        if resolved is None or not resolved.is_dir():
            previous = self._current
            while self._current != self._root:
                self._current = self._current.parent
                resolved = self._within_root(self._current)
                if resolved is not None and resolved.is_dir():
                    break
            if resolved is None or not resolved.is_dir():
                self.file_list.clear()
                self._error(tr("Çalışma klasörüne erişilemiyor. Menüden başka bir klasör seçebilirsiniz."))
                self._update_controls()
                return
            if previous != self._current:
                self.directory_changed.emit(self._current)
        self._current = resolved
        self.file_list.setSortingEnabled(False)
        self.file_list.clear()
        count_files = count_folders = 0
        try:
            children = list(self._current.iterdir())
            for child in children:
                if child.name.startswith(".") or child.name.startswith("~$"):
                    continue
                safe = self._within_root(child)
                if safe is None:
                    continue
                try:
                    is_folder = safe.is_dir()
                    if not is_folder and (not safe.is_file() or child.suffix.lower() not in TABLE_EXTENSIONS):
                        continue
                    details = child.stat()
                except OSError:
                    continue
                kind = tr("Klasör") if is_folder else tr(FILE_LABELS[child.suffix.lower()])
                item = FileItem(
                    [
                        child.name,
                        kind,
                        _modified_label(details.st_mtime),
                        "—" if is_folder else _size_label(details.st_size),
                    ]
                )
                item.setData(0, PATH_ROLE, child)
                for column, value in enumerate(
                    [child.name.casefold(), kind, details.st_mtime, 0 if is_folder else details.st_size]
                ):
                    item.setData(column, SORT_ROLE, (not is_folder, value))
                icon = QStyle.StandardPixmap.SP_DirIcon if is_folder else QStyle.StandardPixmap.SP_FileIcon
                item.setIcon(0, self.style().standardIcon(icon))
                item.setToolTip(0, str(child))
                item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.file_list.addTopLevelItem(item)
                if child == selected:
                    self.file_list.setCurrentItem(item)
                if is_folder:
                    count_folders += 1
                else:
                    count_files += 1
        except OSError:
            self._error(tr("Bu klasörün içeriği okunamadı. Erişim izinlerini kontrol edin."))
        finally:
            self.file_list.setSortingEnabled(True)
        self.empty_label.setText(tr("Bu klasör boş.\nYeni dosya oluşturun veya dosyalarınızı içe aktarın."))
        self.footer.setText(tr("{folders} klasör · {files} dosya", folders=count_folders, files=count_files))
        self._update_controls()

    def selected_path(self):
        items = self.file_list.selectedItems()
        return items[0].data(0, PATH_ROLE) if items else None

    def _open_item(self, item):
        path = item.data(0, PATH_ROLE)
        safe = self._within_root(path)
        if safe is None:
            self._error(tr("Dosya bulunamadı veya çalışma klasörünün dışında."))
        elif safe.is_dir():
            self.navigate(path)
        elif safe.is_file() and path.suffix.lower() in TABLE_EXTENSIONS:
            self.open_requested.emit(path)

    def _new_folder(self):
        if self._current is not None:
            self.new_folder_requested.emit(self._current)

    def _new_file(self):
        if self._current is not None:
            self.new_file_requested.emit(self._current)

    def _import(self):
        if self._current is not None:
            self.import_requested.emit(self._current)

    def _rename(self):
        path = self.selected_path()
        if path is not None:
            self.rename_requested.emit(path)

    def _move(self):
        path = self.selected_path()
        if path is not None:
            self.move_requested.emit(path)

    def _update_selection(self):
        selected = self.selected_path() is not None
        self.rename_action.setEnabled(selected)
        self.move_action.setEnabled(selected)

    def _update_controls(self):
        valid_path = self._within_root(self._current) if self._current is not None else None
        valid = valid_path is not None and valid_path.is_dir()
        self.back_button.setEnabled(bool(self._history))
        self.up_button.setEnabled(valid and self._current != self._root)
        for control in (
            self.new_file_button,
            self.new_folder_button,
            self.import_button,
            self.new_file_action,
            self.new_folder_action,
            self.import_action,
            self.refresh_button,
        ):
            control.setEnabled(valid)
        if valid:
            relative = self._current.relative_to(self._root)
            parts = [self._root.name or str(self._root), *relative.parts]
            self.breadcrumb.setText(" / ".join(parts))
            self.breadcrumb.setCursorPosition(len(self.breadcrumb.text()))
            self.breadcrumb.setToolTip(str(self._current))
            self.folder_title.setText(self._current.name or str(self._current))
            self.folder_title.setToolTip(str(self._current))
        self.empty_label.setVisible(self.file_list.topLevelItemCount() == 0)
        self._update_selection()
        self._adapt_layout()

    def _error(self, text):
        self.error_label.setText(text)
        self.error_label.show()

    def _context_menu(self, point):
        item = self.file_list.itemAt(point)
        menu = QMenu(self)
        if item is not None:
            self.file_list.setCurrentItem(item)
            menu.addAction(tr("Aç"), lambda: self._open_item(item))
            menu.addSeparator()
            menu.addAction(tr("Yeniden adlandır…"), self._rename)
            menu.addAction(tr("Taşı…"), self._move)
            menu.addAction(
                tr("Yolu kopyala"), lambda: QApplication.clipboard().setText(str(self.selected_path()))
            )
        else:
            menu.addAction(tr("Yeni dosya…"), self._new_file).setEnabled(self._current is not None)
            menu.addAction(tr("Yeni klasör…"), self._new_folder).setEnabled(self._current is not None)
            menu.addAction(tr("İçe aktar…"), self._import).setEnabled(self._current is not None)
        menu.exec(self.file_list.viewport().mapToGlobal(point))

    def _adapt_layout(self):
        # Toolbar actions remain in the overflow menu when text is magnified.
        room = self.width()
        wanted = (
            sum(
                widget.sizeHint().width()
                for widget in (
                    self.new_file_button,
                    self.new_folder_button,
                    self.import_button,
                    self.more_button,
                )
            )
            + 120
        )
        self.import_button.setVisible(room >= wanted)
        self.new_folder_button.setVisible(room >= wanted - self.import_button.sizeHint().width())
        unit = max(1, self.fontMetrics().height())
        self.file_list.setColumnHidden(1, room < unit * 40)
        self.file_list.setColumnHidden(2, room < unit * 29)
        self.file_list.setColumnHidden(3, room < unit * 22)
        self.file_list.setColumnWidth(1, unit * 7)
        self.file_list.setColumnWidth(2, unit * 11)
        self.file_list.setColumnWidth(3, unit * 5)
        self.empty_label.setGeometry(self.file_list.viewport().rect().adjusted(16, 12, -16, -12))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "file_list"):
            self._adapt_layout()

    def eventFilter(self, watched, event):
        if watched is self.file_list and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_F2:
                self._rename()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.file_list.currentItem()
                if item is not None:
                    self._open_item(item)
                return True
        if watched is self.file_list.viewport() and event.type() == QEvent.Type.Resize:
            self.empty_label.setGeometry(watched.rect().adjusted(16, 12, -16, -12))
        return super().eventFilter(watched, event)

    @staticmethod
    def _dropped_files(mime: QMimeData):
        if not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            try:
                if path.is_file() and path.suffix.lower() in TABLE_EXTENSIONS and path not in paths:
                    paths.append(path)
            except OSError:
                continue
        return paths

    def dragEnterEvent(self, event):
        if self._current is not None and self._dropped_files(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self._dropped_files(event.mimeData())
        if paths and self._current is not None:
            self.import_files_requested.emit(paths, self._current)
            event.acceptProposedAction()
