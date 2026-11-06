"""The DataDesk workspace. Data, filters and displayed results stay separate."""

from pathlib import Path
from datetime import date, datetime
from numbers import Integral
import re

import pandas as pd
from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .core import FilterRule, apply_filters, display_value, infer_kind, parse_date, parse_number, sort_frame
from .dialogs import ExportDialog, ImportDialog, RowDialog, demo_frame
from .io import ImportOptions, inspect_file, read_table, write_table
from .models import Document, TableModel
from .theme import STYLE


OPERATORS = [
    ("İçerir", "contains"),
    ("İçermez", "not_contains"),
    ("Eşittir", "equals"),
    ("Eşit değildir", "not_equals"),
    ("İle başlar", "starts_with"),
    ("İle biter", "ends_with"),
    ("Arasında (dahil)", "between"),
    ("Büyüktür / sonradır", "gt"),
    ("Büyük veya eşit", "gte"),
    ("Küçüktür / öncedir", "lt"),
    ("Küçük veya eşit", "lte"),
    ("Tüm kelimeleri içerir (VE)", "all_words"),
    ("Bir kelimeyi içerir (VEYA)", "any_words"),
    ("Listedekilerden biri", "in"),
    ("Boştur", "is_empty"),
    ("Boş değildir", "not_empty"),
]
KIND_LABELS = {"text": "Metin", "number": "Sayı", "date": "Tarih", "boolean": "Mantıksal"}


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


class TaskSignals(QObject):
    finished = Signal(int, object, str)


