"""Real local files and folders, integrated with the table editor."""

from pathlib import Path
import os
import tempfile

import pandas as pd
from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
)

from .dialogs import ScrollableDialog, form_layout, wrapped_label
from .i18n import render_text, tr
from . import translations_workspace as _translations_workspace  # noqa: F401
from .io import ExportOptions, write_table
from .workspace import Workspace


class NewTableDialog(ScrollableDialog):
    def __init__(self, parent=None):
        super().__init__((560, 510), parent)
        self.setWindowTitle(tr("Yeni dosya"))
        self.content_layout.addWidget(wrapped_label(tr("Yeni tablo"), "folderTitle"))
        form = form_layout()
        self.name = QLineEdit(tr("Yeni tablo"))
        self.name.setAccessibleName(tr("Dosya adı"))
        self.name.selectAll()
        form.addRow(tr("Dosya adı"), self.name)
        self.format = QComboBox()
        for title, suffix in [("Excel (.xlsx)", "xlsx"), ("CSV (.csv)", "csv"), ("TSV (.tsv)", "tsv")]:
            self.format.addItem(title, suffix)
        self.format.setAccessibleName(tr("Yeni dosya biçimi"))
        form.addRow(tr("Biçim"), self.format)
        self.content_layout.addLayout(form)
        self.content_layout.addWidget(QLabel(tr("Sütunlar")))
        self.content_layout.addWidget(wrapped_label(tr("Her satıra bir sütun adı yazın."), "muted"))
        self.columns = QPlainTextEdit(tr("Ad\nTarih\nTutar"))
        self.columns.setAccessibleName(tr("Sütun adları, her satırda bir ad"))
        self.columns.setMinimumHeight(110)
        self.content_layout.addWidget(self.columns, 1)
        self.error = wrapped_label("", "error")
        self.error.hide()
        self.content_layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Oluştur"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Vazgeç"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.finish_with(buttons)
        self.content_scroll.watch_focus((self.name, self.format, self.columns))

    def values(self):
        return self.name.text().strip(), self.format.currentData(), self.columns.toPlainText().splitlines()

    def accept(self):
        name, _, headings = self.values()
        headings = [heading.strip() for heading in headings]
        if (
            not name
            or not headings
            or any(not heading for heading in headings)
            or len(set(headings)) != len(headings)
        ):
            self.error.setText(tr("Dosya adı ve birbirinden farklı, boş olmayan sütun adları girin."))
            self.error.show()
            return
        super().accept()


def _identity(path):
    try:
        stat = Path(path).stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
    except OSError:
        return None


