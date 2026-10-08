# -*- coding: utf-8 -*-
"""
İklim verisi: 12 aylık ortalama değerler (manuel düzenlenebilir) ve
Open-Meteo arşiv API'sinden (anahtar gerektirmez) çevrimiçi getirme.
"""
from datetime import date, timedelta

import requests

from .coords import CITIES

# Varsayılan iklim: İç Anadolu platosu (Konya civarı) temsili
DEFAULT_CLIMATE = {
    "tmax": [5, 7, 12, 17, 22, 27, 31, 31, 27, 20, 12, 6],
    "tmin": [-3, -2, 1, 5, 9, 13, 16, 15, 11, 6, 1, -2],
    "rh":   [75, 72, 65, 58, 52, 45, 38, 38, 45, 58, 68, 75],
    "u2":   [2.5, 2.8, 2.8, 2.5, 2.2, 2.2, 2.5, 2.2, 2.0, 2.0, 2.2, 2.5],
    "n":    [4, 5, 6, 7, 9, 11, 12, 11, 9, 7, 5, 4],
    "p":    [35, 30, 35, 40, 35, 25, 8, 5, 10, 30, 35, 45],
}

# Bölgesel iklim ön tanımları (offline kullanım için yaklaşık değerler)
REGIONAL_CLIMATE = {
    "Akdeniz (Antalya)": {
        "tmax": [15, 16, 19, 22, 26, 31, 34, 34, 32, 28, 21, 16],
        "tmin": [6, 6, 8, 11, 15, 19, 22, 22, 19, 15, 10, 7],
        "rh":   [68, 66, 64, 64, 64, 58, 56, 58, 58, 62, 68, 68],
        "u2":   [1.8, 2.0, 2.0, 1.8, 1.6, 1.5, 1.5, 1.5, 1.5, 1.6, 1.7, 1.8],
        "n":    [5, 6, 7, 8, 10, 12, 12, 11, 9, 8, 6, 5],
        "p":    [230, 130, 80, 45, 30, 8, 3, 3, 15, 70, 120, 200],
    },
    "Ege (İzmir)": {
        "tmax": [12, 14, 17, 21, 26, 31, 34, 33, 30, 25, 18, 13],
        "tmin": [4, 5, 7, 10, 14, 18, 21, 21, 17, 13, 8, 5],
        "rh":   [74, 72, 70, 66, 62, 54, 50, 52, 56, 64, 72, 74],
        "u2":   [2.2, 2.3, 2.2, 2.0, 1.8, 1.8, 2.0, 2.0, 1.9, 1.9, 2.0, 2.2],
        "n":    [5, 6, 7, 8, 10, 12, 12, 11, 10, 8, 6, 4],
        "p":    [120, 100, 75, 45, 30, 10, 3, 3, 15, 40, 90, 120],
    },
    "Karadeniz (Trabzon)": {
        "tmax": [11, 11, 13, 16, 19, 23, 26, 27, 24, 20, 16, 13],
        "tmin": [4, 4, 5, 8, 12, 16, 19, 19, 16, 13, 9, 6],
        "rh":   [73, 74, 76, 78, 78, 74, 72, 73, 74, 74, 74, 73],
        "u2":   [2.0, 2.0, 1.8, 1.6, 1.4, 1.4, 1.5, 1.5, 1.5, 1.6, 1.8, 2.0],
        "n":    [3, 3, 4, 5, 6, 7, 6, 6, 5, 4, 3, 2],
        "p":    [90, 70, 70, 60, 55, 50, 40, 55, 85, 120, 110, 95],
    },
    "GAP (Şanlıurfa)": {
        "tmax": [10, 13, 17, 23, 29, 35, 39, 38, 34, 27, 18, 12],
        "tmin": [2, 3, 6, 11, 16, 21, 24, 24, 20, 14, 7, 3],
        "rh":   [72, 68, 62, 55, 46, 35, 32, 34, 40, 52, 65, 72],
        "u2":   [2.0, 2.2, 2.3, 2.2, 2.3, 2.6, 2.8, 2.5, 2.2, 1.9, 1.8, 1.9],
        "n":    [5, 6, 7, 8, 10, 12, 12, 11, 10, 8, 6, 5],
        "p":    [65, 60, 55, 45, 30, 5, 0, 0, 3, 25, 40, 60],
    },
    "Doğu Anadolu (Erzurum)": {
        "tmax": [-3, -1, 4, 12, 18, 23, 28, 29, 24, 16, 7, 0],
        "tmin": [-15, -13, -7, 0, 5, 8, 12, 12, 7, 1, -6, -12],
        "rh":   [78, 76, 72, 62, 55, 50, 48, 48, 52, 64, 73, 78],
        "u2":   [2.2, 2.3, 2.5, 2.5, 2.3, 2.2, 2.2, 2.0, 1.9, 1.9, 2.0, 2.1],
        "n":    [3, 4, 5, 6, 8, 10, 11, 10, 8, 6, 4, 3],
        "p":    [25, 30, 40, 60, 65, 45, 25, 15, 25, 45, 35, 30],
    },
    "Marmara (Bursa)": {
        "tmax": [9, 11, 14, 19, 24, 28, 31, 31, 27, 21, 15, 11],
        "tmin": [1, 2, 4, 8, 12, 16, 18, 18, 14, 10, 5, 2],
        "rh":   [76, 74, 72, 68, 65, 58, 55, 56, 62, 70, 76, 77],
        "u2":   [2.4, 2.5, 2.4, 2.2, 2.0, 2.0, 2.2, 2.2, 2.0, 2.0, 2.2, 2.4],
        "n":    [3, 4, 5, 7, 9, 11, 12, 11, 9, 6, 4, 3],
        "p":    [80, 70, 65, 55, 45, 35, 15, 15, 40, 65, 75, 90],
    },
    "İç Anadolu (Konya)": DEFAULT_CLIMATE,
}

