"""Appearance and language preferences, committed by the caller after Apply."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialogButtonBox

from . import translations_settings as _translations_settings  # noqa: F401
from .dialogs import ScrollableDialog, combo, form_layout, wrapped_label
from .i18n import tr


class SettingsDialog(ScrollableDialog):
    def __init__(self, parent=None, language="tr", theme="light", zoom=100, can_apply=None):
        super().__init__((580, 440), parent)
        self._can_apply = can_apply
        self.setWindowTitle(tr("DataDesk · Ayarlar"))
        self.content.setAutoFillBackground(False)
        self.content_scroll.viewport().setAutoFillBackground(False)
        self.content_layout.addWidget(wrapped_label(tr("Görünüm ve dil"), "sectionTitle"))

        self.language_combo = combo([("Türkçe", "tr"), ("English", "en")])
        self.language_combo.setObjectName("settingsLanguage")
        self.language_combo.setAccessibleName(tr("Arayüz dili"))
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language)))

        self.theme_combo = combo([(tr("Açık"), "light"), (tr("Koyu"), "dark"), (tr("Sistem"), "system")])
        self.theme_combo.setObjectName("settingsTheme")
        self.theme_combo.setAccessibleName(tr("Tema"))
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(theme)))

        try:
            zoom = max(75, min(150, int(zoom)))
        except (TypeError, ValueError):
            zoom = 100
        sizes = sorted({75, 100, 125, 150, zoom})
        self.zoom_combo = combo([(f"{value}%", value) for value in sizes])
        self.zoom_combo.setObjectName("settingsZoom")
        self.zoom_combo.setAccessibleName(tr("Arayüz boyutu"))
        self.zoom_combo.setCurrentIndex(self.zoom_combo.findData(zoom))

        form = form_layout()
        form.addRow(tr("Arayüz dili"), self.language_combo)
        form.addRow(tr("Tema"), self.theme_combo)
        form.addRow(tr("Arayüz boyutu"), self.zoom_combo)
        self.content_layout.addLayout(form)
        self.content_layout.addWidget(
            wrapped_label(
                tr("Dil seçimi yalnızca arayüzü değiştirir. Dosyalarınız ve hücre içerikleri değişmez."),
                "muted",
            )
        )
        self.content_layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setText(tr("Uygula"))
        apply_button.setObjectName("primary")
        apply_button.setDefault(True)
        apply_button.clicked.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Vazgeç"))
        buttons.rejected.connect(self.reject)
        self.finish_with(buttons)
        self._apply_guard_timer = QTimer(self)
        self._apply_guard_timer.setInterval(50)
        self._apply_guard_timer.timeout.connect(self._refresh_apply_state)
        self.finished.connect(self._apply_guard_timer.stop)
        self._refresh_apply_state()

    def _refresh_apply_state(self):
        allowed = self._can_apply is None or self._can_apply()
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(allowed)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_apply_state()
        if self._can_apply is not None:
            self._apply_guard_timer.start()

    def accept(self):
        # Recheck at click/Enter time as a task may have started since the last
        # timer tick. Keep the dialog and its draft choices open until it ends.
        if self._can_apply is not None and not self._can_apply():
            self._refresh_apply_state()
            return
        super().accept()

    def preferences(self):
        """Return candidate preferences without changing global application state."""
        return {
            "language": self.language_combo.currentData(),
            "theme": self.theme_combo.currentData(),
            "zoom": self.zoom_combo.currentData(),
        }
