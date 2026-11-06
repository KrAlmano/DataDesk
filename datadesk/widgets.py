"""Small desktop widgets that retain useful space when content grows."""

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy

from .i18n import render_text


class ElidedLabel(QLabel):
    """Keep the complete filename accessible while its painted title can shrink."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideMiddle, self.contentsRect().width()
        )
        painter.drawText(self.contentsRect(), self.alignment(), text)


class ControlScrollArea(QScrollArea):
    """Reveal the whole focused control, including its border and label spacing."""

    def ensureWidgetVisible(self, widget, xmargin=12, ymargin=12):
        if not widget.isVisible() or not self.widget().isAncestorOf(widget):
            return
        center = widget.mapTo(self.widget(), QPoint(widget.width() // 2, widget.height() // 2))
        self.ensureVisible(
            center.x(), center.y(), widget.width() // 2 + xmargin, widget.height() // 2 + ymargin
        )

    def watch_focus(self, controls):
        for control in controls:
            control.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, self, lambda control=watched: self.ensureWidgetVisible(control))
        return super().eventFilter(watched, event)


class Notice(QScrollArea):
    """A readable, scrollable message that cannot push the table off screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setObjectName("notice")
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.setWidget(self.message)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.limit = 84
        self._value = ""

    def setText(self, text):
        self._value = text
        self.message.setText(render_text(text))
        self.message.setAccessibleName(render_text(text))
        self._fit_height()

    def value(self):
        return self._value

    def text(self):
        return self.message.text()

    def set_limit(self, height):
        self.limit = height
        self._fit_height()

    def _fit_height(self):
        width = max(80, self.viewport().width() - 16)
        wanted = max(self.message.fontMetrics().height() + 20, self.message.heightForWidth(width))
        self.setFixedHeight(min(self.limit, wanted))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()
