"""Shared light/dark palettes and scalable desktop styling.

Application palettes cover native-painted controls and table editors; the same
semantic colors also drive QSS so dialogs, menus, and widget surfaces agree.
"""

import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory

_shared_font_family = None
_ASSETS = Path(__file__).parent / "assets"
THEMES = ("light", "dark", "system")


class DesktopStyle(QProxyStyle):
    """Keep Qt file-dialog navigation visible in either application palette."""

    def standardIcon(self, standard_icon, option=None, widget=None):
        directions = {
            QStyle.StandardPixmap.SP_ArrowBack: ((10, 3), (5, 8), (10, 13)),
            QStyle.StandardPixmap.SP_ArrowLeft: ((10, 3), (5, 8), (10, 13)),
            QStyle.StandardPixmap.SP_ArrowForward: ((6, 3), (11, 8), (6, 13)),
            QStyle.StandardPixmap.SP_ArrowRight: ((6, 3), (11, 8), (6, 13)),
            QStyle.StandardPixmap.SP_ArrowUp: ((3, 10), (8, 5), (13, 10)),
            QStyle.StandardPixmap.SP_ArrowDown: ((3, 6), (8, 11), (13, 6)),
        }
        if standard_icon not in directions:
            return super().standardIcon(standard_icon, option, widget)
        palette = QGuiApplication.palette()
        icon = QIcon()
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected, QIcon.Mode.Disabled):
            group = (
                QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled else QPalette.ColorGroup.Active
            )
            color = palette.color(group, QPalette.ColorRole.WindowText)
            pixmap = QPixmap(32, 32)
            pixmap.setDevicePixelRatio(2)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(
                QPen(color, 1.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            )
            points = [QPointF(*point) for point in directions[standard_icon]]
            painter.drawLine(points[0], points[1])
            painter.drawLine(points[1], points[2])
            painter.end()
            icon.addPixmap(pixmap, mode)
        return icon


PALETTES = {
    "light": {
        "window": "#f5f6f8",
        "surface": "#ffffff",
        "chrome": "#f7f8fa",
        "sidebar": "#f3f4f6",
        "alternate": "#fafbfc",
        "text": "#262b33",
        "muted": "#626a76",
        "border": "#dfe2e7",
        "control_border": "#b8c0cc",
        "grid": "#e9edf1",
        "separator": "#e7eaf0",
        "hover": "#eef1f5",
        "hover_border": "#8b99ac",
        "pressed": "#e5eaf0",
        "accent": "#3568a8",
        "primary": "#3568a8",
        "on_primary": "#ffffff",
        "primary_hover": "#2c5b97",
        "primary_pressed": "#244d82",
        "primary_focus": "#1e426f",
        "selection": "#e4edf8",
        "selection_text": "#234f85",
        "selected_border": "#7d9fc9",
        "disabled_bg": "#f0f2f5",
        "disabled_text": "#626c79",
        "disabled_border": "#dfe2e7",
        "notice_bg": "#faf4e7",
        "notice_text": "#76571d",
        "notice_border": "#d7c496",
        "error_bg": "#fbefee",
        "error_text": "#a13d35",
        "error_border": "#ddaaa5",
        "scroll_handle": "#b4becb",
        "scroll_hover": "#8b99ac",
        "progress_track": "#e8edf4",
        "shadow": "#697484",
    },
    "dark": {
        "window": "#1e232b",
        "surface": "#20262f",
        "chrome": "#282f3a",
        "sidebar": "#1b2028",
        "alternate": "#252c36",
        "text": "#e6eaf1",
        "muted": "#afb9c8",
        "border": "#3a4453",
        "control_border": "#596779",
        "grid": "#343d4b",
        "separator": "#3a4453",
        "hover": "#303a48",
        "hover_border": "#7f93ad",
        "pressed": "#3b4859",
        "accent": "#9fc6ff",
        "primary": "#3568a8",
        "on_primary": "#ffffff",
        "primary_hover": "#305f9c",
        "primary_pressed": "#284f82",
        "primary_focus": "#c8deff",
        "selection": "#354e70",
        "selection_text": "#edf4ff",
        "selected_border": "#9fc6ff",
        "disabled_bg": "#292f39",
        "disabled_text": "#9aa6b7",
        "disabled_border": "#3a4453",
        "notice_bg": "#3a3325",
        "notice_text": "#f2d899",
        "notice_border": "#7e6b42",
        "error_bg": "#422b30",
        "error_text": "#ffb8b0",
        "error_border": "#945c61",
        "scroll_handle": "#66758a",
        "scroll_hover": "#92a3ba",
        "progress_track": "#394351",
        "shadow": "#11151b",
    },
}


def resolve_theme(theme="light", app=None):
    """Resolve a stored preference without changing the OS appearance setting."""
    if theme in ("light", "dark"):
        return theme
    if theme == "system":
        app = app if app is not None else QGuiApplication.instance()
        if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            return "dark"
    return "light"


def palette_for(theme="light", app=None):
    colors = PALETTES[resolve_theme(theme, app)]
    palette = QPalette()
    for role, key in [
        (QPalette.ColorRole.Window, "window"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "surface"),
        (QPalette.ColorRole.AlternateBase, "alternate"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "surface"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.Highlight, "selection"),
        (QPalette.ColorRole.HighlightedText, "selection_text"),
        (QPalette.ColorRole.ToolTipBase, "surface"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.Link, "accent"),
        (QPalette.ColorRole.LinkVisited, "accent"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
        (QPalette.ColorRole.BrightText, "on_primary"),
        (QPalette.ColorRole.Light, "control_border"),
        (QPalette.ColorRole.Midlight, "hover_border"),
        (QPalette.ColorRole.Dark, "border"),
        (QPalette.ColorRole.Mid, "separator"),
        (QPalette.ColorRole.Shadow, "shadow"),
        (QPalette.ColorRole.Accent, "accent"),
    ]:
        palette.setColor(role, QColor(colors[key]))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.PlaceholderText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_text"]))
    for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Button):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_bg"]))
    return palette


def apply_theme(app, theme="light"):
    """Apply native-control colors; callers apply scaled_style to their window."""
    resolved = resolve_theme(theme, app)
    app.setPalette(palette_for(resolved))
    app.setProperty("datadeskTheme", resolved)
    app.setProperty("datadeskThemePreference", theme if theme in THEMES else "light")
    return resolved


def configure_app(app, theme="light"):
    global _shared_font_family
    app._datadesk_style = DesktopStyle(QStyleFactory.create("Fusion"))
    app.setStyle(app._datadesk_style)
    # One bundled font keeps layout and typography consistent across platforms.
    font_file = _ASSETS / "fonts" / "Inter.ttf"
    if _shared_font_family is None and font_file.is_file():
        # Reading bytes also supports Windows install paths containing Turkish.
        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(font_file.read_bytes()))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _shared_font_family = families[0]
    app.setFont(QFont(_shared_font_family or app.font().family(), 12))
    return apply_theme(app, theme)