class Task(QRunnable):
    def __init__(self, task_id, function):
        super().__init__()
        self.task_id = task_id
        self.function = function
        self.signals = TaskSignals()

    @Slot()
    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            self.signals.finished.emit(self.task_id, None, str(exc) or type(exc).__name__)
        else:
            self.signals.finished.emit(self.task_id, result, "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataDesk")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)
        self.settings = QSettings("DataDesk", "DataDesk")
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.tasks = {}
        self.task_id = 0
        self.busy = False
        self.document = None
        self.source_path = None
        self.source_name = ""
        self.rules = []
        self.match = "all"
        self.search_text = ""
        self.sort_column = None
        self.sort_ascending = True
        self.kinds = {}
        self.number_formats = {}
        self.dirty = False
        self.view_revision = 0
        self.kinds_revision = 0
        self.import_dialog = None
        self.model = TableModel(self.edit_cell, self)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.apply_view)
        self._build()
        self._menus()
        self._recent()
        self._controls()

    def _build(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(20, 28, 20, 22)
        side_layout.setSpacing(12)
        brand = QHBoxLayout()
        mark = label("D", "brandMark")
        mark.setFixedSize(39, 39)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark)
        brand.addWidget(label("DataDesk", "brand"))
        side_layout.addLayout(brand)
        subtitle = label("Veriden sonuca, kolayca.")
        subtitle.setStyleSheet("font-size: 11px; margin-bottom: 24px;")
        side_layout.addWidget(subtitle)
        self.open_button = button("＋  Dosya aç", self.open_file, "primary")
        self.open_button.setToolTip("Excel, CSV veya TSV aç · Ctrl/Cmd+O")
        side_layout.addWidget(self.open_button)
        self.demo_button = button("▦  Örnek veriyi keşfet", self.open_demo)
        side_layout.addWidget(self.demo_button)
        side_layout.addSpacing(24)
        recent_label = label("SON AÇILANLAR")
        recent_label.setStyleSheet("font-size: 10px; letter-spacing: 1px; font-weight: 700;")
        side_layout.addWidget(recent_label)
        self.recent_list = QListWidget()
        self.recent_list.setWordWrap(True)
        self.recent_list.itemClicked.connect(lambda item: self.open_path(item.data(Qt.ItemDataRole.UserRole)))
        side_layout.addWidget(self.recent_list, 1)
        self.clear_recent = button("Geçmişi temizle", self.clear_history)
        side_layout.addWidget(self.clear_recent)
        side_layout.addSpacing(12)
        privacy = label(
            "YEREL ÇALIŞMA ALANI\n\nDosyalarınız cihazınızda kalır.\nKaynak dosyalar değiştirilmez."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet("font-size: 11px; line-height: 1.4; color: #9bb5a8;")
        side_layout.addWidget(privacy)
        outer.addWidget(side)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(28, 25, 28, 16)
        main_layout.setSpacing(16)
        top = QHBoxLayout()
        top.addWidget(label("ÇALIŞMA ALANI  /  VERİ DÜZENLEYİCİ", "eyebrow"))
        top.addStretch()
        top.addWidget(label("●  Cihazınızda çalışır", "badge"))
        main_layout.addLayout(top)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label("Verilerinize netlik katın.", "title"))
        self.subtitle = label("Dosyanızı açın, filtrelerinizi belirleyin, sonucu paylaşın.", "muted")
        titles.addWidget(self.subtitle)
        heading.addLayout(titles, 1)
        self.export_button = button("Dışa aktar  ↗", self.export_file, "primary")
        self.export_button.setMinimumHeight(40)
        heading.addWidget(self.export_button)
        main_layout.addLayout(heading)
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.stats = {}
        for key, title, hint in [
            ("rows", "GÖSTERİLEN SATIR", "Tüm satırlar çıktıya dahildir"),
            ("columns", "SÜTUN", "Kaynak değerleri korunur"),
            ("filters", "AKTİF FİLTRE", "Sonuçları birlikte daraltın"),
        ]:
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 13, 18, 13)
            card_layout.setSpacing(3)
            card_layout.addWidget(label(title, "eyebrow"))
            value = label("—", "statValue")
            card_layout.addWidget(value)
            card_layout.addWidget(label(hint, "muted"))
            self.stats[key] = value
            stats.addWidget(card)
        main_layout.addLayout(stats)
        self.notice = label("", "notice")
        self.notice.setWordWrap(True)
        self.notice.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.notice.hide()
        main_layout.addWidget(self.notice)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        main_layout.addWidget(self.progress)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)
        self._table_panel()
        self._filter_panel()
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([820, 300])
        main_layout.addWidget(self.splitter, 1)
        self.footer = label("01  DOSYAYI AÇ      →      02  FİLTRELE      →      03  DIŞA AKTAR", "eyebrow")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.footer)
        outer.addWidget(main, 1)
        self.statusBar().showMessage("Hazır · Excel, CSV veya TSV dosyasını pencereye sürükleyebilirsiniz.")

    def _table_panel(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setMinimumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 12, 16, 12)
        self.file_label = label("Veri tablosu", "sectionTitle")
        self.file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self.file_label, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tüm sütunlarda ara…")
        self.search.setAccessibleName("Tüm sütunlarda ara")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(lambda _: self.search_timer.start())
        toolbar.addWidget(self.search)
        layout.addLayout(toolbar)
        self.stack = QStackedWidget()
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(32, 30, 32, 30)
        empty_layout.addStretch()
        icon = label("▦")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 64px; color: #91b49c;")
        empty_layout.addWidget(icon)
        welcome = label("Bir dosyayla başlayın", "sectionTitle")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(welcome)
        desc = label(
            "Excel veya CSV dosyanızı buraya sürükleyin.\nSayfa ve başlıkları kontrol edip filtrelemeye başlayın.",
            "muted",
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        empty_layout.addWidget(desc)
        empty_button = button("Dosya seç", self.open_file, "primary")
        empty_button.setFixedWidth(180)
        empty_layout.addSpacing(15)
        empty_layout.addWidget(empty_button, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        self.stack.addWidget(empty)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(37)
        self.table.verticalHeader().setMinimumWidth(44)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by)
        self.table.horizontalHeader().setDefaultSectionSize(155)
        self.table.horizontalHeader().setMinimumSectionSize(65)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.stack.addWidget(self.table)
        no_results = QWidget()
        no_layout = QVBoxLayout(no_results)
        no_layout.addStretch()
        no_title = label("Eşleşen satır bulunamadı", "sectionTitle")
        no_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_layout.addWidget(no_title)
        no_desc = label(
            "Filtreleri veya arama metnini değiştirin.\nDışa aktarırken sütun başlıkları yine korunur.",
            "muted",
        )
        no_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_layout.addWidget(no_desc)
        reset = button("Görünümü sıfırla", self.reset_view)
        no_layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignCenter)
        no_layout.addStretch()
        self.stack.addWidget(no_results)
        layout.addWidget(self.stack, 1)
        actions = QHBoxLayout()
        actions.setContentsMargins(14, 10, 14, 10)
        self.add_button = button("＋ Satır", self.add_row)
        self.delete_button = button("Seçili satırları sil", self.delete_rows, "danger")
        self.undo_button = button("↶", self.undo)
        self.undo_button.setToolTip("Düzenlemeyi geri al · Ctrl/Cmd+Z (son 10 işlem)")
        self.redo_button = button("↷", self.redo)
        self.redo_button.setToolTip("Düzenlemeyi yinele · Ctrl/Cmd+Shift+Z")
        actions.addWidget(self.add_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        layout.addLayout(actions)
        self.splitter.addWidget(panel)

    def _filter_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(380)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QFrame()
        panel.setObjectName("filterPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(label("Filtreler", "sectionTitle"))
        heading.addStretch()
        self.reset_button = button("Sıfırla", self.reset_view)
        heading.addWidget(self.reset_button)
        layout.addLayout(heading)
        explanation = label("Koşul ekleyin, sonuçlarınızı daraltın.", "muted")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.filter_tabs = QTabWidget()
        self.filter_tabs.setDocumentMode(True)
        self.filter_tabs.tabBar().setDrawBase(False)
        builder = QWidget()
        build = QVBoxLayout(builder)
        build.setContentsMargins(0, 12, 0, 0)
        build.setSpacing(8)
        active = QWidget()
        active_layout = QVBoxLayout(active)
        active_layout.setContentsMargins(0, 12, 0, 0)
        active_layout.setSpacing(10)
        self.filter_tabs.addTab(builder, "Koşul ekle")
        self.filter_tabs.addTab(active, "Aktif (0)")
        layout.addWidget(self.filter_tabs, 1)
        build.addWidget(label("SÜTUN", "eyebrow"))
        self.column = QComboBox()
        self.column.setAccessibleName("Filtre sütunu")
        self.column.currentIndexChanged.connect(self._column_changed)
        build.addWidget(self.column)
        self.type_label = label("Bir dosya açın", "muted")
        build.addWidget(self.type_label)
        self.kind = QComboBox()
        for text, value in [
            ("Otomatik veri türü", "auto"),
            ("Metin olarak işle", "text"),
            ("Sayı olarak işle", "number"),
            ("Tarih olarak işle", "date"),
            ("Mantıksal olarak işle", "boolean"),
        ]:
            self.kind.addItem(text, value)
        self.kind.setToolTip("Yalnızca eklenecek koşulun türünü belirler; kaynak değerleri değiştirmez.")
        self.kind.currentIndexChanged.connect(self._operator_changed)
        build.addWidget(self.kind)
        self.number_format = QComboBox()
        self.number_format.addItem("Sayı biçimi: otomatik", "auto")
        self.number_format.addItem("Türkçe · 1.234,56", "tr")
        self.number_format.addItem("İngilizce · 1,234.56", "us")
        self.number_format.setToolTip(
            "Tek ayraçlı sayılar belirsiz olabilir. 1.234 değerini bin iki yüz otuz dört okumak için Türkçe seçin. Seçim bu sütunun sıralamasında da kullanılır."
        )
        self.number_format.currentIndexChanged.connect(self._number_format_changed)
        build.addWidget(self.number_format)
        build.addWidget(label("KOŞUL", "eyebrow"))
        self.operator = QComboBox()
        for text, value in OPERATORS:
            self.operator.addItem(text, value)
        self.operator.currentIndexChanged.connect(self._operator_changed)
        build.addWidget(self.operator)
        self.value = QLineEdit()
        self.value.setPlaceholderText("Değer girin…")
        self.value.setAccessibleName("Filtre değeri")
        self.value.returnPressed.connect(self.add_filter)
        build.addWidget(self.value)
        self.value2 = QLineEdit()
        self.value2.setPlaceholderText("Üst sınır (dahil)")
        self.value2.setAccessibleName("Filtre üst sınırı")
        self.value2.returnPressed.connect(self.add_filter)
        self.value2.hide()
        build.addWidget(self.value2)
        self.filter_hint = label("Metin araması büyük/küçük harfe duyarsızdır.", "muted")
        self.filter_hint.setWordWrap(True)
        self.filter_hint.setStyleSheet("font-size: 11px;")
        build.addWidget(self.filter_hint)
        self.filter_button = button("＋  Filtre ekle", self.add_filter, "primary")
        build.addWidget(self.filter_button)
        self.filter_error = label("", "error")
        self.filter_error.setWordWrap(True)
        self.filter_error.hide()
        build.addWidget(self.filter_error)
        build.addStretch()
        active_layout.addWidget(label("KOŞULLARI BİRLEŞTİR", "eyebrow"))
        self.match_combo = QComboBox()
        self.match_combo.addItem("Tümü eşleşsin (VE)", "all")
        self.match_combo.addItem("Biri eşleşsin (VEYA)", "any")
        self.match_combo.currentIndexChanged.connect(self.change_match)
        active_layout.addWidget(self.match_combo)
        self.rule_list = QListWidget()
        self.rule_list.setMinimumHeight(100)
        self.rule_list.setWordWrap(True)
        self.rule_list.setToolTip("Kaldırmak istediğiniz koşulu seçin.")
        active_layout.addWidget(self.rule_list, 1)
        self.remove_button = button("Seçili filtreyi kaldır", self.remove_filter)
        active_layout.addWidget(self.remove_button)
        tips = label(
            "İPUCU\n\nSıralamak için sütun başlığına tıklayın. Hücreyi düzenlemek için çift tıklayın.",
            "muted",
        )
        tips.setWordWrap(True)
        tips.setStyleSheet("font-size: 11px; padding-top: 8px;")
        active_layout.addWidget(tips)
        scroll.setWidget(panel)
        self.splitter.addWidget(scroll)

    def _menus(self):
        menu = self.menuBar().addMenu("Dosya")
        for title, shortcut, callback in [
            ("Dosya aç…", QKeySequence.StandardKey.Open, self.open_file),
            ("Dışa aktar…", "Ctrl+Shift+E", self.export_file),
            ("Örnek veriyi aç", None, self.open_demo),
        ]:
            action = QAction(title, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(callback)
            menu.addAction(action)
        edit = self.menuBar().addMenu("Düzenle")
        for title, shortcut, callback in [
            ("Geri al", QKeySequence.StandardKey.Undo, self.undo),
            ("Yinele", QKeySequence.StandardKey.Redo, self.redo),
            ("Ara", QKeySequence.StandardKey.Find, self.search.setFocus),
        ]:
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            edit.addAction(action)
        help_menu = self.menuBar().addMenu("Yardım")
        about = QAction("DataDesk hakkında", self)
        about.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "DataDesk",
                "<b>DataDesk</b><p>Excel ve CSV için yerel veri çalışma alanı.</p><p>Dosya aç → Filtrele → Dışa aktar</p><p>Kaynak biçim ve makrolar aktarılmaz. Formüller hesaplanmaz; kayıtlı sonuçlar okunur. Excel'de kaydedilmiş güncel sonuçları kullanın.</p>",
            )
        )
        help_menu.addAction(about)
        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.table)
        self.copy_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.copy_shortcut.activated.connect(self.copy_selection)

    def _controls(self):
        available = self.document is not None and not self.busy
        for widget in (
            self.export_button,
            self.search,
            self.column,
            self.kind,
            self.number_format,
            self.operator,
            self.value,
            self.value2,
            self.filter_button,
            self.match_combo,
            self.reset_button,
            self.rule_list,
            self.remove_button,
            self.add_button,
        ):
            widget.setEnabled(available)
        for widget in (self.open_button, self.demo_button, self.recent_list):
            widget.setEnabled(not self.busy)
        self.model.editable = available
        self.table.setEnabled(not self.busy)
        self.delete_button.setEnabled(available and bool(self.table.selectionModel().selectedRows()))
        self.undo_button.setEnabled(available and bool(self.document.history))
        self.redo_button.setEnabled(available and bool(self.document.future))
        self.progress.setVisible(self.busy)
        self._operator_changed()

    def _selection_changed(self, *_):
        self.delete_button.setEnabled(not self.busy and bool(self.table.selectionModel().selectedRows()))

    def _run_task(self, message, function, success, failure=None):
        if self.busy:
            return False
        self.search_timer.stop()
        self.busy = True
        self._controls()
        self.statusBar().showMessage(message)
        self.task_id += 1
        task = Task(self.task_id, function)
        self.tasks[self.task_id] = (task, success, failure)
        task.signals.finished.connect(self._task_finished)
        self.pool.start(task)
        return True

    @Slot(int, object, str)
    def _task_finished(self, task_id, result, error):
        _, success, failure = self.tasks.pop(task_id)
        self.busy = False
        self._controls()
        if error:
            self.statusBar().showMessage("İşlem tamamlanamadı. Mevcut verileriniz korunuyor.")
            if failure:
                failure(error)
            else:
                self.show_error(error)
        else:
            self.statusBar().showMessage("Hazır")
            success(result)
        QTimer.singleShot(0, self._flush_pending_view)

    def _view_stale(self):
        return self.document is not None and (
            self.search.text() != self.search_text or self.document.revision != self.view_revision
        )

    def _flush_pending_view(self):
        if not self.busy and self.import_dialog is None and self._view_stale():
            self.apply_view()

    def show_error(self, message):
        QMessageBox.warning(self, "DataDesk · İşlem tamamlanamadı", message)

    def _confirm_replace(self):
        if not self.dirty:
            return True
        choice = QMessageBox.question(
            self,
            "Düzenlemeleri bırak?",
            "Bellekte dışa aktarılmamış düzenlemeler var. Devam ederseniz bu düzenlemeler kapanır.\n\nÖnce dışa aktarmak için Vazgeç'i seçin.",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return choice == QMessageBox.StandardButton.Discard

    def open_file(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "DataDesk · Dosya seç",
            self.settings.value("last_directory", str(Path.home())),
            "Veri dosyaları (*.xlsx *.xlsm *.xls *.csv *.tsv);;Excel (*.xlsx *.xlsm *.xls);;CSV / TSV (*.csv *.tsv)",
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        if self.busy or not self._confirm_replace():
            return
        path = Path(path).expanduser().resolve()

        def inspect():
            info = inspect_file(path)
            try:
                loaded = read_table(path)
                return info, loaded, ""
            except Exception as exc:
                return info, None, str(exc)

        self._run_task("Dosya inceleniyor…", inspect, lambda result: self._choose_import(path, result))

    def _choose_import(self, path, result):
        info, loaded, error = result
        dialog = ImportDialog(path, info, loaded, error, self)
        self.import_dialog = dialog

        def preview(options):
            dialog.set_busy(True)

            def done(table):
                dialog.set_busy(False)
                dialog.set_preview(table)

            def failed(message):
                dialog.set_busy(False)
                dialog.message.setText(message)

            self._run_task("Önizleme okunuyor…", lambda: read_table(path, options), done, failed)

        dialog.preview_requested.connect(preview)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            options = dialog.options()
            self.import_dialog = None
            self.load_path(path, options)
        else:
            self.import_dialog = None

    def load_path(self, path, options=None):
        """Load explicit options; failed reads never replace the active document."""
        if self.busy:
            return
        path = Path(path).resolve()

        def read():
            loaded = read_table(path, options or ImportOptions())
            kinds = {c: infer_kind(loaded.frame[c]) for c in loaded.frame.columns}
            return loaded, kinds

        def loaded(result):
            table, kinds = result
            name = path.name + (f"  /  {table.sheet}" if table.sheet else "")
            self.set_document(table.frame, name, path, table.warnings, kinds)
            self.settings.setValue("last_directory", str(path.parent))
            recent = self.settings.value("recent_files", [], type=list)
            self.settings.setValue("recent_files", [str(path)] + [p for p in recent if p != str(path)][:7])
            self._recent()

        self._run_task("Dosya okunuyor…", read, loaded)

    def set_document(self, frame, name, path=None, warnings=None, kinds=None):
        frame = frame.reset_index(drop=True).copy()
        self.document = Document(frame)
        self.source_path = Path(path).resolve() if path else None
        self.source_name = name
        self.dirty = False
        self.view_revision = 0
        self.kinds_revision = 0
        self.rules = []
        self.match = "all"
        self.search_text = ""
        self.sort_column = None
        self.kinds = kinds if kinds is not None else {c: infer_kind(frame[c]) for c in frame.columns}
        self.number_formats = {}
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.match_combo.blockSignals(True)
        self.match_combo.setCurrentIndex(0)
        self.match_combo.blockSignals(False)
        self.column.clear()
        self.column.addItems(list(frame.columns))
        self.kind.setCurrentIndex(0)
        self.value.clear()
        self.value2.clear()
        self.operator.setCurrentIndex(0)
        self.rule_list.clear()
        self.filter_tabs.setTabText(1, "Aktif (0)")
        self.filter_tabs.setCurrentIndex(0)
        self.filter_error.hide()
        self.notice.setText("\n".join(warnings or []))
        self.notice.setVisible(bool(warnings))
        self.file_label.setText(name)
        self.file_label.setToolTip(name)
        self.subtitle.setText("Filtreleyin, düzenleyin ve ihtiyacınız olan veriyi dışa aktarın.")
        self.setWindowTitle(f"{name} · DataDesk")
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self._show_frame(frame)
        metrics = self.table.fontMetrics()
        for position, col in enumerate(frame.columns[:200]):
            sample = frame[col].head(100)
            width = (
                max(
                    [
                        metrics.horizontalAdvance(str(col)),
                        *[metrics.horizontalAdvance(display_value(v)) for v in sample],
                    ]
                )
                + 30
            )
            self.table.setColumnWidth(position, min(260, max(90, width)))
        self._controls()

    def open_demo(self):
        if not self.busy and self._confirm_replace():
            self.set_document(
                demo_frame(),
                "Örnek satış verileri",
                warnings=["Örnek veri · Bu kayıtlar uygulamayı denemek için oluşturulmuştur."],
            )

    def _recent(self):
        self.recent_list.clear()
        for path in self.settings.value("recent_files", [], type=list):
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.recent_list.addItem(item)

    def clear_history(self):
        self.settings.remove("recent_files")
        self._recent()

    def _column_changed(self, *_):
        col = self.column.currentText()
        kind = self.kinds.get(col, "text")
        self.type_label.setText("Algılanan tür: " + KIND_LABELS.get(kind, str(kind)))
        if hasattr(self, "number_format"):
            self.number_format.blockSignals(True)
            self.number_format.setCurrentIndex(
                max(0, self.number_format.findData(self.number_formats.get(col, "auto")))
            )
            self.number_format.blockSignals(False)
        if hasattr(self, "operator"):
            self._operator_changed()

    def _number_format_changed(self, *_):
        if self.document is not None and not self.busy:
            self.number_formats[self.column.currentText()] = self.number_format.currentData()
            if self.sort_column == self.column.currentText():
                self.apply_view()

    def _operator_changed(self, *_):
        op = self.operator.currentData()
        kind = self.kind.currentData()
        effective_kind = self.kinds.get(self.column.currentText(), "text") if kind == "auto" else kind
        self.number_format.setVisible(effective_kind == "number")
        self.value2.setVisible(op == "between")
        self.value.setEnabled(
            self.document is not None and not self.busy and op not in ("is_empty", "not_empty")
        )
        self.value.setPlaceholderText("Alt sınır (dahil)" if op == "between" else "Değer girin…")
        hints = {
            "between": "Sayı: 1234,56 veya 1234.56 · Tarih: 31.12.2026. Son günün tamamı dahildir.",
            "in": "Değerleri noktalı virgülle ayırın (ör. 1,5; 2,5). Listede olan satırlar eşleşir.",
            "all_words": "Kelimeleri boşlukla ayırın. Hepsini içeren satırlar eşleşir.",
            "any_words": "Kelimeleri boşlukla ayırın. En az birini içeren satırlar eşleşir.",
            "is_empty": "Boş hücreler ve yalnızca boşluk içeren metinler eşleşir.",
            "not_empty": "İçinde değer olan hücreler eşleşir.",
        }
        self.filter_hint.setText(
            hints.get(
                op,
                "Metin araması büyük/küçük harfe duyarsızdır. Sayı ve tarih karşılaştırmaları veri türüne göre yapılır.",
            )
        )

    def add_filter(self):
        if self.document is None or self.busy:
            return
        kind = self.kind.currentData()
        if kind == "auto":
            kind = self.kinds.get(self.column.currentText(), "text")
        rule = FilterRule(
            column=self.column.currentText(),
            operator=self.operator.currentData(),
            value=self.value.text(),
            value2=self.value2.text(),
            kind=kind,
            number_format=self.number_format.currentData(),
        )
        self.apply_view(rules=[*self.rules, rule])

    def remove_filter(self):
        index = self.rule_list.currentRow()
        if index >= 0 and not self.busy:
            self.apply_view(rules=[r for i, r in enumerate(self.rules) if i != index])

    def change_match(self, *_):
        if self.document is not None and not self.busy:
            self.apply_view(match=self.match_combo.currentData())

    def reset_view(self):
        if self.document is None or self.busy:
            return
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.match_combo.blockSignals(True)
        self.match_combo.setCurrentIndex(0)
        self.match_combo.blockSignals(False)
        self.sort_column = None
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.apply_view(rules=[], match="all")

    def sort_by(self, section):
        if self.document is None or self.busy:
            return
        col = self.model.frame.columns[section]
        ascending = not self.sort_ascending if col == self.sort_column else True
        self.apply_view(sort=(col, ascending))

    def apply_view(self, rules=None, match=None, sort=None, after=None):
        if self.document is None or self.busy:
            return
        # Qt timers call this without arguments. Commit view state only on success.
        proposed = list(self.rules if rules is None else rules)
        combination = self.match if match is None else match
        query = self.search.text()
        column, ascending = sort if sort is not None else (self.sort_column, self.sort_ascending)
        source = self.document.frame
        revision = self.document.revision
        current_kinds = self.kinds
        kinds_revision = self.kinds_revision
        number_format = self.number_formats.get(column, "auto")

        def calculate():
            kinds = (
                current_kinds
                if kinds_revision == revision
                else {c: infer_kind(source[c]) for c in source.columns}
            )
            frame = apply_filters(source, proposed, match=combination, search=query)
            if column:
                frame = sort_frame(
                    frame, column, ascending, kind=kinds.get(column, "auto"), number_format=number_format
                )
            return frame, kinds

        def done(result):
            frame, kinds = result
            self.kinds = kinds
            self.kinds_revision = revision
            self.view_revision = revision
            self.rules = proposed
            self.match = combination
            self.search_text = query
            self.sort_column, self.sort_ascending = column, ascending
            self.filter_error.hide()
            self._rule_labels()
            self._show_frame(frame)
            self._column_changed()
            if column:
                self.table.horizontalHeader().setSortIndicator(
                    list(frame.columns).index(column),
                    Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder,
                )
                self.table.horizontalHeader().setSortIndicatorShown(True)
            if after:
                after()

        def fail(error):
            self.filter_error.setText(error)
            self.filter_error.show()
            self.match_combo.blockSignals(True)
            self.match_combo.setCurrentIndex(0 if self.match == "all" else 1)
            self.match_combo.blockSignals(False)
            # Keep the visible search field consistent with the retained result.
            self.search.blockSignals(True)
            self.search.setText(self.search_text)
            self.search.blockSignals(False)
            self.view_revision = revision

        self._run_task("Filtreler ve sıralama uygulanıyor…", calculate, done, fail)

    def _rule_labels(self):
        self.rule_list.clear()
        self.filter_tabs.setTabText(1, f"Aktif ({len(self.rules)})")
        operators = {value: title for title, value in OPERATORS}
        for rule in self.rules:
            detail = f"{rule.value} — {rule.value2}" if rule.operator == "between" else rule.value
            text = f"{rule.column}\n{operators.get(rule.operator, rule.operator)} {detail}"
            item = QListWidgetItem(text)
            item.setToolTip(
                text
                + "\nTür: "
                + KIND_LABELS.get(rule.kind, "Otomatik")
                + " · Sayı biçimi: "
                + rule.number_format
            )
            self.rule_list.addItem(item)

    def _show_frame(self, frame):
        self.model.replace(frame, self.kinds)
        self.stack.setCurrentIndex(1 if len(frame) else 2)
        self.stats["rows"].setText(f"{len(frame):,}")
        self.stats["columns"].setText(str(len(frame.columns)))
        self.stats["filters"].setText(str(len(self.rules)))
        if self.document:
            text = f"{len(frame):,} / {len(self.document.frame):,} satır · {len(frame.columns)} sütun"
            if self.dirty:
                text += " · Düzenlemeler bellekte; dışa aktararak kaydedin."
            self.statusBar().showMessage(text)
        self._controls()

    def _after_edit(self):
        self.dirty = True
        # Defer model reset until the editor's setData call has returned.
        QTimer.singleShot(0, self.apply_view)
        self._controls()

    def edit_cell(self, row, col, text):
        if self.busy or self.document is None:
            return False
        value = text if text != "" else None
        current = self.document.frame.at[row, col]
        if value is not None and isinstance(current, (pd.Timestamp, datetime, date)):
            value = parse_date(text)
            if value is None:
                self.show_error("Geçerli bir tarih girin. Örnek: 31.12.2026")
                return False
        elif value is not None and (isinstance(current, bool) or pd.api.types.is_bool_dtype(type(current))):
            normalized = str(text).strip().casefold().replace("ı", "i")
            if normalized not in ("evet", "hayir", "true", "false", "1", "0"):
                self.show_error("Evet / Hayır veya True / False girin.")
                return False
            value = normalized in ("evet", "true", "1")
        elif value is not None and isinstance(current, Integral) and re.fullmatch(r"[+-]?\d+", text.strip()):
            value = int(text)
        elif value is not None and pd.api.types.is_number(current):
            value = parse_number(text, number_format=self.number_formats.get(col, "auto"))
            if value is None:
                self.show_error("Geçerli bir sayı girin. Örnek: 1234,56 veya 1234.56")
                return False
        self.document.edit(row, col, value)
        self._after_edit()
        return True

    def add_row(self):
        if self.document is None or self.busy:
            return
        dialog = RowDialog(self.document.frame.columns, self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            try:
                for col, value in values.items():
                    if value is None:
                        continue
                    kind = self.kinds.get(col, "text")
                    if kind == "number":
                        parsed = (
                            int(value)
                            if re.fullmatch(r"[+-]?\d+", value.strip())
                            else parse_number(value, number_format=self.number_formats.get(col, "auto"))
                        )
                        if parsed is None:
                            raise ValueError(f"{col}: Geçerli bir sayı girin.")
                        values[col] = parsed
                    elif kind == "date":
                        parsed = parse_date(value)
                        if parsed is None:
                            raise ValueError(f"{col}: Geçerli bir tarih girin (31.12.2026).")
                        values[col] = parsed
                    elif kind == "boolean":
                        normalized = value.strip().casefold().replace("ı", "i")
                        if normalized not in ("evet", "hayir", "true", "false", "1", "0"):
                            raise ValueError(f"{col}: Evet / Hayır girin.")
                        values[col] = normalized in ("evet", "true", "1")
            except ValueError as exc:
                self.show_error(str(exc))
                continue
            self.document.add(values)
            self._after_edit()
            break

    def delete_rows(self):
        if self.document is None or self.busy:
            return
        rows = [self.model.frame.index[idx.row()] for idx in self.table.selectionModel().selectedRows()]
        if not rows:
            return
        reply = QMessageBox.question(
            self,
            "Satırları sil",
            f"Seçili {len(rows)} satır çalışma verisinden silinsin mi?\nGeri al düğmesiyle bu işlemi geri alabilirsiniz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.document.delete(rows)
            self._after_edit()

    def undo(self):
        if not self.busy and self.document and self.document.history:
            self.document.undo()
            self._after_edit()

    def redo(self):
        if not self.busy and self.document and self.document.future:
            self.document.redo()
            self._after_edit()

    def copy_selection(self):
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        if rows:
            frame = self.model.frame.iloc[rows]
            QApplication.clipboard().setText(frame.to_csv(sep="\t", index=False))
            self.statusBar().showMessage(f"{len(rows)} satır başlıklarıyla panoya kopyalandı.")

    def export_file(self):
        if self.document is None or self.busy:
            return
        if self._view_stale():
            self.apply_view(after=self.export_file)
            return
        dialog = ExportDialog(self.model.frame.columns, len(self.model.frame), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        extension = dialog.format.currentData()
        base = self.source_path.stem if self.source_path else "DataDesk"
        directory = self.settings.value("export_directory", str(Path.home() / "Desktop"))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "DataDesk · Çıktıyı kaydet",
            str(Path(directory) / f"{base}_filtreli{extension}"),
            f"{extension[1:].upper()} (*{extension})",
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != extension:
            path = path.with_suffix(extension)
            if (
                path.exists()
                and QMessageBox.question(
                    self,
                    "Dosya zaten var",
                    f"{path.name} değiştirilsin mi?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        if self._is_source(path):
            self.show_error("Kaynak dosyayı korumak için farklı bir ad veya konum seçin.")
            return
        self.export_to(path, dialog.options())

    def export_to(self, path, options=None):
        if self.document is None or self.busy:
            return
        path = Path(path)
        if self._is_source(path):
            self.show_error("Kaynak dosya üzerine yazılamaz. Farklı bir çıktı adı seçin.")
            return
        if self._view_stale():
            self.apply_view(after=lambda: self.export_to(path, options))
            return
        frame = self.model.frame.copy(deep=True)

        def done(saved):
            self.settings.setValue("export_directory", str(Path(saved).parent))
            self.notice.setText(f"Çıktı kaydedildi · {len(frame):,} satır\n{saved}")
            self.notice.show()
            if len(frame) == len(self.document.frame) and (
                options is None or options.columns is None or set(options.columns) == set(frame.columns)
            ):
                self.dirty = False
            self._show_frame(self.model.frame)
            self.statusBar().showMessage(f"Kaydedildi: {saved}")

        self._run_task("Tüm sonuçlar dışa aktarılıyor…", lambda: write_table(frame, path, options), done)

    def _is_source(self, path):
        if self.source_path is None:
            return False
        path = Path(path)
        if path.resolve() == self.source_path:
            return True
        try:
            return path.exists() and path.samefile(self.source_path)
        except OSError:
            return False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.busy:
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile() and not self.busy:
            self.open_path(urls[0].toLocalFile())
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy:
            self.statusBar().showMessage("İşlem sürüyor. Tamamlandığında pencereyi kapatabilirsiniz.")
            event.ignore()
            return
        if self._confirm_replace():
            self.search_timer.stop()
            event.accept()
        else:
            event.ignore()
