# -*- coding: utf-8 -*-
"""
Koordinat dönüşümleri.

- WGS84 (enlem/boylam) <-> TM (Transverse Mercator) Gauss-Krüger serisi (n=3)
  GRS80 elipsoidi üzerinde; Türkiye 3°'lik TM dilimleri (27..45) için k0 = 1.0,
  UTM tarzı 6°'lik dilimler için k0 = 0.9996.
- pyproj kurulu ise daha yüksek hassasiyet için kullanılır (isteğe bağlı).
- Derece/dakika/saniye yardımcıları ve mesafe/alan hesabı.
"""
import math

try:
    import pyproj  # isteğe bağlı
    _HAS_PYPROJ = True
except Exception:
    _HAS_PYPROJ = False

# GRS80 / WGS84 elipsoidi
A = 6378137.0
F = 1.0 / 298.257222101
E2 = F * (2.0 - F)
E4 = E2 * E2
E6 = E4 * E2
EP2 = E2 / (1.0 - E2)   # ikinci eksantriklik karesi (e'²)

TM3_ZONES = [27, 30, 33, 36, 39, 42, 45]

# Türkiye'de yaygın il merkezleri (WGS84) — hızlı konum seçimi için
CITIES = {
    "Adana": (37.0000, 35.3213, 30),
    "Adıyaman": (37.7648, 38.2786, 700),
    "Afyonkarahisar": (38.7507, 30.5567, 1010),
    "Ağrı": (39.7191, 43.0503, 1640),
    "Amasya": (40.6499, 35.8353, 410),
    "Ankara": (39.9334, 32.8597, 890),
    "Antalya": (36.8969, 30.7133, 40),
    "Aydın": (37.8560, 27.8416, 65),
    "Balıkesir": (39.6484, 27.8826, 140),
    "Bursa": (40.1885, 29.0610, 100),
    "Çanakkale": (40.1553, 26.4142, 10),
    "Denizli": (37.7765, 29.0864, 425),
    "Diyarbakır": (37.9144, 40.2306, 675),
    "Edirne": (41.6818, 26.5623, 42),
    "Elazığ": (38.6810, 39.2264, 1060),
    "Erzurum": (39.9000, 41.2700, 1750),
    "Eskişehir": (39.7767, 30.5206, 790),
    "Gaziantep": (37.0662, 37.3833, 850),
    "Giresun": (40.9128, 38.3895, 10),
    "Gümüşhane": (40.4386, 39.5089, 1210),
    "Hatay": (36.4018, 36.3498, 100),
    "Isparta": (37.7648, 30.5566, 1050),
    "İzmir": (38.4192, 27.1287, 25),
    "Kahramanmaraş": (37.5858, 36.9371, 570),
    "Kayseri": (38.7312, 35.4787, 1050),
    "Kırklareli": (41.7333, 27.2167, 230),
    "Kocaeli": (40.8533, 29.8815, 5),
    "Konya": (37.8667, 32.4833, 1016),
    "Kütahya": (39.4167, 29.9833, 940),
    "Malatya": (38.3552, 38.3095, 950),
    "Manisa": (38.6191, 27.4289, 71),
    "Mardin": (37.3212, 40.7245, 1080),
    "Mersin": (36.8000, 34.6333, 10),
    "Muğla": (37.2153, 28.3636, 660),
    "Muş": (38.9462, 41.7539, 1400),
    "Nevşehir": (38.6939, 34.6857, 1220),
    "Niğde": (37.9667, 34.6833, 1220),
    "Ordu": (40.9839, 37.8764, 10),
    "Osmaniye": (37.0742, 36.2478, 90),
    "Rize": (41.0201, 40.5234, 10),
    "Sakarya": (40.7569, 30.3783, 30),
    "Samsun": (41.2928, 36.3313, 10),
    "Şanlıurfa": (37.1591, 38.7969, 550),
    "Siirt": (37.9333, 41.9500, 900),
    "Sinop": (42.0231, 35.1531, 30),
    "Sivas": (39.7477, 37.0179, 1280),
    "Tekirdağ": (40.9781, 27.5085, 20),
    "Tokat": (40.3167, 36.5500, 620),
    "Trabzon": (41.0015, 39.7178, 30),
    "Uşak": (38.6823, 29.4082, 910),
    "Van": (38.4891, 43.4089, 1730),
    "Yozgat": (39.8200, 34.8083, 1300),
    "Zonguldak": (41.4564, 31.7987, 10),
}


