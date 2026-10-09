# -*- coding: utf-8 -*-
"""Smoke test: modüller, hesap, koordinat, UI kurulumu."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Windows konsolunda kod sayfası cp1252 olduğunda Türkçe karakterler (ı ğ ş İ ç ö)
# UnicodeEncodeError'a yol açıyordu (GitHub Actions runner'ında smoke test bu
# yüzden 1. saniyede düşüyordu). Stdout/stderr'i UTF-8'e sar: bu yalnızca bu
# betiğin konsol çıktısını etkiler, uygulama içi davranışı değiştirmez.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass
# Windows CI runner'da stdout cp1252'dir; Türkçe karakterli print() çağrıları
# UnicodeEncodeError atıyor ve betik ilk satırda ölüyordu. Çıktıyı UTF-8'e sabitle.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # stdout değiştirilemezse sessizce devam
    pass

# CI runner'larda (özel. Windows) stdout cp1252 olabilir ve bu betik sadelikle
# Türkçe karakter basar. Python < 3.15 "locale" kodlayıcıyı kullanır, bu yüzden
# print('...ış...') natamamlıkla UnicodeEncodeError ile çöker; test hiçbir
# iş kalmadan 1 saniyede düşer.  UTF-8'e zorlamak yeterlidir.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from datetime import date

# 1) koordinat testleri
from app.coords import lonlat_to_tm, tm_to_lonlat, tm_zone_for_lon, polygon_area_m2, haversine

# bilinen nokta: UTM dilim 33 (meridyen 15°E), k0=0.9996, φ=42, λ=15 → E=500000, N≈4649776.22
x, y = lonlat_to_tm(15.0, 42.0, zone=33, tm3=False)
assert abs(x - 500000.0) < 0.5, f"UTM X hatalı: {x}"
assert abs(y - 4649776.22) < 0.5, f"UTM Y hatalı: {y}"
lon, lat = tm_to_lonlat(x, y, zone=33, tm3=False)
assert abs(lon - 15.0) < 1e-9 and abs(lat - 42.0) < 1e-9, (lon, lat)
print(f"UTM dönüşüm OK: ({x:.2f}, {y:.2f}) -> ({lon:.9f}, {lat:.9f})")

# TM3 Konya
x3, y3 = lonlat_to_tm(32.4833, 37.8667, zone=30)
lon3, lat3 = tm_to_lonlat(x3, y3, zone=30)
assert abs(lon3 - 32.4833) < 1e-6 and abs(lat3 - 37.8667) < 1e-6
print(f"TM3 dönüşüm OK: Konya -> X={x3:,.1f} Y={y3:,.1f}")

# alan: 100m x 100m kare (yaklaşık)
sq = [(32.5, 37.8), (32.5011, 37.8), (32.5011, 37.8009), (32.5, 37.8009)]
a = polygon_area_m2(sq)
assert 9000 < a < 11000, f"Alan hatalı: {a}"
d = haversine(32.5, 37.8, 32.5011, 37.8)
assert 95 < d < 105, f"Mesafe hatalı: {d}"
print(f"Alan/mesafe OK: {a:.0f} m², {d:.1f} m")

# 2) veritabanı
from app.database import Database
import tempfile
tmpdb = os.path.join(tempfile.mkdtemp(), "test.db")
db = Database(tmpdb)
plants = db.list_plants()
cats = db.plant_count_by_category()
print(f"Bitki sayısı: {len(plants)}, kategoriler: {cats}")
assert len(plants) > 100

# 3) hesap
from app.climate import ClimateData
from app.calculations import compute_water_need, monthly_eto, effective_rainfall

clim = ClimateData()
eto = monthly_eto(clim)
print("Aylık ETo (FAO-56):", [round(v, 1) for v in eto])
assert 0.5 < eto[0] < 3, "Ocak ETo mantıksız"
assert 4 < eto[6] < 9, "Temmuz ETo mantıksız"
pe = effective_rainfall(clim.p)
print("Etkili yağış:", [round(v, 1) for v in pe])

p = db.list_plants(kategori="Sebze", arama="Domates")[0]
res = compute_water_need(p, clim, {
    "ekim_tarihi": date(2024, 4, 1), "alan_da": 10.0,
    "eto_method": "FAO-56 Penman-Monteith", "rain_method": "USDA-SCS",
    "toprak": "Tınlı", "sistem": "Damla Sulama", "mad": 0.5,
})
print(f"Hesap [{p['ad']}]: ETc={res['tot_et']:.0f} mm, net={res['tot_net']:.0f} mm, "
      f"brüt={res['tot_gross']:.0f} mm, m³ net={res['total_m3_net']:,.0f}, aralık={res['interval']} gün")
assert res["tot_et"] > 100, "ETc çok düşük"
assert res["tot_gross"] >= res["tot_net"] >= 0

# ağaç hesabı
elma = db.list_plants(kategori="Meyve", arama="Elma")[0]
res2 = compute_water_need(elma, clim, {
    "ekim_tarihi": date(2024, 3, 1), "alan_da": 20.0,
    "eto_method": "Hargreaves-Samani", "rain_method": "FAO Basit Yöntem",
    "toprak": "Killi", "sistem": "Damla Sulama", "mad": 0.4,
})
print(f"Elma: sezon {res2['tot_net']:.0f} mm, ağaç başına {res2['per_tree']['sezon_brut_litre']:,.0f} L brüt")
assert res2["per_tree"] is not None

# 4) rapor
from app.report import build_report_html
html_doc = build_report_html(res)
assert "ProSU" in html_doc
print(f"HTML rapor uzunluğu: {len(html_doc)}")

# 5) UI kurulumu
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from app.main_window import MainWindow
win = MainWindow()
win.show()
app.processEvents()
print("MainWindow kuruldu:", win.windowTitle())
print("Sayfalar:", list(win.pages.keys()))

# harita hızlı testi
win.map.set_center(35.5, 39.0, zoom=10)
app.processEvents()
win.map.add_marker(35.5, 39.0, "Test Noktası")
app.processEvents()
print("Harita testi OK")

# parsel çizimi simülasyonu
from app.mapwidget import lonlat_to_pixel, pixel_to_lonlat
x0, y0 = lonlat_to_pixel(35.5, 39.0, 10)
lon_r, lat_r = pixel_to_lonlat(x0, y0, 10)
assert abs(lon_r - 35.5) < 1e-9 and abs(lat_r - 39.0) < 1e-9

# hesap sayfası: hesaplama çalıştır
win.plant_combo.setCurrentIndex(0)
win.run_calculation()
assert win.last_result is not None
print("UI hesaplama OK")

print("\n=== TÜM SMOKE TESTLER BAŞARILI ===")
