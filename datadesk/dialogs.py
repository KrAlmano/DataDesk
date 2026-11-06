"""Explicit import/export choices, with a preview before committing an import."""

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .io import ExportOptions, ImportOptions
from .models import TableModel


def combo(items):
    widget = QComboBox()
    for text, value in items:
        widget.addItem(text, value)
    return widget


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


class ImportDialog(QDialog):
    preview_requested = Signal(object)

    def __init__(self, path, info, loaded=None, error="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataDesk · Dosyayı içe aktar")
        self.resize(850, 610)
        self.setMinimumSize(620, 460)
        self.path = Path(path)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        title = QLabel(self.path.name)
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        subtitle = QLabel("Sayfayı ve başlığı kontrol edin. Veriler kaynak dosya değiştirilmeden açılır.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        form = QFormLayout()
        self.sheet = QComboBox()
        self.sheet.addItems(info.sheets or ["CSV / TSV"])
        self.sheet.setEnabled(bool(info.sheets))
        form.addRow("Excel sayfası", self.sheet)
        header_line = QHBoxLayout()
        self.header = QSpinBox()
        self.header.setRange(1, 10000)
        self.header.setValue(1)
        self.no_header = QCheckBox("Dosyada başlık yok")
        self.no_header.toggled.connect(lambda checked: self.header.setEnabled(not checked))
        header_line.addWidget(self.header)
        header_line.addWidget(self.no_header)
        form.addRow("Başlık satırı", header_line)
        self.encoding = combo(ENCODINGS)
        self.delimiter = combo(DELIMITERS)
        is_csv = self.path.suffix.lower() in (".csv", ".tsv")
        self.encoding.setEnabled(is_csv)
        self.delimiter.setEnabled(is_csv)
        form.addRow("CSV kodlaması", self.encoding)
        form.addRow("CSV ayırıcısı", self.delimiter)
        layout.addLayout(form)
        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("VERİ ÖNİZLEMESİ · İLK 6 SATIR"))
        preview_row.addStretch()
        self.preview_button = QPushButton("Önizlemeyi yenile")
        self.preview_button.clicked.connect(lambda: self.preview_requested.emit(self.options()))
        preview_row.addWidget(self.preview_button)
        layout.addLayout(preview_row)
        self.preview = QTableView()
        self.preview_model = TableModel(lambda *_: False, self)
        self.preview_model.editable = False
        self.preview.setModel(self.preview_model)
        self.preview.setAlternatingRowColors(True)
        layout.addWidget(self.preview, 1)
        self.message = QLabel()
        self.message.setObjectName("notice")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Open
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        self.buttons.button(QDialogButtonBox.StandardButton.Open).setText("Dosyayı aç")
        self.buttons.button(QDialogButtonBox.StandardButton.Open).setObjectName("primary")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
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


class ExportDialog(QDialog):
    def __init__(self, columns, count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataDesk · Sonuçları dışa aktar")
        self.resize(540, 630)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        title = QLabel(f"{count:,} satırı dışa aktar")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        note = QLabel(
            "Geçerli filtreler ve sıralama çıktıya uygulanır. Boş sonuçlarda da sütun başlıkları korunur."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        form = QFormLayout()
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
        self.safe_csv = QCheckBox("Formül gibi başlayan metinleri güvenli yaz")
        self.safe_csv.setChecked(True)
        self.safe_csv.setToolTip(
            "CSV/TSV metinlerinde =, +, -, @ ile başlayan değerlerin önüne ' eklenir. Sayısal hücreler değişmez. Birebir metin çıktısı için kapatın."
        )
        form.addRow("Dosya biçimi", self.format)
        form.addRow("CSV ayırıcısı", self.delimiter)
        form.addRow("Metin kodlaması", self.encoding)
        form.addRow(self.safe_csv)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(QLabel("ÇIKTIDAKİ SÜTUNLAR"))
        row.addStretch()
        select = QPushButton("Tümünü seç")
        select.clicked.connect(lambda: self.check_all(Qt.CheckState.Checked))
        clear = QPushButton("Seçimi kaldır")
        clear.clicked.connect(lambda: self.check_all(Qt.CheckState.Unchecked))
        row.addWidget(select)
        row.addWidget(clear)
        layout.addLayout(row)
        self.columns = QListWidget()
        self.columns.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for column in columns:
            item = QListWidgetItem(column)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.columns.addItem(item)
        layout.addWidget(self.columns, 1)
        hint = QLabel("Sütunları sürükleyerek çıktıdaki sırayı değiştirebilirsiniz.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel("")
        self.error.setObjectName("error")
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
        layout.addWidget(buttons)
        self.format.currentIndexChanged.connect(self.update_controls)
        self.update_controls()

    def update_controls(self):
        text = self.format.currentData() in (".csv", ".tsv")
        self.encoding.setEnabled(text)
        self.delimiter.setEnabled(self.format.currentData() == ".csv")
        self.safe_csv.setEnabled(text)

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


class RowDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataDesk · Satır ekle")
        self.resize(500, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Boş bırakılan hücreler boş olarak kaydedilir."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        self.entries = {}
        for col in columns:
            entry = QLineEdit()
            entry.setAccessibleName(col)
            form.addRow(col, entry)
            self.entries[col] = entry
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Satır ekle")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
