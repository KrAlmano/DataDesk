"""Explicit import/export choices, with a preview before committing an import."""

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .io import ExportOptions, ImportOptions
from .models import TableModel


def combo(items):
    widget = QComboBox()
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(12)
    widget.setMinimumWidth(0)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    for text, value in items:
        widget.addItem(text, value)
    widget.currentTextChanged.connect(widget.setToolTip)
    widget.setToolTip(widget.currentText())
    return widget


def wrapped_label(text, name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setMinimumWidth(1)
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    if name:
        widget.setObjectName(name)
    return widget


def form_layout():
    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(10)
    return form


class ScrollableDialog(QDialog):
    """Keep final actions visible while content remains reachable at large zoom."""

    def __init__(self, preferred_size, parent=None):
        super().__init__(parent)
        self._preferred_size = QSize(*preferred_size)
        self._initial_fit_done = False
        self._adaptive_rows = []
        self.setMinimumSize(360, 280)
        self.resize(self._preferred_size)
        self.shell = QVBoxLayout(self)
        self.shell.setContentsMargins(20, 18, 20, 18)
        self.shell.setSpacing(12)
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content_scroll.setMinimumSize(0, 0)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(2, 2, 8, 2)
        self.content_layout.setSpacing(12)
        self.content_scroll.setWidget(self.content)
        self.shell.addWidget(self.content_scroll, 1)

    def add_adaptive_row(self, row):
        self._adaptive_rows.append(row)

    def showEvent(self, event):
        if not self._initial_fit_done:
            self._initial_fit_done = True
            screen = self.screen().availableGeometry()
            parent = self.parentWidget()
            width = min(self._preferred_size.width(), screen.width() - 40)
            height = min(self._preferred_size.height(), screen.height() - 64)
            if parent is not None:
                width = min(width, max(360, parent.width() - 32))
                height = min(height, max(280, parent.height() - 48))
            self.resize(max(360, width), max(280, height))
        super().showEvent(event)
        self._reflow_rows()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_rows()

    def _reflow_rows(self):
        if not hasattr(self, "_adaptive_rows"):
            return
        horizontal = self.width() >= max(600, self.fontMetrics().height() * 36)
        if hasattr(self, "content"):
            # Windows' field metrics can exceed a form's tentative column width.
            # At large text sizes give each label/field its own full-width row.
            policy = (
                QFormLayout.RowWrapPolicy.DontWrapRows
                if horizontal
                else QFormLayout.RowWrapPolicy.WrapAllRows
            )
            for form in self.content.findChildren(QFormLayout):
                form.setRowWrapPolicy(policy)
        direction = QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom
        for row in self._adaptive_rows:
            row.setDirection(direction)
        if hasattr(self, "buttons"):
            visible_buttons = [button for button in self.buttons.buttons() if not button.isHidden()]
            needed = sum(
                max(button.sizeHint().width(), button.minimumSizeHint().width()) for button in visible_buttons
            )
            margins = self.shell.contentsMargins()
            available = self.width() - margins.left() - margins.right()
            orientation = Qt.Orientation.Horizontal if needed + 16 <= available else Qt.Orientation.Vertical
            if self.buttons.orientation() != orientation:
                self.buttons.setOrientation(orientation)

    def finish_with(self, buttons):
        self.buttons = buttons
        self.shell.addWidget(buttons)
        self._reflow_rows()


ENCODINGS = [
    ("Otomatik algıla", None),
    ("UTF-8", "utf-8-sig"),
    ("Türkçe Windows (1254)", "cp1254"),
    ("Windows (1252)", "cp1252"),
    ("UTF-16", "utf-16"),
]
DELIMITERS = [
    ("Otomatik algıla", None),
    ("Noktalı virgül ;", ";"),
    ("Virgül ,", ","),
    ("Sekme", "\t"),
    ("Dikey çizgi |", "|"),
]


class ImportDialog(ScrollableDialog):
    preview_requested = Signal(object)

    def __init__(self, path, info, loaded=None, error="", parent=None):
        super().__init__((850, 660), parent)
        self.setWindowTitle("DataDesk · Dosyayı içe aktar")
        self.path = Path(path)
        layout = self.content_layout
        title = wrapped_label(self.path.name, "sectionTitle")
        title.setToolTip(self.path.name)
        layout.addWidget(title)
        subtitle = wrapped_label(
            "Sayfayı ve başlığı kontrol edin. Veriler kaynak dosya değiştirilmeden açılır.", "muted"
        )
        layout.addWidget(subtitle)
        form = form_layout()
        self.sheet = combo([(name, name) for name in (info.sheets or ["CSV / TSV"])])
        self.sheet.setEnabled(bool(info.sheets))
        form.addRow("Excel sayfası", self.sheet)
        self.header = QSpinBox()
        self.header.setRange(1, 10000)
        self.header.setValue(1)
        self.no_header = QCheckBox("Başlık yok")
        self.no_header.setAccessibleName("Dosyada başlık yok")
        self.no_header.setToolTip("İlk satırı da veri olarak kullan; sütun başlıklarını DataDesk oluştursun.")
        self.no_header.toggled.connect(lambda checked: self.header.setEnabled(not checked))
        form.addRow("Başlık satırı", self.header)
        form.addRow(self.no_header)
        self.encoding = combo(ENCODINGS)
        self.delimiter = combo(DELIMITERS)
        is_csv = self.path.suffix.lower() in (".csv", ".tsv")
        self.encoding.setEnabled(is_csv)
        self.delimiter.setEnabled(is_csv)
        form.addRow("CSV kodlaması", self.encoding)
        form.addRow("CSV ayırıcısı", self.delimiter)
        form.setRowVisible(self.sheet, not is_csv)
        form.setRowVisible(self.encoding, is_csv)
        form.setRowVisible(self.delimiter, is_csv)
        layout.addLayout(form)
        preview_row = QHBoxLayout()
        preview_row.addWidget(wrapped_label("VERİ ÖNİZLEMESİ · İLK 6 SATIR"))
        preview_row.addStretch()
        self.preview_button = QPushButton("Önizlemeyi yenile")
        self.preview_button.clicked.connect(lambda: self.preview_requested.emit(self.options()))
        preview_row.addWidget(self.preview_button)
        self.add_adaptive_row(preview_row)
        layout.addLayout(preview_row)
        self.preview = QTableView()
        self.preview_model = TableModel(lambda *_: False, self)
        self.preview_model.editable = False
        self.preview.setModel(self.preview_model)
        self.preview.setAlternatingRowColors(True)
        self.preview.setMinimumHeight(150)
        self.preview.setWordWrap(False)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview, 1)
        self.message = wrapped_label("", "notice")
        layout.addWidget(self.message)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Open
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        self.buttons.button(QDialogButtonBox.StandardButton.Open).setText("Dosyayı aç")
        self.buttons.button(QDialogButtonBox.StandardButton.Open).setObjectName("primary")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.finish_with(self.buttons)
        for control in (self.sheet, self.encoding, self.delimiter):
            control.currentIndexChanged.connect(self.mark_stale)
        self.header.valueChanged.connect(self.mark_stale)
        self.no_header.toggled.connect(self.mark_stale)
        if loaded is not None:
            self.set_preview(loaded)
        else:
            self.message.setText(error or "Önizlemeyi yenileyerek dosyayı kontrol edin.")

    def mark_stale(self, *_):
        self.message.setText("Ayarlar değişti. Açmadan önce önizlemeyi yenileyebilirsiniz.")

    def options(self):
        sheet = self.sheet.currentText() if self.sheet.isEnabled() else 0
        return ImportOptions(
            sheet=sheet,
            header_row=None if self.no_header.isChecked() else self.header.value(),
            encoding=self.encoding.currentData(),
            delimiter=self.delimiter.currentData(),
        )

    def set_preview(self, loaded):
        self.preview_model.replace(loaded.frame.head(6), {c: "text" for c in loaded.frame.columns})
        for i in range(len(loaded.frame.columns)):
            self.preview.setColumnWidth(i, 145)
        details = f"{len(loaded.frame):,} satır · {len(loaded.frame.columns)} sütun"
        if loaded.encoding:
            details += f" · {loaded.encoding}"
        self.message.setText(details + ("\n" + "\n".join(loaded.warnings) if loaded.warnings else ""))

    def set_busy(self, busy):
        self.preview_button.setEnabled(not busy)
        self.buttons.setEnabled(not busy)
        is_csv = self.path.suffix.lower() in (".csv", ".tsv")
        self.sheet.setEnabled(not busy and not is_csv)
        self.header.setEnabled(not busy and not self.no_header.isChecked())
        self.no_header.setEnabled(not busy)
        self.encoding.setEnabled(not busy and is_csv)
        self.delimiter.setEnabled(not busy and is_csv)

    def reject(self):
        if self.preview_button.isEnabled():
            super().reject()


