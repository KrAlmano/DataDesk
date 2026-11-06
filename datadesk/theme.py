"""Shared, quiet desktop styling for DataDesk's files and tables."""

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
import re
from pathlib import Path

_shared_font_family = None


def scaled_style(percent=100):
    """Qt handles device DPI; this separately implements the user's UI zoom."""
    factor = percent / 100
    css = re.sub(r"(-?\d+(?:\.\d+)?)px", lambda match: f"{round(float(match[1]) * factor)}px", STYLE)
    return css.replace("@CHEVRON@", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())


def configure_app(app):
    global _shared_font_family
    app.setStyle("Fusion")
    # One bundled font keeps layout and typography consistent across platforms.
    font_file = Path(__file__).parent / "assets" / "fonts" / "Inter.ttf"
    if _shared_font_family is None and font_file.is_file():
        # Reading bytes also supports Windows install paths containing Turkish.
        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(font_file.read_bytes()))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _shared_font_family = families[0]
    app.setFont(QFont(_shared_font_family or app.font().family(), 12))
    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, "#f5f6f8"),
        (QPalette.ColorRole.WindowText, "#262b33"),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.AlternateBase, "#fafbfc"),
        (QPalette.ColorRole.Text, "#262b33"),
        (QPalette.ColorRole.Button, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#303640"),
        (QPalette.ColorRole.Highlight, "#e4edf8"),
        (QPalette.ColorRole.HighlightedText, "#234f85"),
        (QPalette.ColorRole.ToolTipBase, "#ffffff"),
        (QPalette.ColorRole.ToolTipText, "#262b33"),
        (QPalette.ColorRole.Link, "#3568a8"),
        (QPalette.ColorRole.PlaceholderText, "#7a818c"),
    ]:
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#9298a2"))
    app.setPalette(palette)