# Türkiye'nin 81 ili (alfabetik) — parsel filtreleri ve açılır listeler için
ILLER = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya",
    "Ankara", "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir",
    "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
    "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari",
    "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir", "Kahramanmaraş",
    "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya",
    "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya",
    "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak",
    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van",
    "Yalova", "Yozgat", "Zonguldak",
]


def has_pyproj():
    return _HAS_PYPROJ


def tm_zone_for_lon(lon, width3=True):
    if width3:
        z = int(round((lon - 1.5) / 3.0)) * 3
        return max(27, min(45, z))
    return int((lon + 180) // 6) + 1  # UTM benzeri 6°


def _meridian_arc(phi):
    """Ekvator'dan phi enlemine meridyen yayı (m) — Snyder eş. 3-21."""
    return A * ((1 - E2 / 4 - 3 * E4 / 64 - 5 * E6 / 256) * phi
                - (3 * E2 / 8 + 3 * E4 / 32 + 45 * E6 / 1024) * math.sin(2 * phi)
                + (15 * E4 / 256 + 45 * E6 / 1024) * math.sin(4 * phi)
                - (35 * E6 / 3072) * math.sin(6 * phi))


def _zone_geometry(zone, tm3):
    if tm3:
        return float(zone), 1.0
    return (zone - 1) * 6 - 180 + 3, 0.9996


def lonlat_to_tm(lon, lat, zone=None, tm3=True):
    """WGS84 -> TM (X, Y) — Snyder klasik TM serisi (cm hassasiyetinde).
    tm3=True: zone=3° dilim meridyeni (27..45), k0=1.0
    tm3=False: zone=UTM dilim no (6°), k0=0.9996"""
    if zone is None:
        zone = tm_zone_for_lon(lon, width3=tm3)
    lon0, k0 = _zone_geometry(zone, tm3)
    phi = math.radians(lat)
    lam = math.radians(lon - lon0)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    N = A / math.sqrt(1 - E2 * sin_phi * sin_phi)
    T = math.tan(phi) ** 2
    C = EP2 * cos_phi * cos_phi
    Aa = lam * cos_phi
    M = _meridian_arc(phi)
    x = k0 * N * (Aa + (1 - T + C) * Aa ** 3 / 6.0
                  + (5 - 18 * T + T * T + 72 * C - 58 * EP2) * Aa ** 5 / 120.0) + 500000.0
    y = k0 * (M + N * math.tan(phi) * (
        Aa ** 2 / 2.0
        + (5 - T + 9 * C + 4 * C * C) * Aa ** 4 / 24.0
        + (61 - 58 * T + T * T + 600 * C - 330 * EP2) * Aa ** 6 / 720.0))
    return x, y


def tm_to_lonlat(x, y, zone, tm3=True):
    """TM -> WGS84 — Snyder klasik TM serisi."""
    lon0, k0 = _zone_geometry(zone, tm3)
    xp = (x - 500000.0) / k0
    yp = y / k0
    mu = yp / (A * (1 - E2 / 4 - 3 * E4 / 64 - 5 * E6 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    e1_2, e1_3, e1_4 = e1 ** 2, e1 ** 3, e1 ** 4
    phi1 = (mu + (3 * e1 / 2 - 27 * e1_3 / 32) * math.sin(2 * mu)
            + (21 * e1_2 / 16 - 55 * e1_4 / 32) * math.sin(4 * mu)
            + (151 * e1_3 / 96) * math.sin(6 * mu)
            + (1097 * e1_4 / 512) * math.sin(8 * mu))
    sin1 = math.sin(phi1)
    cos1 = math.cos(phi1)
    tan1 = math.tan(phi1)
    N1 = A / math.sqrt(1 - E2 * sin1 * sin1)
    T1 = tan1 * tan1
    C1 = EP2 * cos1 * cos1
    R1 = A * (1 - E2) / (1 - E2 * sin1 * sin1) ** 1.5
    D = xp / N1
    phi = phi1 - (N1 * tan1 / R1) * (
        D ** 2 / 2.0
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * EP2) * D ** 4 / 24.0
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * EP2 - 3 * C1 * C1) * D ** 6 / 720.0)
    lam = (D - (1 + 2 * T1 + C1) * D ** 3 / 6.0
           + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * EP2 + 24 * T1 * T1) * D ** 5 / 120.0) / cos1
    return math.degrees(lam) + lon0, math.degrees(phi)


