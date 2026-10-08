# -*- coding: utf-8 -*-
"""Uygulamanın yazılabilir klasörlerini (data, raporlar, ayarlar) çözer.

- Kaynak koddan (python main.py) çalıştırılırken: proje kökü.
- PyInstaller tek exe (--onefile) olarak çalıştırılırken: exe'nin bulunduğu klasör.
  Böylece veritabanı ve raporlar geçici çıkarma klasörüne (sys._MEIPASS) değil,
  exe'nin yanına yazılır ve kalıcı olur.
"""
import os
import sys


def app_base_dir():
    """Veri/rapor dosyalarının yazılacağı ana klasör."""
    if getattr(sys, "frozen", False):
        # PyInstaller tek exe: exe'nin yanı
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DATA_DIR = os.path.join(app_base_dir(), "data")
REPORT_DIR = os.path.join(app_base_dir(), "raporlar")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DB_PATH = os.path.join(DATA_DIR, "prosu.db")