class WorkspaceActions:
    """UI coordination; the Workspace backend owns all filesystem mutations."""

    def _init_workspace(self, root=None):
        saved_root = self.settings.value("workspace_root", "")
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        default = Path(documents or Path.home()) / "DataDesk"
        self._workspace_startup_warning = ""
        try:
            self.workspace = Workspace(root or saved_root or default, create=bool(root) or not saved_root)
        except (ValueError, OSError) as error:
            # If a removed external disk was selected, retain that preference
            # until the user explicitly chooses another working folder.
            self.workspace = Workspace(default)
            self._workspace_startup_warning = tr(
                "Çalışma klasörü açılamadı: {error}\nGeçici olarak {directory} gösteriliyor.",
                error=error,
                directory=default,
            )
        if not self._workspace_startup_warning:
            self.settings.setValue("workspace_root", str(self.workspace.root))
        self._session_saved = {}

    def _connect_browser(self):
        self.browser.open_requested.connect(self.open_path)
        self.browser.new_folder_requested.connect(self.new_workspace_folder)
        self.browser.new_file_requested.connect(self.new_workspace_file)
        self.browser.import_requested.connect(self.import_workspace_files)
        self.browser.import_files_requested.connect(self._copy_workspace_files)
        self.browser.rename_requested.connect(self.rename_workspace_item)
        self.browser.move_requested.connect(self.move_workspace_item)
        self.browser.root_requested.connect(self.choose_workspace_root)
        self.browser.directory_changed.connect(self._directory_changed)

    def _page_changed(self, index):
        if hasattr(self, "pages"):
            self.pages.setCurrentIndex(index)
            self.notice.setVisible(index == 1 and bool(self.notice.text()))
            self._relayout()

    def show_files(self):
        self.browser.refresh()
        self.page_tabs.setCurrentIndex(0)
        self.pages.setCurrentIndex(0)
        self.statusBar().showMessage(str(self.browser.current_directory))

    def show_document(self):
        if self.document is not None:
            self.page_tabs.setCurrentIndex(1)
            self.pages.setCurrentIndex(1)

    def _document_opened(self):
        if self.page_tabs.count() == 1:
            self.page_tabs.addTab(
                self.source_path.name if self.source_path else render_text(self.source_name)
            )
        self._update_document_title()
        self.show_document()

    def _update_document_title(self):
        if self.document is None:
            return
        name = self.source_path.name if self.source_path else render_text(self.source_name)
        dirty = " *" if self.dirty else ""
        if hasattr(self, "page_tabs") and self.page_tabs.count() > 1:
            self.page_tabs.setTabText(1, name + dirty)
            self.page_tabs.setTabToolTip(1, str(self.source_path or name))
        self.setWindowTitle(f"{name}{dirty} · DataDesk")
        if hasattr(self, "save_button"):
            self.save_button.setToolTip(
                tr("Tüm satırları çalışma dosyasına kaydet")
                if self._can_save_source()
                else tr("Tüm satırları yeni bir çalışma dosyasına kaydet")
            )

    def _folder_clicked(self, index):
        self.browser.navigate(Path(self.folder_model.filePath(index)))
        self.show_files()

    def _directory_changed(self, path):
        self.folder_tree.setCurrentIndex(self.folder_model.index(str(path)))
        self.settings.setValue("workspace_directory", str(path))

    def _workspace_menu(self):
        menu = QMenu(self)
        menu.addAction(tr("Yeni klasör…"), self.new_workspace_folder)
        menu.addAction(tr("Yeni dosya…"), self.new_workspace_file)
        menu.addSeparator()
        menu.addAction(tr("Çalışma klasörünü değiştir…"), self.choose_workspace_root)
        menu.addAction(
            tr("Çalışma klasörünü sistemde göster"),
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.workspace.root))),
        )
        menu.exec(self.workspace_menu_button.mapToGlobal(self.workspace_menu_button.rect().bottomLeft()))

    def choose_workspace_root(self):
        if self.busy:
            return
        directory = QFileDialog.getExistingDirectory(
            self, tr("Çalışma klasörünü seç"), str(self.workspace.root)
        )
        if directory:
            self.set_workspace_root(directory)

    def set_workspace_root(self, directory):
        try:
            workspace = Workspace(directory)
        except (ValueError, OSError) as error:
            self.show_error(str(error))
            return False
        self.workspace = workspace
        self.settings.setValue("workspace_root", str(workspace.root))
        self.folder_model.setRootPath(str(workspace.root))
        self.folder_tree.setRootIndex(self.folder_model.index(str(workspace.root)))
        self.browser.set_root(workspace.root)
        self.show_files()
        self._update_document_title()
        return True

    def _workspace_parent(self, parent):
        return self.browser.current_directory if parent is None or isinstance(parent, bool) else Path(parent)

    def new_workspace_folder(self, parent=None):
        if self.busy:
            return
        parent = self._workspace_parent(parent)
        name, accepted = QInputDialog.getText(self, tr("Yeni klasör"), tr("Klasör adı"))
        if not accepted:
            return
        try:
            path = self.workspace.create_folder(parent, name)
        except (ValueError, OSError) as error:
            self.show_error(str(error))
            return
        self.browser.navigate(path)
        self.show_files()
        self.statusBar().showMessage(tr("Klasör oluşturuldu: {name}", name=path.name))

    def new_workspace_file(self, parent=None):
        if self.busy:
            return
        parent = self._workspace_parent(parent)
        dialog = NewTableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and self._confirm_replace():
            name, suffix, headings = dialog.values()
            self.create_workspace_file(parent, name, headings, suffix)

    def create_workspace_file(self, parent, name, columns, suffix="xlsx"):
        if self.busy:
            return None
        try:
            path = self.workspace.create_table(parent, name, columns, file_format=suffix)
        except (ValueError, OSError) as error:
            self.show_error(str(error))
            return None
        self.browser.refresh()
        if self.workspace.metadata_warning:
            self.statusBar().showMessage(self.workspace.metadata_warning)
        self.load_path(path)
        return path

    def import_workspace_files(self, parent=None):
        if self.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Çalışma klasörüne dosya kopyala"),
            self.settings.value("last_directory", str(Path.home())),
            "Excel / CSV / TSV (*.xlsx *.xlsm *.xls *.csv *.tsv)",
        )
        if paths:
            self._copy_workspace_files(paths, self._workspace_parent(parent))

    def _copy_workspace_files(self, paths, parent):
        if self.busy:
            return

        def done(copied):
            self.browser.navigate(Path(parent))
            self.browser.refresh()
            self.statusBar().showMessage(tr("{count} dosya çalışma klasörüne kopyalandı.", count=len(copied)))

        self._run_task(tr("Dosyalar kopyalanıyor…"), lambda: self.workspace.import_files(paths, parent), done)

    def rename_workspace_item(self, path):
        if self.busy:
            return
        path = Path(path)
        name, accepted = QInputDialog.getText(self, tr("Yeniden adlandır"), tr("Yeni ad"), text=path.name)
        if not accepted:
            return
        try:
            target = self.workspace.rename(path, name)
        except (ValueError, OSError) as error:
            self.show_error(str(error))
            return
        self._item_moved(path, target)

    def move_workspace_item(self, path):
        if self.busy:
            return
        path = Path(path)
        destination = QFileDialog.getExistingDirectory(
            self, tr("Taşınacak klasörü seç"), str(self.workspace.root)
        )
        if not destination:
            return
        try:
            target = self.workspace.move(path, destination)
        except (ValueError, OSError) as error:
            self.show_error(str(error))
            return
        self._item_moved(path, target)

    def _item_moved(self, old, new):
        if self.source_path is not None and self.source_path.is_relative_to(old):
            self.source_path = new / self.source_path.relative_to(old) if old != self.source_path else new
            self.source_name = self.source_path.name
            self.title_label.setText(self.source_path.name)
            self.file_label.setText(self.source_name)
            self._update_document_title()
        recents = []
        for value in self.settings.value("recent_files", [], type=list):
            path = Path(value)
            if path.is_relative_to(old):
                path = new / path.relative_to(old) if path != old else new
            recents.append(str(path))
        self.settings.setValue("recent_files", recents)
        self._recent()
        self.browser.navigate(new.parent)
        self.browser.refresh()
        self.statusBar().showMessage(
            self.workspace.metadata_warning or tr("Dosya konumu güncellendi: {name}", name=new.name)
        )

    def _can_save_source(self):
        path = self.source_path
        return path is not None and (
            self.workspace.is_managed(path)
            or (str(path) in self._session_saved and _identity(path) == self._session_saved[str(path)])
        )

    def save_document(self):
        if self.document is None or self.busy:
            return
        if self._can_save_source():
            self.save_document_to(self.source_path)
        else:
            self.save_document_as()

    def save_document_as(self):
        if self.document is None or self.busy:
            return
        base = self.source_path.stem if self.source_path else tr("Yeni tablo")
        path, selected = QFileDialog.getSaveFileName(
            self,
            tr("Tabloyu farklı kaydet · Tüm satırlar"),
            str(self.browser.current_directory / tr("{base}_calisma.xlsx", base=base)),
            "Excel (*.xlsx);;CSV (*.csv);;TSV (*.tsv)",
        )
        if not path:
            return
        path = Path(path)
        if not path.suffix:
            suffix = ".csv" if "*.csv" in selected else ".tsv" if "*.tsv" in selected else ".xlsx"
            path = path.with_suffix(suffix)
            if (
                path.exists()
                and QMessageBox.question(
                    self,
                    tr("Dosya zaten var"),
                    tr("{name} değiştirilsin mi?", name=path.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        self.save_document_to(path)

    def save_document_to(self, path):
        """Save every source row, independently of search, filters and ordering."""
        if self.document is None or self.busy or not self._commit_cell_edit():
            return False
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() not in {".xlsx", ".csv", ".tsv"}:
            self.show_error(tr("Çalışma tablosunu XLSX, CSV veya TSV olarak kaydedin."))
            return False
        same = self._is_source(path)
        if same and not self._can_save_source():
            self.show_error(tr("Bu kaynak dosyayı korumak için Farklı kaydet ile yeni bir dosya oluşturun."))
            return False
        frame = self.document.frame.copy(deep=True)
        identity = _identity(path)

        def save():
            handle, temporary_name = tempfile.mkstemp(
                prefix=".datadesk-save-", suffix=path.suffix, dir=path.parent
            )
            os.close(handle)
            temporary = Path(temporary_name)
            try:
                write_table(frame, temporary, ExportOptions(sheet_name=tr("Veriler"), safe_csv=False))
                if _identity(path) != identity:
                    raise ValueError(
                        tr("Dosya başka bir uygulamada değişti. Farklı bir dosya adıyla kaydedin.")
                    )
                os.replace(temporary, path)
                return path
            finally:
                temporary.unlink(missing_ok=True)

        def done(saved):
            self.source_path = Path(saved).resolve()
            self.source_name = self.source_path.name
            if self.source_path.is_relative_to(self.workspace.root):
                self.workspace.register_table(self.source_path)
            self._session_saved[str(self.source_path)] = _identity(self.source_path)
            self.dirty = False
            self.file_label.setText(self.source_name)
            self.title_label.setText(self.source_name)
            self._update_document_title()
            self.browser.refresh()
            self.statusBar().showMessage(
                self.workspace.metadata_warning
                or tr("Kaydedildi: {name} · {count} satır", name=self.source_path.name, count=len(frame))
            )

        return self._run_task(tr("Tablo kaydediliyor…"), save, done)

    def open_in_spreadsheet(self):
        if self.busy or self.source_path is None:
            return
        if self.dirty:
            self.show_error(
                tr("Düzenlemeleri önce Kaydet ile kaydedin. Ardından dosyayı Excel'de açabilirsiniz.")
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.source_path))):
            self.show_error(tr("Dosya açılamadı. Bilgisayarınızda bu biçimi açan bir uygulama bulunamadı."))

    def add_column(self):
        if self.document is None or self.busy:
            return
        name, accepted = QInputDialog.getText(self, tr("Sütun ekle"), tr("Sütun adı"))
        if not accepted:
            return
        name = name.strip()
        if not name or name in self.document.frame.columns:
            self.show_error(tr("Boş olmayan ve tabloda bulunmayan bir sütun adı girin."))
            return
        self.document.checkpoint()
        self.document.frame[name] = pd.Series(None, index=self.document.frame.index, dtype=object)
        self._after_edit()

    def _sync_columns(self):
        columns = list(self.document.frame.columns)
        if columns == [self.column.itemText(index) for index in range(self.column.count())]:
            return
        current = self.column.currentText()
        self.rules = [rule for rule in self.rules if rule.column in columns]
        if self.sort_column not in columns:
            self.sort_column = None
        self.column.blockSignals(True)
        self.column.clear()
        self.column.addItems(columns)
        if current in columns:
            self.column.setCurrentText(current)
        self.column.blockSignals(False)
