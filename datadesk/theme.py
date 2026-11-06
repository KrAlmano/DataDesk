"""DataDesk's restrained, accessible desktop palette."""

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
import re
from pathlib import Path


def scaled_style(percent=100):
    """Qt handles device DPI; this separately implements the user's UI zoom."""
    factor = percent / 100
    css = re.sub(r"(-?\d+(?:\.\d+)?)px", lambda match: f"{round(float(match[1]) * factor)}px", STYLE)
    return css.replace("@CHEVRON@", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())


def configure_app(app):
    app.setStyle("Fusion")
    # Ship one font, so Windows and macOS use the same typography and metrics.
    font_file = Path(__file__).parent / "assets" / "fonts" / "Inter.ttf"
    families = QFontDatabase.families()
    if "Inter" not in families and font_file.is_file():
        QFontDatabase.addApplicationFont(str(font_file))
        families = QFontDatabase.families()
    app.setFont(QFont("Inter" if "Inter" in families else app.font().family(), 12))
    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, "#f4f7f6"),
        (QPalette.ColorRole.WindowText, "#233a39"),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.AlternateBase, "#f8fbf9"),
        (QPalette.ColorRole.Text, "#233a39"),
        (QPalette.ColorRole.Button, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#233a39"),
        (QPalette.ColorRole.Highlight, "#dcefe2"),
        (QPalette.ColorRole.HighlightedText, "#153b2a"),
    ]:
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#a6b4ad"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#a6b4ad"))
    app.setPalette(palette)


STYLE = """
QWidget { color: #233a39; font-size: 13px; }
QMainWindow, QDialog { background: #f4f7f6; }
QFrame#sidebar { background: #142e2b; border: none; }
QFrame#sidebar QLabel { color: #acbfbb; }
QFrame#sidebar QLabel#brand { color: #ffffff; font-size: 27px; font-weight: 700; letter-spacing: -1px; }
QFrame#sidebar QLabel#brandMark { background: #b9eb99; color: #19352c; border-radius: 12px; font-size: 19px; font-weight: 800; }
QFrame#sidebar QPushButton { color: #cfdfda; background: transparent; border: 1px solid #3d5750; text-align: left; padding: 11px 14px; }
QFrame#sidebar QPushButton:hover { background: #24443b; border-color: #789b84; }
QFrame#sidebar QPushButton#primary { background: #b9eb99; color: #17372c; border: none; font-weight: 700; }
QFrame#sidebar QListWidget { background: transparent; color: #bed0ca; border: none; outline: none; }
QFrame#sidebar QListWidget::item { padding: 10px 8px; border-radius: 7px; }
QFrame#sidebar QListWidget::item:selected { background: #2d4a41; color: white; }
QLabel#eyebrow { color: #526f62; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#title { font-size: 27px; font-weight: 700; letter-spacing: -0.6px; color: #193c34; }
QLabel#muted { color: #526f62; }
QLabel#badge { border: 1px solid #cfdfd6; background: #edf5ef; border-radius: 13px; padding: 5px 10px; color: #397353; font-size: 11px; font-weight: 600; }
QLabel#statValue { font-size: 28px; font-weight: 650; color: #1c4236; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #234138; }
QFrame#card { background: #ffffff; border: 1px solid #dfe8e2; border-radius: 12px; }
QFrame#filterPanel { background: #ffffff; border: 1px solid #dfe8e2; border-radius: 12px; }
QFrame#filterBody { background: #ffffff; border: none; }
QLabel#notice { background: #fff5de; color: #765719; padding: 10px 12px; border-radius: 8px; font-size: 12px; }
QLabel#error { background: #fcebe8; color: #973a2e; padding: 10px 12px; border-radius: 8px; }
QPushButton { background: #ffffff; border: 1px solid #d8e3dc; border-radius: 7px; padding: 8px 13px; font-weight: 550; }
QPushButton:hover { background: #f0f6f1; border-color: #90b7a0; }
QPushButton:pressed { background: #e5f0e8; }
QPushButton:focus { border: 2px solid #4b805d; }
QPushButton#primary { background: #236d50; color: #ffffff; border: 1px solid #236d50; }
QPushButton#primary:hover { background: #18563e; }
QPushButton#primary:focus { border: 2px solid #123c29; background: #18563e; }
QFrame#sidebar QPushButton#primary:focus { border: 2px solid #123c29; }
QPushButton#danger { color: #a1493c; }
QPushButton:disabled { color: #a6b4ad; border-color: #e4ebe7; background: #f1f4f2; }
QPushButton#primary:disabled, QPushButton#danger:disabled { color: #a6b4ad; border-color: #e4ebe7; background: #f1f4f2; }
QFrame#sidebar QPushButton#primary:disabled { color: #8fa69a; background: #3b5348; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #d8e3dc; border-radius: 6px; min-height: 20px; padding: 7px 9px; selection-background-color: #cce7d1; selection-color: #1a3f30; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #438561; }
QComboBox::drop-down { width: 23px; border: none; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e6f1e9; selection-color: #183c2c; padding: 4px; }
QListWidget { background: #f8faf8; border: 1px solid #e2ebe5; border-radius: 6px; outline: none; }
QListWidget::item { padding: 9px 7px; border-bottom: 1px solid #e6eee8; }
QListWidget::item:selected { background: #e1f0e5; color: #214b35; }
QTableView { background: #ffffff; alternate-background-color: #f8fbf9; border: none; gridline-color: #edf1ee; selection-background-color: #dcefe2; selection-color: #153b2a; outline: none; }
QTableView::item { padding: 5px 10px; border-bottom: 1px solid #edf1ee; }
QHeaderView { background: #f3f7f4; }
QHeaderView::section { background: #f3f7f4; color: #587267; padding: 11px 12px; border: none; border-bottom: 1px solid #dfe8e2; border-right: 1px solid #e8efea; font-weight: 650; font-size: 12px; }
QTableCornerButton::section { background: #f3f7f4; border: none; }
QScrollBar:vertical { background: #f6f8f6; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #c5d4ca; border-radius: 4px; min-height: 25px; }
QScrollBar:horizontal { background: #f6f8f6; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #c5d4ca; border-radius: 4px; min-width: 25px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QProgressBar { border: none; background: #e2ece5; height: 3px; }
QProgressBar::chunk { background: #4c9668; }
QStatusBar { background: #eef4ef; color: #607a6c; font-size: 11px; border-top: 1px solid #dfe8e2; }
QCheckBox { spacing: 7px; padding: 4px 0; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: #526f62; padding: 10px 12px; border-bottom: 2px solid #e5ede7; font-weight: 600; }
QTabBar::tab:selected { color: #236d50; border-bottom: 2px solid #3b8059; }
QToolTip { background: #193b2b; color: #ffffff; border: none; padding: 6px; }
QLabel#sidebarTagline { font-size: 11px; }
QLabel#sidebarCaption { font-size: 10px; letter-spacing: 1px; font-weight: 700; }
QLabel#sidebarPrivacy { font-size: 11px; color: #b3c8bc; }
QLabel#hint { color: #526f62; font-size: 11px; }
QLabel#emptyIcon { color: #91b49c; font-size: 64px; }
QToolButton { color: #365d47; border: none; border-radius: 5px; padding: 4px 6px; }
QToolButton:hover { background: #dcebe0; }
QToolButton:focus { border: 1px solid #438561; }
QPushButton#filterToggle:checked { color: #18583e; background: #e1f0e5; border-color: #7fae8e; }
QSplitter::handle:hover { background: #d4e4d9; }
"""

STYLE = STYLE.replace("@CHEVRON@", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())