class ExportDialog(ScrollableDialog):
    def __init__(self, columns, count, parent=None):
        super().__init__((590, 690), parent)
        self.setWindowTitle("DataDesk · Sonuçları dışa aktar")
        layout = self.content_layout
        title = wrapped_label(f"{count:,} satırı dışa aktar", "sectionTitle")
        layout.addWidget(title)
        note = wrapped_label(
            "Geçerli filtreler ve sıralama çıktıya uygulanır. Boş sonuçlarda da sütun başlıkları korunur.",
            "muted",
        )
        layout.addWidget(note)
        form = form_layout()
        self.options_form = form
        self.format = combo(
            [
                ("Excel çalışma kitabı (.xlsx)", ".xlsx"),
                ("CSV (.csv)", ".csv"),
                ("Sekmeyle ayrılmış (.tsv)", ".tsv"),
                ("Word tablosu (.docx)", ".docx"),
            ]
        )
        self.delimiter = combo(DELIMITERS[1:])
        self.encoding = combo(ENCODINGS[1:])
        self.safe_csv = QCheckBox("CSV formül güvenliği")
        self.safe_csv.setAccessibleName("Formül gibi başlayan CSV metinlerini güvenli yaz")
        self.safe_csv.setChecked(True)
        self.safe_csv.setToolTip(
            "CSV/TSV metinlerinde =, +, -, @ ile başlayan değerlerin önüne ' eklenir. Sayısal hücreler değişmez. Birebir metin çıktısı için kapatın."
        )
        form.addRow("Dosya biçimi", self.format)
        form.addRow("CSV ayırıcısı", self.delimiter)
        form.addRow("Metin kodlaması", self.encoding)
        form.addRow(self.safe_csv)
        layout.addLayout(form)
        self.csv_safety_note = wrapped_label(
            "Güvenli CSV çıktısı, formül gibi başlayan metinlere tek tırnak ekler.", "muted"
        )
        layout.addWidget(self.csv_safety_note)
        row = QHBoxLayout()
        row.addWidget(wrapped_label("ÇIKTIDAKİ SÜTUNLAR"))
        row.addStretch()
        select = QPushButton("Tümünü seç")
        select.clicked.connect(lambda: self.check_all(Qt.CheckState.Checked))
        clear = QPushButton("Seçimi kaldır")
        clear.clicked.connect(lambda: self.check_all(Qt.CheckState.Unchecked))
        row.addWidget(select)
        row.addWidget(clear)
        self.add_adaptive_row(row)
        layout.addLayout(row)
        self.columns = QListWidget()
        self.columns.setMinimumHeight(150)
        self.columns.setWordWrap(True)
        self.columns.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for column in columns:
            item = QListWidgetItem(column)
            item.setToolTip(column)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.columns.addItem(item)
        layout.addWidget(self.columns, 1)
        hint = wrapped_label("Sütunları sürükleyerek çıktıdaki sırayı değiştirebilirsiniz.", "muted")
        layout.addWidget(hint)
        self.error = wrapped_label("", "error")
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Konum seç ve kaydet")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        self.finish_with(buttons)
        self.format.currentIndexChanged.connect(self.update_controls)
        self.update_controls()

    def update_controls(self):
        text = self.format.currentData() in (".csv", ".tsv")
        self.encoding.setEnabled(text)
        self.delimiter.setEnabled(self.format.currentData() == ".csv")
        self.safe_csv.setEnabled(text)
        self.options_form.setRowVisible(self.encoding, text)
        self.options_form.setRowVisible(self.delimiter, self.format.currentData() == ".csv")
        self.options_form.setRowVisible(self.safe_csv, text)
        self.csv_safety_note.setVisible(text)

    def check_all(self, state):
        for i in range(self.columns.count()):
            self.columns.item(i).setCheckState(state)

    def selected_columns(self):
        return [
            self.columns.item(i).text()
            for i in range(self.columns.count())
            if self.columns.item(i).checkState() == Qt.CheckState.Checked
        ]

    def validate(self):
        if not self.selected_columns():
            self.error.setText("En az bir sütun seçin.")
            self.error.show()
            return
        self.accept()

    def options(self):
        return ExportOptions(
            columns=self.selected_columns(),
            delimiter="\t" if self.format.currentData() == ".tsv" else self.delimiter.currentData(),
            encoding=self.encoding.currentData(),
            safe_csv=self.safe_csv.isChecked(),
        )