STYLE = """
QWidget { color: #262b33; font-size: 13px; }
QMainWindow { background: #ffffff; }
QDialog { background: #f7f8fa; }
QFrame#sidebar, QWidget#workspaceSidebar {
    background: #f3f4f6;
    border: none;
    border-right: 1px solid #dfe2e7;
}
QFrame#sidebar QLabel, QWidget#workspaceSidebar QLabel { color: #626a76; }
QFrame#sidebar QLabel#brand, QWidget#workspaceSidebar QLabel#workspaceHeading, QLabel#workspaceHeading {
    color: #262b33; font-size: 17px; font-weight: 600;
}
QFrame#sidebar QLabel#brandMark {
    background: transparent; color: #3568a8; font-size: 18px; font-weight: 600;
}
QFrame#sidebar QPushButton {
    color: #303640; background: #ffffff; border: 1px solid #d4d9e0;
    text-align: left; padding: 7px 10px;
}
QFrame#sidebar QPushButton:hover { background: #e9edf2; border-color: #b2bac5; }
QFrame#sidebar QListWidget {
    background: transparent; color: #4e5765; border: none; outline: none;
}
QFrame#sidebar QListWidget::item { padding: 7px 5px; border: none; border-radius: 3px; }
QFrame#sidebar QListWidget::item:selected { background: #dfe7f2; color: #234f85; }
QLabel#title, QLabel#folderTitle { font-size: 19px; font-weight: 600; color: #262b33; }
QLabel#sectionTitle, QLabel#emptyTitle { font-size: 14px; font-weight: 600; color: #303640; }
QLabel#eyebrow, QLabel#sidebarCaption, QLabel#sectionCaption {
    color: #626a76; font-size: 11px; font-weight: 600;
}
QLabel#muted, QLabel#emptyHint { color: #68717e; }
QLabel#breadcrumb { color: #626a76; font-size: 12px; }
QLabel#badge { color: #68717e; padding: 3px 0; font-size: 11px; }
QLabel#statValue { font-size: 18px; font-weight: 600; color: #303640; }
QFrame#card, QFrame#filterPanel {
    background: #ffffff; border: 1px solid #dfe2e7; border-radius: 4px;
}
QFrame#filterBody { background: #ffffff; border: none; }
QWidget#workspaceToolbar, QWidget#documentToolbar { background: #ffffff; }
QLabel#notice {
    background: #faf4e7; color: #76571d; padding: 8px 10px;
    border: 1px solid #eee2c8; border-radius: 4px; font-size: 12px;
}
QLabel#error {
    background: #fbefee; color: #a13d35; padding: 8px 10px;
    border: 1px solid #efd8d5; border-radius: 4px;
}
QPushButton {
    background: #ffffff; border: 1px solid #d4d9e0; border-radius: 4px;
    padding: 6px 10px; font-weight: 500;
}
QPushButton:hover { background: #f0f3f7; border-color: #aab6c6; }
QPushButton:pressed { background: #e5eaf0; }
QPushButton:focus { border: 1px solid #3568a8; }
QPushButton#primary { background: #3568a8; color: #ffffff; border: 1px solid #3568a8; }
QPushButton#primary:hover { background: #2c5b97; border-color: #2c5b97; }
QPushButton#primary:pressed { background: #244d82; }
QPushButton#primary:focus { border: 1px solid #1e426f; }
QPushButton#danger { color: #a13d35; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled {
    color: #9298a2; border-color: #e1e4e9; background: #f4f5f7;
}
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background: #ffffff; border: 1px solid #d4d9e0; border-radius: 4px;
    min-height: 20px; padding: 6px 8px;
    selection-background-color: #dce8f7; selection-color: #234f85;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3568a8;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #f3f4f6; color: #9298a2; }
QComboBox::drop-down { width: 23px; border: none; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 12px; height: 8px; }
QComboBox QAbstractItemView {
    background: #ffffff; selection-background-color: #e4edf8;
    selection-color: #234f85; padding: 4px; border: 1px solid #d4d9e0;
}
QListWidget {
    background: #ffffff; border: 1px solid #dfe2e7; border-radius: 4px; outline: none;
}
QListWidget::item { padding: 7px 6px; border-bottom: 1px solid #eff1f4; }
QListWidget::item:selected { background: #e4edf8; color: #234f85; }
QTreeView {
    background: #ffffff; alternate-background-color: #fafbfc; border: none;
    selection-background-color: #e4edf8; selection-color: #234f85; outline: none;
}
QTreeView::item { min-height: 30px; padding: 2px 6px; }
QTreeView::item:hover { background: #f0f3f7; }
QTreeView::item:selected { background: #e4edf8; color: #234f85; }
QTreeView#workspaceTree { background: transparent; }
QTreeView#workspaceTree::item { min-height: 28px; padding: 2px 4px; }
QTreeView#workspaceTree::item:selected { border-radius: 3px; }
QTreeView#fileList::item { min-height: 36px; padding: 3px 9px; }
QTableView {
    background: #ffffff; alternate-background-color: #fafbfc; border: none;
    gridline-color: #e9edf1; selection-background-color: #e4edf8;
    selection-color: #234f85; outline: none;
}
QTableView::item { padding: 4px 8px; border-bottom: 1px solid #eff1f4; }
QHeaderView { background: #f7f8fa; }
QHeaderView::section {
    background: #f7f8fa; color: #626a76; padding: 8px 9px; border: none;
    border-bottom: 1px solid #dfe2e7; border-right: 1px solid #e9edf1;
    font-weight: 500; font-size: 12px;
}
QTableCornerButton::section { background: #f7f8fa; border: none; border-bottom: 1px solid #dfe2e7; }
QScrollBar:vertical { background: #f5f6f8; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #c6ccd5; border-radius: 4px; min-height: 25px; }
QScrollBar:horizontal { background: #f5f6f8; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #c6ccd5; border-radius: 4px; min-width: 25px; }
QScrollBar::handle:hover { background: #acb5c1; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QProgressBar { border: none; background: #e8edf4; height: 3px; }
QProgressBar::chunk { background: #3568a8; }
QStatusBar {
    background: #f7f8fa; color: #68717e; font-size: 11px; border-top: 1px solid #dfe2e7;
}
QStatusBar::item { border: none; }
QCheckBox { spacing: 7px; padding: 4px 0; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: #68717e; padding: 8px 11px;
    border-bottom: 2px solid #e7eaf0; font-weight: 500;
}
QTabBar::tab:selected { color: #234f85; border-bottom: 2px solid #3568a8; }
QToolTip { background: #ffffff; color: #303640; border: 1px solid #d4d9e0; padding: 6px; }
QLabel#sidebarTagline, QLabel#sidebarPrivacy, QLabel#hint { font-size: 11px; color: #68717e; }
QLabel#emptyIcon { color: #9aa5b5; font-size: 36px; }
QToolButton { color: #4e5765; border: 1px solid transparent; border-radius: 4px; padding: 4px 6px; }
QToolButton:hover { background: #e9edf2; }
QToolButton:focus { border-color: #3568a8; }
QPushButton#filterToggle:checked { color: #234f85; background: #e4edf8; border-color: #9eb7d5; }
QSplitter::handle { background: #e7eaf0; }
QSplitter::handle:hover { background: #c6d3e5; }
QMenuBar { background: #f7f8fa; border-bottom: 1px solid #dfe2e7; }
QMenuBar::item { padding: 5px 9px; background: transparent; }
QMenuBar::item:selected { background: #e4edf8; }
QMenu { background: #ffffff; border: 1px solid #d4d9e0; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; }
QMenu::item:selected { background: #e4edf8; color: #234f85; }
QMenu::item:disabled { color: #9298a2; }
QMenu::separator { height: 1px; background: #e7eaf0; margin: 4px 6px; }
"""

STYLE = STYLE.replace("@CHEVRON@", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())
