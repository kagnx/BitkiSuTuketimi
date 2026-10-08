# -*- coding: utf-8 -*-
"""Görsel doğrulama: gerçek platformda pencereyi render eder, tema renklerini
kontrol eder ve ekran görüntüsünü kaydeder.  python tests/visual_check.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# gerçek platform kullan (Windows); yoksa offscreen'e düş
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor

from app.main_window import MainWindow
from app.theme import BG_DARK, PRIMARY

app = QApplication([])
win = MainWindow()
win.resize(1280, 800)
win.show()
for _ in range(5):
    app.processEvents()

# hesap çalıştır (grafik dolu olsun)
win.plant_combo.setCurrentIndex(0)
win.run_calculation()
app.processEvents()

img = win.grab().toImage()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raporlar", "onizleme.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)


def sample(x, y):
    c = img.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def near(c1, c2, tol=28):
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# kenar çubuğu koyu yeşil olmalı
sidebar_ok = any(near(sample(10, y), hexrgb(BG_DARK)) for y in range(100, 700, 40))
print("Kenar çubuğu (koyu yeşil):", sidebar_ok)

# ilk nav butonu (seçili) fıstık yeşili olmalı
nav_ok = any(near(sample(x, y), hexrgb(PRIMARY)) for x in range(20, 200, 10) for y in range(130, 190, 8))
print("Nav butonu (fıstık yeşili):", nav_ok)

# sayfaları gez
for i in range(6):
    win.nav_buttons[i].setChecked(True)
    win.nav_buttons[i].click()
    app.processEvents()
    win.grab()
    print(f"Sayfa {i} render OK")

win.show()
app.processEvents()
print("Önizleme kaydedildi:", out)
if not (sidebar_ok and nav_ok):
    print("UYARI: tema renk kontrolü başarısız")
    sys.exit(1)
print("=== GÖRSEL KONTROL BAŞARILI ===")
