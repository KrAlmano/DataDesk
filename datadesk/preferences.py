"""Live appearance/language changes without replacing the working document."""

from PySide6.QtCore import QItemSelectionModel, QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog

from .i18n import render_text, set_language, tr
from .settings_ui import SettingsDialog
from .theme import THEMES, apply_theme, scaled_style
from .workspace_widgets import PATH_ROLE


class PreferencesActions:
    def _init_preferences(self):
        code = self.settings.value("ui_language", "tr")
        self.language_code = code if code in {"tr", "en"} else "tr"
        theme = self.settings.value("ui_theme", "light")
        self.theme_mode = theme if theme in THEMES else "light"
        set_language(self.language_code)
        app = QApplication.instance()
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        app.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self._apply_appearance()

    def _apply_appearance(self):
        app = QApplication.instance()
        apply_theme(app, self.theme_mode)
        style = scaled_style(self.zoom_percent, self.theme_mode)
        app.setStyleSheet(style)
        self.setStyleSheet(style)

    def _system_theme_changed(self, *_):
        if self.theme_mode == "system":
            self._apply_appearance()

    def show_settings(self):
        if self.busy or self.import_dialog is not None or not self._commit_cell_edit():
            return
        dialog = SettingsDialog(
            self,
            language=self.language_code,
            theme=self.theme_mode,
            zoom=self.zoom_percent,
            can_apply=lambda: not self.busy and self.import_dialog is None,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            preferences = dialog.preferences()
            # The accepted dialog must stop contributing shortcuts/focus before
            # widgets are rebuilt in the newly selected language.
            dialog.hide()
            self.apply_preferences(**preferences)
        dialog.deleteLater()

    def apply_preferences(self, *, language, theme, zoom=None):
        if self.busy or self.import_dialog is not None:
            return False
        if language not in {"tr", "en"} or theme not in THEMES:
            raise ValueError("Unsupported appearance or language preference")
        if not self._commit_cell_edit():
            return False
        changed_language = language != self.language_code
        self.theme_mode = theme
        self.language_code = language
        set_language(language)
        self.settings.setValue("ui_language", language)
        self.settings.setValue("ui_theme", theme)
        self._apply_appearance()
        if changed_language:
            self._rebuild_translated_ui()
        if zoom is not None:
            self.set_zoom(zoom)
        self.settings.sync()
        return True

    def _rebuild_translated_ui(self):
        """Recreate presentation only; retain raw data, undo, and view state."""
        page = self.page_tabs.currentIndex()
        directory = self.browser.current_directory
        history = list(self.browser._history)
        selected_file = self.browser.selected_path()
        browser_header = self.browser.file_list.header()
        browser_sort = (browser_header.sortIndicatorSection(), browser_header.sortIndicatorOrder())
        draft = {
            "column": self.column.currentText(),
            "kind": self.kind.currentData(),
            "operator": self.operator.currentData(),
            "number_format": self.number_format.currentData(),
            "value": self.value.text(),
            "value2": self.value2.text(),
            "search": self.search.text(),
        }
        tab = self.filter_tabs.currentIndex()
        rule_row = self.rule_list.currentRow()
        pending_search = self.search_timer.isActive()
        self.search_timer.stop()
        notice = self.notice.value()
        filter_error = getattr(self, "_filter_error_text", self.filter_error.text())
        selected_rows = [index.row() for index in self.table.selectionModel().selectedRows()]
        current = (self.table.currentIndex().row(), self.table.currentIndex().column())
        widths = [self.table.columnWidth(i) for i in range(self.model.columnCount())]
        scroll = (self.table.horizontalScrollBar().value(), self.table.verticalScrollBar().value())
        frame = self.model.frame
        self._layout_ready = False
        self._last_layout = None
        old_root = self.takeCentralWidget()
        old_root.hide()
        old_root.setEnabled(False)
        old_folder_model = self.folder_model
        # Menu actions belong to the main window, rather than the central widget.
        # Disable shortcuts immediately, then release the entire old menu tree.
        for action in self.findChildren(QAction, options=Qt.FindChildOption.FindDirectChildrenOnly):
            action.setEnabled(False)
            action.deleteLater()
        old_menus = [action.menu() for action in self.menuBar().actions() if action.menu() is not None]
        self.menuBar().clear()
        for menu in old_menus:
            menu.deleteLater()
        self.statusBar().removeWidget(self.zoom_controls)
        self.zoom_controls.hide()
        self.zoom_controls.deleteLater()
        self._build()
        self._menus()
        self._zoom_controls()
        self._recent()
        self.browser.navigate(directory)
        self.browser._history = history
        self.browser.file_list.sortByColumn(*browser_sort)
        for index in range(self.browser.file_list.topLevelItemCount()):
            item = self.browser.file_list.topLevelItem(index)
            if item.data(0, PATH_ROLE) == selected_file:
                self.browser.file_list.setCurrentItem(item)
                break
        if self.document is not None:
            with QSignalBlocker(self.column):
                self.column.addItems(list(self.document.frame.columns))
                self.column.setCurrentText(draft["column"])
            self._column_changed()
            for name in ("kind", "operator", "number_format"):
                control = getattr(self, name)
                with QSignalBlocker(control):
                    control.setCurrentIndex(max(0, control.findData(draft[name])))
            for name in ("value", "value2", "search"):
                with QSignalBlocker(getattr(self, name)):
                    getattr(self, name).setText(draft[name])
            with QSignalBlocker(self.match_combo):
                self.match_combo.setCurrentIndex(self.match_combo.findData(self.match))
            self._operator_changed()
            self.file_label.setText(render_text(self.source_name))
            self.file_label.setToolTip(render_text(self.source_name))
            self.title_label.setText(
                self.source_path.name if self.source_path else render_text(self.source_name)
            )
            self._document_opened()
            self._show_frame(frame)
            self._rule_labels()
            self.filter_tabs.setCurrentIndex(tab)
            self.rule_list.setCurrentRow(rule_row)
            if self.sort_column in frame.columns:
                self.table.horizontalHeader().setSortIndicator(
                    list(frame.columns).index(self.sort_column),
                    Qt.SortOrder.AscendingOrder if self.sort_ascending else Qt.SortOrder.DescendingOrder,
                )
                self.table.horizontalHeader().setSortIndicatorShown(True)
            for column, width in enumerate(widths):
                self.table.setColumnWidth(column, width)
            selection = self.table.selectionModel()
            if current[0] >= 0:
                selection.setCurrentIndex(
                    self.model.index(*current), QItemSelectionModel.SelectionFlag.NoUpdate
                )
            for row in selected_rows:
                selection.select(
                    self.model.index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
            self.filter_error.setText(render_text(filter_error))
            self.filter_error.setVisible(tab == 0 and bool(filter_error))
        self.notice.setText(notice)
        self.page_tabs.setCurrentIndex(page)
        self.pages.setCurrentIndex(page)
        self.notice.setVisible(page == 1 and bool(notice))
        self._layout_ready = True
        self._controls()
        self._relayout()
        self.table.verticalHeader().setDefaultSectionSize(self._px(30))
        self.table.horizontalScrollBar().setValue(scroll[0])
        self.table.verticalScrollBar().setValue(scroll[1])
        old_root.deleteLater()
        old_folder_model.deleteLater()
        if pending_search or self._view_stale():
            QTimer.singleShot(0, self._flush_pending_view)
        if page == 0:
            self.statusBar().showMessage(str(directory))

    def _preferences_menu(self, menu):
        self.settings_action = QAction(tr("Ayarlar…"), self)
        self.settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.triggered.connect(self.show_settings)
        menu.addSeparator()
        menu.addAction(self.settings_action)
