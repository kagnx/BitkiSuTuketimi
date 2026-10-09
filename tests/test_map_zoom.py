# -*- coding: utf-8 -*-
"""Harita zoom regresyon testleri.

Kapsar:
- zoom_in sınırı: MAX_Z (22) aşılamaz
- zoom_out sınırı: MIN_Z (3) altına inilemez
- zoom_to: aralık dışı değerler tutturulur
- effective_tile_z: katman native sınırını aşan seviyelerde indirme
  max_z'e tutturulur (overzoom)
- parent_tile: ata karo ve alt bölge matematiği doğruluğu
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.mapwidget import (MapCanvas, MIN_Z, MAX_Z, TILE, effective_tile_z,
                           parent_tile, layer_max_z)

app = QApplication.instance() or QApplication([])


def _canvas(z=11):
    c = MapCanvas()
    c.set_online(False)  # ağ trafiği yok: yalnız çevrimdışı mantık
    c.zoom_to(z)
    return c


def test_zoom_sinirlari_buton():
    c = _canvas(MIN_Z)
    for _ in range((MAX_Z - MIN_Z) + 10):
        c.zoom_in()
    assert c.zoom == MAX_Z, f"maksimum yakınlaşma: {c.zoom}"
    for _ in range((MAX_Z - MIN_Z) + 10):
        c.zoom_out()
    assert c.zoom == MIN_Z, f"minimum uzaklaşma: {c.zoom}"


def test_zoom_to_tutturma():
    c = _canvas()
    c.zoom_to(MAX_Z + 50)
    assert c.zoom == MAX_Z
    c.zoom_to(MIN_Z - 50)
    assert c.zoom == MIN_Z
    c.zoom_to(15)
    assert c.zoom == 15


def test_katman_native_sinir():
    assert 18 <= layer_max_z("g_hyb") <= MAX_Z
    assert 18 <= layer_max_z("g_sat") <= MAX_Z
    assert 18 <= layer_max_z("osm") <= MAX_Z
    assert 18 <= layer_max_z("esri") <= MAX_Z
    assert layer_max_z("bilinmeyen") == MAX_Z


def test_effective_tile_z_overzoom():
    # 22. seviyede Google (max 20) için indirme 20'ye tutturulur
    assert effective_tile_z(MAX_Z, "g_sat") == 20
    assert effective_tile_z(MAX_Z, "osm") == 19
    assert effective_tile_z(15, "osm") == 15
    assert effective_tile_z(2, "osm") == MIN_Z


def test_parent_tile_matematik():
    # z=22, (100, 200) karosu z_eff=20 için: her eksende 4 kat
    px, py, f, sx, sy, s = parent_tile(22, 100, 200, 20)
    assert (px, py) == (25, 50)
    assert f == 4
    assert s == TILE // 4
    assert sx == (100 % 4) * s and sy == (200 % 4) * s
    # ata bölgesinden geri genişleyen hedef karo tam kapsanmalı
    assert 0 <= sx < TILE and 0 <= sy < TILE
    assert sx + s <= TILE and sy + s <= TILE


def test_canvas_overzoom_kuralı():
    c = _canvas(MAX_Z)
    assert c.zoom == MAX_Z
    assert c.layer_native_max() <= MAX_Z
    assert effective_tile_z(c.zoom, c.tile_key) <= c.zoom
    # çevrimdışı yeniden çizim çökmeden çalışmalı
    c.apply_transform()
    c.tile_layer.update()