class RowDialog(ScrollableDialog):
    def __init__(self, columns, parent=None):
        super().__init__((560, 560), parent)
        self.setWindowTitle("DataDesk · Satır ekle")
        layout = self.content_layout
        layout.addWidget(wrapped_label("Boş bırakılan hücreler boş olarak kaydedilir.", "muted"))
        form = QVBoxLayout()
        form.setSpacing(14)
        self.entries = {}
        for col in columns:
            entry = QLineEdit()
            entry.setAccessibleName(col)
            title = wrapped_label(str(col))
            title.setToolTip(str(col))
            title.setBuddy(entry)
            field = QWidget()
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(6)
            field_layout.addWidget(title)
            field_layout.addWidget(entry)
            form.addWidget(field)
            self.entries[col] = entry
        layout.addLayout(form)
        layout.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Satır ekle")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.finish_with(buttons)

    def values(self):
        return {c: entry.text() if entry.text() else None for c, entry in self.entries.items()}


def demo_frame():
    """Deterministic sample, kept independent of the user's actual files."""
    cities = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Eskişehir"]
    teams = ["Satış", "Operasyon", "Finans", "Pazarlama"]
    names = [
        "Deniz Yılmaz",
        "Ece Kaya",
        "Mert Demir",
        "Selin Arslan",
        "Can Aydın",
        "Elif Çelik",
        "Bora Şahin",
        "Ada Koç",
    ]
    return pd.DataFrame(
        [
            {
                "Sipariş No": f"DD-{i + 1:05d}",
                "Müşteri": names[i % 8],
                "Şehir": cities[i % 6],
                "Departman": teams[i % 4],
                "Tarih": pd.Timestamp("2026-10-01") + pd.Timedelta(days=i % 30),
                "Tutar": round(750 + ((i * 1741) % 24000) + (i % 4) * 0.25, 2),
                "Durum": ["Tamamlandı", "Bekliyor", "Tamamlandı", "İşlemde"][i % 4],
                "Müşteri Kodu": f"{i + 1:06d}",
            }
            for i in range(120)
        ]
    )
