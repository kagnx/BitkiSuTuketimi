# -*- coding: utf-8 -*-
"""u2 / ETo regresyon testleri.

Kapsadığı hatalar:
- Open-Meteo'nun km/h değerinin m/s sanılması (eski hata: u2 ~3.6 kat şişerdi)
- wind_speed_10m_max yerine wind_speed_10m_mean kullanılmaması (ekstra ~%15 sapma)
- FAO-56 ETo motorunda formül/regresyon değişiklikleri (bilinen taban değerler)

Çevrimdışı testler her koşuda çalışır; canlı API testi ağ yoksa atlanır (skip).
"""
from datetime import date, timedelta

import pytest

from app.calculations import monthly_eto
from app.climate import DEFAULT_CLIMATE, REGIONAL_CLIMATE, ClimateData, fetch_openmeteo

# Varsayılan Konya iklimiyle FAO-56 Penman-Monteith aylık ETo (mm/gün) —
# motorun bilinen taban değerleri; formül değişikliğini yakalar.
ETO_BASELINE = [0.8647, 1.2878, 2.1506, 3.2568, 4.4819, 5.8035,
                6.895, 6.0958, 4.3274, 2.51, 1.3285, 0.8419]
ETO_TOL = 0.05  # mm/gün


# ----------------------------- çevrimdışı: u2 aralığı -----------------------------

def test_on_tanimli_iklimlerde_u2_araligi():
    """Tüm ön tanımlı iklimlerde u2 fiziksel m/s aralığında olmalı (0.5–6)."""
    u2_vals = list(DEFAULT_CLIMATE["u2"])
    for ad, d in REGIONAL_CLIMATE.items():
        u2_vals.extend(d["u2"])
    assert u2_vals, "u2 verisi yok"
    assert min(u2_vals) >= 0.5, f"u2 çok düşük: {min(u2_vals)}"
    assert max(u2_vals) <= 6.0, f"u2 çok yüksek: {max(u2_vals)} (birim/mm hatası olabilir)"


def test_eto_aylik_regresyon_toleransi():
    """Varsayılan Konya iklimi aylık ETo taban değerlere ±0.05 mm/gün uymalı."""
    eto = monthly_eto(ClimateData())
    assert len(eto) == 12
    for i, (v, b) in enumerate(zip(eto, ETO_BASELINE)):
        assert abs(v - b) <= ETO_TOL, (
            f"ay {i+1}: ETo {v:.3f} != taban {b:.3f} (tolerans {ETO_TOL})")


# --------------------- çevrimdışı: fetch birim/alan regresyonu ---------------------

class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def _fake_daily(wind_mean=None, wind_max=None):
    """365 günlük sabit değerli sahte Open-Meteo yanıtı."""
    today = date.today()
    days = [(today - timedelta(days=k)).isoformat() for k in range(365, 0, -1)]
    n = len(days)
    d = {
        "time": days,
        "temperature_2m_max": [20.0] * n,
        "temperature_2m_min": [10.0] * n,
        "precipitation_sum": [0.0] * n,
        "sunshine_duration": [43200.0] * n,
        "relative_humidity_2m_mean": [50.0] * n,
    }
    if wind_mean is not None:
        d["wind_speed_10m_mean"] = [wind_mean] * n
    if wind_max is not None:
        d["wind_speed_10m_max"] = [wind_max] * n
    return {"daily": d, "elevation": 1000}


def _patch_fetch(monkeypatch, payload):
    captured = {}

    def fake_get(url, params=None, timeout=None, **kw):
        captured["url"] = url
        captured["params"] = params or {}
        captured["timeout"] = timeout
        return _FakeResp(payload)

    monkeypatch.setattr("app.climate.requests.get", fake_get)
    return captured


def test_fetch_ms_birimi_ve_mean_alani(monkeypatch):
    """fetch_openmeteo: wind_speed_unit=ms istemeli, 10m mean kullanmalı,
    u2 = mean × 0.75 olmalı (km/h veya max hatası olmamalı)."""
    cap = _patch_fetch(monkeypatch, _fake_daily(wind_mean=2.0, wind_max=5.0))
    c = fetch_openmeteo(37.87, 32.48, 1016)
    assert c is not None
    assert cap["params"].get("wind_speed_unit") == "ms", "API birimi m/s istenmeli"
    assert "wind_speed_10m_mean" in cap["params"].get("daily", ""), "10m mean istenmeli"
    assert cap["timeout"], "ağ zaman aşımı koruması kalmalı"
    # 2.0 m/s × 0.75 = 1.5 — max (5.0×0.75=3.75) veya km/h yorumu (13.5) olmamalı
    assert all(abs(u - 1.5) < 1e-9 for u in c.u2), f"u2 beklenen 1.5 değil: {c.u2}"


def test_fetch_max_fallback(monkeypatch):
    """mean alanı gelmezse günlük maksimuma düşmeli (yine ×0.75)."""
    _patch_fetch(monkeypatch, _fake_daily(wind_max=5.0))
    c = fetch_openmeteo(37.87, 32.48, 1016)
    assert c is not None
    assert all(abs(u - 3.75) < 1e-9 for u in c.u2), f"fallback u2 hatalı: {c.u2}"


# -------------------------- canlı: u2 aralığı + ETo toleransı --------------------------

def test_canli_fetch_u2_araligi_eto_toleransi():
    """Canlı API: u2 aylık 0.1–8 m/s ve yıl ortası 0.3–5 m/s;
    Konya Temmuz ETo 3–9 mm/gün. Eski hata (u2 ~10, ETo ~10.5) bu testi yakalar."""
    try:
        c = fetch_openmeteo(37.87, 32.48, 1016)
    except Exception as e:  # ağ yoksa atla, testi başarısız sayma
        pytest.skip(f"Open-Meteo'ya erişilemedi: {e}")
    if c is None:
        pytest.skip("Open-Meteo yetersiz veri döndürdü")

    assert all(0.1 <= u <= 8.0 for u in c.u2), f"aylık u2 aralığı dışı: {c.u2}"
    yillik = sum(c.u2) / 12
    assert 0.3 <= yillik <= 5.0, f"yıllık ortalama u2 mantıksız: {yillik:.2f} m/s"

    temmuz = monthly_eto(c)[6]
    assert 3.0 <= temmuz <= 9.0, f"Temmuz ETo tolerans dışı: {temmuz:.2f} mm/gün"