def pyproj_tm_to_lonlat(x, y, zone, tm3=True):
    """pyproj varsa daha hassas dönüşüm."""
    if not _HAS_PYPROJ:
        return None
    try:
        if tm3:
            crs = pyproj.CRS.from_proj4(f"+proj=tmerc +lat_0=0 +lon_0={zone} +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs")
        else:
            crs = pyproj.CRS.from_proj4(f"+proj=utm +zone={zone} +ellps=GRS80 +units=m +no_defs")
        t = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        lon, lat = t.transform(x, y)
        return lon, lat
    except Exception:
        return None


def pyproj_lonlat_to_tm(lon, lat, zone, tm3=True):
    if not _HAS_PYPROJ:
        return None
    try:
        if tm3:
            crs = pyproj.CRS.from_proj4(f"+proj=tmerc +lat_0=0 +lon_0={zone} +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs")
        else:
            crs = pyproj.CRS.from_proj4(f"+proj=utm +zone={zone} +ellps=GRS80 +units=m +no_defs")
        t = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = t.transform(lon, lat)
        return x, y
    except Exception:
        return None


def dms_to_decimal(deg, minutes, seconds, hemi=""):
    v = abs(deg) + minutes / 60.0 + seconds / 3600.0
    if deg < 0 or hemi.upper() in ("S", "W", "G", "B"):
        v = -v
    return v


def decimal_to_dms(value):
    h = "K" if value >= 0 else "G"
    v = abs(value)
    d = int(v)
    m_float = (v - d) * 60
    m = int(m_float)
    s = (m_float - m) * 60
    return d, m, s, h


def haversine(lon1, lat1, lon2, lat2):
    """İki nokta arası mesafe (m) — küresel yaklaşım."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_city(lat, lon, max_km=150.0):
    """Verilen noktaya en yakın il merkezini ve uzaklığını (km) döner.
    max_km içinde şehir yoksa (None, None) döner."""
    best, best_d = None, None
    for city, (clat, clon, _alt) in CITIES.items():
        d = haversine(lon, lat, clon, clat) / 1000.0
        if best is None or d < best_d:
            best, best_d = city, d
    if best is not None and best_d <= max_km:
        return best, best_d
    return None, None


def polygon_area_m2(coords):
    """Çokgen alanı (m²) — TM(30) projeksiyonunda Gauss alan formülü."""
    if len(coords) < 3:
        return 0.0
    pts = [lonlat_to_tm(lon, lat) for lon, lat in coords]
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def format_area(m2):
    if m2 >= 10000:
        return f"{m2 / 10000:.2f} ha"
    if m2 >= 1000:
        return f"{m2 / 1000:.2f} da ({m2:,.0f} m²)"
    return f"{m2:,.0f} m²"