def scaled_style(percent=100, theme="light"):
    """Qt handles device DPI; this separately implements the user's UI zoom."""
    resolved = resolve_theme(theme)
    css = _STYLE_TEMPLATE
    for key, value in PALETTES[resolved].items():
        css = css.replace("@" + key.upper() + "@", value)
    chevron = "chevron-dark.svg" if resolved == "dark" else "chevron.svg"
    css = css.replace("@CHEVRON@", (_ASSETS / chevron).as_posix())
    for token, filename in {
        "CHEVRON_UP": f"chevron-up{'-dark' if resolved == 'dark' else ''}.svg",
        "CHECKMARK": "checkmark.svg",
        "CHECKMARK_DISABLED": f"checkmark-disabled-{resolved}.svg",
    }.items():
        css = css.replace(f"@{token}@", (_ASSETS / filename).as_posix())
    factor = percent / 100
    return re.sub(r"(-?\d+(?:\.\d+)?)px", lambda match: f"{round(float(match[1]) * factor)}px", css)


_STYLE_TEMPLATE = """
QWidget { color: @TEXT@; font-size: 13px; }
QWidget:disabled { color: @DISABLED_TEXT@; }
QMainWindow { background: @SURFACE@; }
QDialog { background: @CHROME@; }
QFrame#sidebar, QWidget#workspaceSidebar {
    background: @SIDEBAR@;
    border: none;
    border-right: 1px solid @BORDER@;
}
QFrame#sidebar QLabel, QWidget#workspaceSidebar QLabel { color: @MUTED@; }
QFrame#sidebar QLabel#brand, QWidget#workspaceSidebar QLabel#workspaceHeading, QLabel#workspaceHeading {
    color: @TEXT@; font-size: 17px; font-weight: 600;
}
QFrame#sidebar QLabel#brandMark {
    background: transparent; color: @ACCENT@; font-size: 18px; font-weight: 600;
}
QFrame#sidebar QPushButton {
    color: @TEXT@; background: @SURFACE@; border: 1px solid @CONTROL_BORDER@;
    text-align: left; padding: 7px 10px;
}
QFrame#sidebar QPushButton:hover { background: @HOVER@; border-color: @HOVER_BORDER@; }
QFrame#sidebar QListWidget {
    background: transparent; color: @MUTED@; border: none; outline: none;
}
QFrame#sidebar QListWidget::item { padding: 7px 5px; border: none; border-radius: 3px; }
QFrame#sidebar QListWidget::item:selected { background: @SELECTION@; color: @SELECTION_TEXT@; }
QLabel#title, QLabel#folderTitle { font-size: 19px; font-weight: 600; color: @TEXT@; }
QLabel#sectionTitle, QLabel#emptyTitle { font-size: 14px; font-weight: 600; color: @TEXT@; }
QLabel#eyebrow, QLabel#sidebarCaption, QLabel#sectionCaption {
    color: @MUTED@; font-size: 11px; font-weight: 600;
}
QLabel#muted, QLabel#emptyHint { color: @MUTED@; }
QLabel#breadcrumb { color: @MUTED@; font-size: 12px; }
QLabel#badge { color: @MUTED@; padding: 3px 0; font-size: 11px; }
QLabel#statValue { font-size: 18px; font-weight: 600; color: @TEXT@; }
QFrame#card, QFrame#filterPanel {
    background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 4px;
}
QFrame#filterBody { background: @SURFACE@; border: none; }
QWidget#workspaceToolbar, QWidget#documentToolbar { background: @SURFACE@; }
QLabel#notice {
    background: @NOTICE_BG@; color: @NOTICE_TEXT@; padding: 8px 10px;
    border: 1px solid @NOTICE_BORDER@; border-radius: 4px; font-size: 12px;
}
QLabel#error {
    background: @ERROR_BG@; color: @ERROR_TEXT@; padding: 8px 10px;
    border: 1px solid @ERROR_BORDER@; border-radius: 4px;
}
QPushButton {
    background: @SURFACE@; border: 1px solid @CONTROL_BORDER@; border-radius: 4px;
    padding: 6px 10px; font-weight: 500;
}
QPushButton:hover { background: @HOVER@; border-color: @HOVER_BORDER@; }
QPushButton:pressed { background: @PRESSED@; }
QPushButton:focus { border: 1px solid @ACCENT@; }
QPushButton#primary { background: @PRIMARY@; color: @ON_PRIMARY@; border: 1px solid @PRIMARY@; }
QPushButton#primary:hover { background: @PRIMARY_HOVER@; border-color: @PRIMARY_HOVER@; }
QPushButton#primary:pressed { background: @PRIMARY_PRESSED@; }
QPushButton#primary:focus { border: 1px solid @PRIMARY_FOCUS@; }
QPushButton#danger { color: @ERROR_TEXT@; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled {
    color: @DISABLED_TEXT@; border-color: @DISABLED_BORDER@; background: @DISABLED_BG@;
}
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background: @SURFACE@; border: 1px solid @CONTROL_BORDER@; border-radius: 4px;
    min-height: 20px; padding: 6px 8px;
    selection-background-color: @SELECTION@; selection-color: @SELECTION_TEXT@;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid @ACCENT@;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: @SIDEBAR@; color: @DISABLED_TEXT@; }
QSpinBox { padding-right: 30px; }
QSpinBox QLineEdit { border: none; padding: 0; min-height: 0; background: transparent; }
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border; width: 24px;
    background: @CHROME@; border-left: 1px solid @CONTROL_BORDER@;
    border-right: 1px solid @CONTROL_BORDER@;
}
QSpinBox::up-button {
    subcontrol-position: top right; border-top-right-radius: 4px;
    border-top: 1px solid @CONTROL_BORDER@;
    border-bottom: 1px solid @CONTROL_BORDER@;
}
QSpinBox::down-button {
    subcontrol-position: bottom right; border-bottom-right-radius: 4px;
    border-bottom: 1px solid @CONTROL_BORDER@;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: @HOVER@; }
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed { background: @PRESSED@; }
QSpinBox::up-button:disabled, QSpinBox::down-button:disabled { background: @DISABLED_BG@; }
QSpinBox::up-arrow { image: url("@CHEVRON_UP@"); width: 10px; height: 7px; }
QSpinBox::down-arrow { image: url("@CHEVRON@"); width: 10px; height: 7px; }
QComboBox::drop-down { width: 23px; border: none; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 12px; height: 8px; }
QComboBox QAbstractItemView {
    background: @SURFACE@; selection-background-color: @SELECTION@;
    selection-color: @SELECTION_TEXT@; padding: 4px; border: 1px solid @CONTROL_BORDER@;
}
QListWidget {
    background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 4px; outline: none;
}
QListWidget::item { padding: 7px 6px; border-bottom: 1px solid @GRID@; }
QListWidget::item:selected { background: @SELECTION@; color: @SELECTION_TEXT@; }
QTreeView {
    background: @SURFACE@; alternate-background-color: @ALTERNATE@; border: none;
    selection-background-color: @SELECTION@; selection-color: @SELECTION_TEXT@; outline: none;
}
QTreeView::item { min-height: 30px; padding: 2px 6px; }
QTreeView::item:hover { background: @HOVER@; }
QTreeView::item:selected { background: @SELECTION@; color: @SELECTION_TEXT@; }
QTreeView#workspaceTree { background: transparent; }
QTreeView#workspaceTree::item { min-height: 28px; padding: 2px 4px; }
QTreeView#workspaceTree::item:selected { border-radius: 3px; }
QTreeView#fileList::item { min-height: 36px; padding: 3px 9px; }
QTableView {
    background: @SURFACE@; alternate-background-color: @ALTERNATE@; border: none;
    gridline-color: @GRID@; selection-background-color: @SELECTION@;
    selection-color: @SELECTION_TEXT@; outline: none;
}
QTableView::item { padding: 4px 8px; border-bottom: 1px solid @GRID@; }
QTableView QLineEdit { padding: 1px 4px; min-height: 0; border: 1px solid @ACCENT@; }
QHeaderView { background: @CHROME@; }
QHeaderView::section {
    background: @CHROME@; color: @MUTED@; padding: 8px 9px; border: none;
    border-bottom: 1px solid @BORDER@; border-right: 1px solid @GRID@;
    font-weight: 500; font-size: 12px;
}
QTableCornerButton::section { background: @CHROME@; border: none; border-bottom: 1px solid @BORDER@; }
QScrollBar:vertical { background: @WINDOW@; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: @SCROLL_HANDLE@; border-radius: 4px; min-height: 25px; }
QScrollBar:horizontal { background: @WINDOW@; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: @SCROLL_HANDLE@; border-radius: 4px; min-width: 25px; }
QScrollBar::handle:hover { background: @SCROLL_HOVER@; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QProgressBar { border: none; background: @PROGRESS_TRACK@; height: 3px; }
QProgressBar::chunk { background: @ACCENT@; }
QStatusBar {
    background: @CHROME@; color: @MUTED@; font-size: 11px; border-top: 1px solid @BORDER@;
}
QStatusBar::item { border: none; }
QCheckBox { spacing: 7px; padding: 4px 0; }
QCheckBox::indicator, QAbstractItemView::indicator {
    width: 14px; height: 14px; border: 1px solid @MUTED@;
    border-radius: 3px; background: @SURFACE@;
}
QCheckBox::indicator:hover, QAbstractItemView::indicator:hover { border-color: @ACCENT@; }
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked {
    image: url("@CHECKMARK@"); background: @PRIMARY@; border-color: @PRIMARY@;
}
QCheckBox::indicator:focus { border: 2px solid @ACCENT@; }
QCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled {
    background: @DISABLED_BG@; border-color: @DISABLED_TEXT@;
}
QCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled {
    image: url("@CHECKMARK_DISABLED@");
}
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: @MUTED@; padding: 8px 11px;
    border-bottom: 2px solid @SEPARATOR@; font-weight: 500;
}
QTabBar::tab:selected { color: @SELECTION_TEXT@; border-bottom: 2px solid @ACCENT@; }
QToolTip { background: @SURFACE@; color: @TEXT@; border: 1px solid @CONTROL_BORDER@; padding: 6px; }
QLabel#sidebarTagline, QLabel#sidebarPrivacy, QLabel#hint { font-size: 11px; color: @MUTED@; }
QLabel#emptyIcon { color: @MUTED@; font-size: 36px; }
QToolButton { color: @MUTED@; border: 1px solid transparent; border-radius: 4px; padding: 4px 6px; }
QToolButton:disabled { color: @DISABLED_TEXT@; }
QToolButton:hover { background: @HOVER@; }
QToolButton:focus { border-color: @ACCENT@; }
QPushButton#filterToggle:checked { color: @SELECTION_TEXT@; background: @SELECTION@; border-color: @SELECTED_BORDER@; }
QSplitter::handle { background: @SEPARATOR@; }
QSplitter::handle:hover { background: @HOVER_BORDER@; }
QMenuBar { background: @CHROME@; border-bottom: 1px solid @BORDER@; }
QMenuBar::item { padding: 5px 9px; background: transparent; }
QMenuBar::item:selected { background: @SELECTION@; color: @SELECTION_TEXT@; }
QMenuBar::item:disabled { color: @DISABLED_TEXT@; }
QMenu { background: @SURFACE@; border: 1px solid @CONTROL_BORDER@; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; }
QMenu::item:selected { background: @SELECTION@; color: @SELECTION_TEXT@; }
QMenu::indicator { width: 14px; height: 14px; }
QMenu::item:disabled { color: @DISABLED_TEXT@; }
QMenu::separator { height: 1px; background: @SEPARATOR@; margin: 4px 6px; }
"""

# The rendered light stylesheet remains available to existing callers.
STYLE = scaled_style()