REGIONS = list(REGIONAL_CLIMATE.keys())


class ClimateData:
    """12 aylık iklim verisi taşıyıcısı."""

    def __init__(self, lat=37.87, lon=32.48, alt=1016, ad="Konya"):
        self.ad = ad
        self.lat = lat
        self.lon = lon
        self.alt = alt
        d = dict(DEFAULT_CLIMATE)
        self.tmax = list(d["tmax"])
        self.tmin = list(d["tmin"])
        self.rh = list(d["rh"])
        self.u2 = list(d["u2"])
        self.n = list(d["n"])
        self.p = list(d["p"])

    def load_region(self, region):
        if region in REGIONAL_CLIMATE:
            d = REGIONAL_CLIMATE[region]
            self.tmax = list(d["tmax"])
            self.tmin = list(d["tmin"])
            self.rh = list(d["rh"])
            self.u2 = list(d["u2"])
            self.n = list(d["n"])
            self.p = list(d["p"])

    def set_city(self, city):
        if city in CITIES:
            lat, lon, alt = CITIES[city]
            self.ad = city
            self.lat = lat
            self.lon = lon
            self.alt = alt

    def annual_precip(self):
        return sum(self.p)

    def to_dict(self):
        return {"ad": self.ad, "lat": self.lat, "lon": self.lon, "alt": self.alt,
                "tmax": self.tmax, "tmin": self.tmin, "rh": self.rh,
                "u2": self.u2, "n": self.n, "p": self.p}

    @classmethod
    def from_dict(cls, d):
        c = cls()
        c.ad = d.get("ad", "")
        c.lat = float(d.get("lat", 37.87))
        c.lon = float(d.get("lon", 32.48))
        c.alt = float(d.get("alt", 1016))
        for k in ("tmax", "tmin", "rh", "u2", "n", "p"):
            v = d.get(k)
            if isinstance(v, list) and len(v) == 12:
                setattr(c, k, [float(x) for x in v])
        return c


def fetch_openmeteo(lat, lon, alt=None):
    """
    Open-Meteo arşiv API'sinden son 12 aylık veriyi çeker ve aylık ortalamaya
    çevirir. Başarısız olursa None döner.

    Rüzgâr: 10m ortalama hız m/s olarak istenir ve FAO-56 profil faktörüyle
    2m'ye indirgenir (u2 = u10 × 0.75). Not: API'nin varsayılan birimi km/h
    olduğundan wind_speed_unit=ms açıkça istenir.
    """
    today = date.today()
    start = today - timedelta(days=365)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": today.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "wind_speed_10m_mean,wind_speed_10m_max,sunshine_duration,"
                 "relative_humidity_2m_mean",
        "timezone": "auto",
        "wind_speed_unit": "ms",
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    j = r.json()
    daily = j.get("daily", {})
    dates = daily.get("time", [])
    if len(dates) < 30:
        return None
    if alt is None:
        alt = j.get("elevation", 0) or 0

    acc = {m: {"tmax": [], "tmin": [], "p": [], "u2": [], "n": [], "rh": []} for m in range(12)}
    for i, ds in enumerate(dates):
        d = date.fromisoformat(ds)
        m = d.month - 1
        try:
            tmx = daily["temperature_2m_max"][i]
            tmn = daily["temperature_2m_min"][i]
            pr = daily["precipitation_sum"][i]
            # 10m ortalama rüzgâr (m/s); yoksa maksimuma düş
            wmean = daily.get("wind_speed_10m_mean") or []
            wd = wmean[i] if i < len(wmean) else None
            if wd is None:
                wmax = daily.get("wind_speed_10m_max") or []
                wd = wmax[i] if i < len(wmax) else None
            sd = daily["sunshine_duration"][i]
            rh = daily["relative_humidity_2m_mean"][i]
        except (IndexError, TypeError, KeyError):
            continue
        if tmx is None or tmn is None:
            continue
        acc[m]["tmax"].append(tmx)
        acc[m]["tmin"].append(tmn)
        acc[m]["p"].append(pr or 0.0)
        # 10m -> 2m: FAO-56 rüzgâr profili, 4.87/ln(67.8·10 − 5.42) ≈ 0.75
        acc[m]["u2"].append((wd or 0.0) * 0.75)
        acc[m]["n"].append((sd or 0.0) / 3600.0)
        acc[m]["rh"].append(rh if rh is not None else 60.0)

    c = ClimateData(lat=lat, lon=lon, alt=float(alt), ad="Çevrimiçi İklim")
    for k in ("tmax", "tmin", "rh", "u2", "n"):
        arr = []
        for m in range(12):
            vals = [v for v in acc[m][k] if v is not None]
            arr.append(round(sum(vals) / len(vals), 2) if vals else DEFAULT_CLIMATE[k][m])
        setattr(c, k, arr)
    c.p = [round(sum(acc[m]["p"]), 1) for m in range(12)]
    return c
