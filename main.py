# -*- coding: utf-8 -*-
"""ProSU — Tarımsal Su İhtiyacı Hesaplama Sistemi (giriş noktası).

Çalıştırma:  python main.py
"""
import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ProSU")
    app.setOrganizationName("ProSU")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
