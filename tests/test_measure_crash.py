# -*- coding: utf-8 -*-
"""Ölçüm (measure) modu regresyon testleri.

Kapsar (kullanıcı bildirimi: "ölçüm yapınca uygulama çöktü"):
- İki+ nokta ile ölçüm yapılırken Qt sahne çizimi çökmez.
  Önceki hata: QGraphicsPathItem.setBrush(Qt.BrushStyle.NoBrush) çağrısı
  PyQt6'da TypeError veriyordu; yakalanmayan istisna Qt slot'unda
  abort() tetikleyip uygulamayı anında kapatıyordu (exit 0xC0000409).
- refresh_items() ölçüm parça çizgisi ve mesafe etiketi oluştururken hata vermez.
- pixel_to_lonlat: ekstrem/harita dışı koordinatlarda OverflowError vermez;
  sonuçlar geçerli aralıkta döner (lon [-180,180], lat ±Mercator sınırı).
- Yüksek zoom (MAX_Z=22) koordinat dönüşümü çift yönlü tutarlıdır.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from app.mapwidget import (MapCanvas, MAX_Z, LAT_LIMIT, lonlat_to_pixel,
                           pixel_to_lonlat)

app = QApplication.instance() or QApplication([])

MODE_MEASURE = MapCanvas.MODE_MEASURE


def _press(cv, pt):
    """Viewport'a sol tıklama olayı gönderir (ölçüm noktası ekler)."""
    ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress, pt,
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(cv.viewport(), ev)


def _measure_canvas(z=MAX_Z):
    c = MapCanvas()
    c.set_online(False)  # ağ trafiği yok
    c.set_mode(MODE_MEASURE)
    c.set_center(32.85, 39.90, z)
    return c


def test_olcum_iki_nokta_cokmez():
    """İkinci noktada (parça çizgisi + etiket) çökme olmamalı."""
    c = _measure_canvas()
    _press(c, QPointF(300, 300))
    _press(c, QPointF(360, 340))          # <- eski kod burada çöküyordu
    _press(c, QPointF(420, 260))
    assert len(c._measure_pts) == 3, f"ölçüm noktası: {len(c._measure_pts)}"
    # nokta + parça çizgisi + mesafe etiketi öğeleri üretilmeli
    assert len(c._item_refs) >= 3


def test_refresh_items_measure_segment():
    """refresh_items doğrudan çağrıldığında ölçüm çizimi hata vermez."""
    c = _measure_canvas()
    c._measure_pts = [[32.85, 39.90], [32.851, 39.900], [32.849, 39.899]]
    c.refresh_items()  # istisna fırlatmamalı
    assert len(c._item_refs) >= 3


def test_olcum_harita_disi_koordinatlar():
    """Harita dışına kaydırma sonrası da ölçüm çökmeden çalışır."""
    c = _measure_canvas()
    c.center_lonlat = (180.0, 0.0)
    c.apply_transform()
    _press(c, QPointF(300, 300))
    _press(c, QPointF(360, 320))
    assert len(c._measure_pts) == 2
    for lon, lat in c._measure_pts:
        assert -180.0 <= lon <= 180.0
        assert -LAT_LIMIT <= lat <= LAT_LIMIT


def test_pixel_to_lonlat_ekstrem_tasmaz():
    """math.sinh OverflowError vermeden geçerli aralık döner."""
    for (x, y, z) in [(0, 0, MAX_Z), (300, 300, MAX_Z), (6e8, 4.1e8, MAX_Z),
                      (1e12, -1e12, MAX_Z), (-1e9, 1e9, MAX_Z),
                      (-1e12, 1e12, MAX_Z)]:
        lon, lat = pixel_to_lonlat(x, y, z)
        assert -180.0 <= lon <= 180.0, f"boylam aralık dışı: {lon}"
        assert -LAT_LIMIT <= lat <= LAT_LIMIT, f"enlem aralık dışı: {lat}"


def test_piksel_koordinat_roundtrip():
    """MAX_Z'de lonlat -> piksel -> lonlat dönüşümü tutarlı."""
    lon, lat = 32.5, 37.8
    x, y = lonlat_to_pixel(lon, lat, MAX_Z)
    assert x > 0 and y > 0
    lon2, lat2 = pixel_to_lonlat(x, y, MAX_Z)
    assert abs(lon2 - lon) < 1e-6, f"boylam: {lon2}"
    assert abs(lat2 - lat) < 1e-6, f"enlem: {lat2}"


def test_boylam_sarma():
    """180°'yi aşan boylam [-180,180] aralığına sarılır."""
    lon, _lat = pixel_to_lonlat(1e12, 4.1e8, MAX_Z)
    assert -180.0 <= lon <= 180.0
