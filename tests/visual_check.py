# -*- coding: utf-8 -*-
"""Görsel doğrulama: gerçek platformda pencereyi render eder, tema renklerini
kontrol eder ve ekran görüntüsünü kaydeder.  python tests/visual_check.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# gerçek platform kullan (Windows); yoksa offscreen'e düş
os.environ.pop("QT_QPA_PLATFORM", None)

# Konsol çıkışı UTF-8'e sar (bkz. tests/smoke_test.py) — cp1252 konsolunda
# Türkçe karakterli print'ler UnicodeEncodeError'a yol açıyor.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass
# Windows CI runner'da stdout cp1252'dir; Türkçe karakterli print() çağrıları
# UnicodeEncodeError atıyordu. Çıktıyı UTF-8'e sabitle.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# CI runner'larda stdout cp1252 olabilir; Türkçe print'ler çökmesin.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
