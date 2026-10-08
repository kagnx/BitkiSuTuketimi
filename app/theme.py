# -*- coding: utf-8 -*-
"""Fıstık yeşili profesyonel tema (QSS)."""

PRIMARY = "#7CB342"        # fıstık yeşili ana renk
PRIMARY_DARK = "#558B2F"
PRIMARY_LIGHT = "#AED581"
ACCENT = "#33691E"
BG_DARK = "#1E2A1A"        # koyu zümrüt-koyu yeşil kenar çubuğu
BG_MAIN = "#F4F7F1"        # açık sayfa zemini
BG_CARD = "#FFFFFF"
TEXT_DARK = "#26311F"
TEXT_MUTED = "#6B7A5E"
BORDER = "#D8E3CC"
OK = "#7CB342"
WARN = "#F9A825"
DANGER = "#C62828"

QSS = f"""
* {{ font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; color: {TEXT_DARK}; }}
QMainWindow, QDialog {{ background: {BG_MAIN}; }}
QWidget#sidebar {{ background: {BG_DARK}; }}
QLabel#appTitle {{ color: #E8F5D5; font-size: 19px; font-weight: 700; }}
QLabel#appSub {{ color: #A9C49A; font-size: 11px; }}
QLabel#pageTitle {{ font-size: 17px; font-weight: 700; color: {PRIMARY_DARK}; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 700; color: {PRIMARY_DARK}; }}
QLabel#muted {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#big {{ font-size: 26px; font-weight: 800; color: {PRIMARY_DARK}; }}
QLabel#okText {{ color: {OK}; font-weight: 700; }}
QLabel#warnText {{ color: {WARN}; font-weight: 700; }}
QLabel#dangerText {{ color: {DANGER}; font-weight: 700; }}

QPushButton {{
    background: {PRIMARY}; color: white; border: none; border-radius: 6px;
    padding: 8px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {PRIMARY_DARK}; }}
QPushButton:pressed {{ background: {ACCENT}; }}
QPushButton:checked {{ background: {ACCENT}; }}
QPushButton:disabled {{ background: #B8CCAA; color: #E8F1DF; }}
QPushButton#navBtn {{
    background: transparent; color: #D7E7C9; border: none; border-radius: 8px;
    text-align: left; padding: 10px 14px; font-size: 13px; font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: #2E4028; color: #FFFFFF; }}
QPushButton#navBtn:checked {{ background: {PRIMARY}; color: white; }}
QPushButton#danger {{ background: {DANGER}; }}
QPushButton#ghost {{
    background: transparent; color: {PRIMARY_DARK}; border: 1px solid {PRIMARY};
    border-radius: 6px; padding: 7px 14px; font-weight: 600;
}}
QPushButton#ghost:hover {{ background: #EAF4E0; }}
QPushButton#ghost:checked {{ background: {PRIMARY}; color: white; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {{
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 8px; selection-background-color: {PRIMARY_LIGHT}; selection-color: {TEXT_DARK};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {PRIMARY_DARK}; margin-right: 6px; }}
QComboBox QAbstractItemView {{ background: {BG_CARD}; border: 1px solid {BORDER}; selection-background-color: {PRIMARY}; }}

QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 8px; margin-top: 12px;
    background: {BG_CARD}; font-weight: 700; color: {PRIMARY_DARK};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}

QTableWidget, QTableView {{
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    gridline-color: #EAF1E2; alternate-background-color: #F6FAF1;
}}
QHeaderView::section {{
    background: #E8F1DC; color: {ACCENT}; border: none; border-bottom: 2px solid {PRIMARY_LIGHT};
    padding: 8px; font-weight: 700;
}}
QTableWidget::item {{ padding: 6px; }}
QTableWidget::item:selected {{ background: {PRIMARY_LIGHT}; color: {TEXT_DARK}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: {BG_CARD}; top: -1px; }}
QTabBar::tab {{
    background: #E8F1DC; color: {PRIMARY_DARK}; padding: 8px 18px; margin-right: 2px;
    border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600;
}}
QTabBar::tab:selected {{ background: {PRIMARY}; color: white; }}
QTabBar::tab:hover:!selected {{ background: {PRIMARY_LIGHT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #BCD0A8; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #BCD0A8; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #A8BE93; border-radius: 4px; background: white; }}
QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY_DARK}; }}
QRadioButton {{ spacing: 6px; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid #A8BE93; border-radius: 8px; background: white; }}
QRadioButton::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY_DARK}; }}

QStatusBar {{ background: {BG_DARK}; color: #D7E7C9; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background: {BG_DARK}; color: white; border: 1px solid {PRIMARY}; padding: 4px; }}

QSplitter::handle {{ background: {BORDER}; width: 3px; }}

QProgressBar {{ background: #E8F1DC; border: none; border-radius: 6px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 6px; }}

QMessageBox {{ background: {BG_MAIN}; }}
QListWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid #EEF3E8; }}
QListWidget::item:selected {{ background: {PRIMARY}; color: white; }}
"""
