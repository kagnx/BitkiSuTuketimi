# -*- coding: utf-8 -*-
"""
Harita widget'ı.

- OpenStreetMap XYZ tile tabanlı Web Mercator harita (QNetworkAccessManager + önbellek)
- Çevrimdışı durumda enlem/boylam ızgarası çizimi
- İşaretçi, parsel çokgeni, mesafe/alan ölçümü
- Ada/Parsel ile arama ve vurgulama
- WGS84 ve TM koordinat girişi
"""
import json
import math
import os
import tempfile

from PyQt6.QtCore import (Qt, QRectF, QPointF, QUrl, pyqtSignal)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QPixmap,
                         QPolygonF, QFont, QFontMetrics, QPixmapCache, QPainterPath)
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem,
                             QGraphicsPolygonItem, QGraphicsEllipseItem,
                             QGraphicsSimpleTextItem, QGraphicsPathItem,
                             QInputDialog)


from .coords import (lonlat_to_tm, tm_to_lonlat, haversine, polygon_area_m2,
                     format_area, tm_zone_for_lon, nearest_city)
from .dialogs import ParcelSaveDialog
from .theme import PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, BG_DARK, DANGER, TEXT_DARK

MIN_Z = 3
MAX_Z = 18
TILE = 256
UA = "ProSU-Tarimsu/1.0 (tarimsal su yonetimi masaustu uygulamasi)"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "prosu_tiles")

# Harita katmanları (uydu + etiketli görünümler)
TILE_SOURCES = {
    "Google Uydu + Etiket": {
        "key": "g_hyb",
        "url": "https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}",
    },
    "Google Uydu": {
        "key": "g_sat",
        "url": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    },
    "OpenStreetMap (Etiketli)": {
        "key": "osm",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    },
    "Esri Uydu": {
        "key": "esri",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    },
}
DEFAULT_TILE_SOURCE = "Google Uydu + Etiket"

# Türkiye sınırları (WGS84)
TURKIYE_BOUNDS = (25.6, 35.8, 44.9, 42.2)  # lon_min, lat_min, lon_max, lat_max


def _parse_tile_url(url_str):
    """İndirilen tile isteğinin URL'sinden (z, x, y) çıkarır — katman URL'leri
    birbirinden farklı olduğundan (Google sorgu parametreli, Esri z/y/x yollu,
    OSM z/x/y yollu) her biri ayrı ayrı çözülür."""
    from urllib.parse import parse_qs
    if "/vt/lyrs" in url_str:  # Google: .../vt/lyrs=s,h&x=..&y=..&z=.. (sorgu işareti yok)
        q = parse_qs(url_str.split("/vt/", 1)[1].split("?")[0])
        return int(q["z"][0]), int(q["x"][0]), int(q["y"][0])
    parts = [p for p in url_str.split("/") if p]
    if "arcgisonline.com" in url_str:  # Esri: .../tile/{z}/{y}/{x}
        return int(parts[-3]), int(parts[-1].split("?")[0]), int(parts[-2])
    # OSM: .../{z}/{x}/{y}.png
    return int(parts[-3]), int(parts[-2]), int(parts[-1].split("?")[0].split(".")[0])


def lonlat_to_pixel(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n * TILE
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n * TILE
    return x, y


def pixel_to_lonlat(x, y, z):
    n = 2 ** z
    lon = x / TILE / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / TILE / n))))
    return lon, lat


def tile_xy(lon, lat, z):
    x, y = lonlat_to_pixel(lon, lat, z)
    return int(x // TILE), int(y // TILE)


def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


class ParcelItem(QGraphicsPolygonItem):
    """Parsel çokgeni + etiket."""

    def __init__(self, parcel, color=PRIMARY, highlighted=False):
        super().__init__()
        self.parcel = parcel
        self._color = QColor(color)
        self._hl = highlighted
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip(self.label_text())

    def label_text(self):
        p = self.parcel
        base = f"Ada: {p['ada']}  Parsel: {p['parsel']}"
        if p.get("mahalle"):
            base += f"  ({p['mahalle']})"
        if p.get("alan_m2"):
            base += f"\nAlan: {format_area(p['alan_m2'])}"
        return base

    def paint(self, painter, option, widget=None):
        if self.isSelected() or self._hl:
            c = QColor("#2E7D32")
        else:
            c = self._color
        painter.setPen(QPen(c, 2.0))
        fill = QColor(c)
        fill.setAlpha(70 if not self._hl else 130)
        painter.setBrush(QBrush(fill))
        painter.drawPolygon(self.polygon())
        # etiket
        p = self.parcel
        r = self.boundingRect()
        cx = r.center().x()
        cy = r.center().y()
        if self._hl:
            # odak görünümü: parselin üzerinde büyük ve kalıcı etiket (ada/parsel + alan)
            lbl1 = f"Ada {p['ada']} / Parsel {p['parsel']}"
            alan = p.get("alan_m2")
            lbl2 = format_area(alan) if alan else "Alan yok"
            f = QFont(painter.font())
            f.setPixelSize(17)
            f.setBold(True)
            painter.setFont(f)
            fm = QFontMetrics(f)
            w = max(fm.horizontalAdvance(lbl1), fm.horizontalAdvance(lbl2)) + 28
            h = fm.height() * 2 + 22
            rect = QRectF(cx - w / 2, cy - h / 2, w, h)
            painter.setPen(QPen(QColor("#1B5E20"), 3))
            painter.setBrush(QBrush(QColor(0, 34, 12, 200)))
            painter.drawRoundedRect(rect, 12, 12)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRectF(rect.x() + 4, cy - fm.height() - 2, w - 8, fm.height()),
                             Qt.AlignmentFlag.AlignCenter, lbl1)
            painter.setPen(QColor("#AED581"))
            painter.drawText(QRectF(rect.x() + 4, cy + 2, w - 8, fm.height()),
                             Qt.AlignmentFlag.AlignCenter, lbl2)
        else:
            lbl = f"{p['ada']}/{p['parsel']}"
            fm = QFontMetrics(painter.font())
            w = fm.horizontalAdvance(lbl) + 8
            h = fm.height() + 6
            painter.setPen(QPen(QColor("#FFFFFF"), 1.0))
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
            painter.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QPointF(cx - w / 2 + 4, cy + fm.ascent() / 2 - 2), lbl)


class MarkerItem(QGraphicsEllipseItem):
    def __init__(self, lon, lat, label, color=DANGER):
        super().__init__(-8, -8, 16, 16)
        self.lon = lon
        self.lat = lat
        self.label = label
        self._color = QColor(color)
        self.setPen(QPen(QColor("#FFFFFF"), 2.0))
        self.setBrush(QBrush(self._color))
        self.setToolTip(f"{label}\n{lat:.6f}, {lon:.6f}")

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(QPen(QColor("#333333"), 1.0))
        fm = QFontMetrics(painter.font())
        painter.drawText(QPointF(10, fm.ascent() + 2), self.label)


class TileLayer(QGraphicsItem):
    def __init__(self, view, z):
        super().__init__()
        self.view = view
        self.z = z
        self._pending = set()
        self.setZValue(-10)

    def boundingRect(self):
        n = 2 ** self.z * TILE
        return QRectF(0, 0, n, n)

    def paint(self, painter, option, widget=None):
        z = self.z
        # görünür alan: viewport tabanlı (paint sırasında exposed dev olabilir)
        view = self.view
        exposed = option.exposedRect
        try:
            vp = view.mapToScene(view.viewport().rect()).boundingRect()
            if not vp.isNull():
                exposed = exposed.intersected(vp)
        except Exception:
            pass
        if exposed.isNull():
            return

        x0 = max(0, int(exposed.left() // TILE))
        x1 = min(2 ** z - 1, int(exposed.right() // TILE))
        y0 = max(0, int(exposed.top() // TILE))
        y1 = min(2 ** z - 1, int(exposed.bottom() // TILE))
        if x1 - x0 > 300 or y1 - y0 > 300:
            return  # güvenlik: mantıksız büyüklükte alan çizme

        # zemin
        painter.fillRect(exposed, QColor("#E8EFE2"))
        self._draw_grid(painter, exposed)

        if view.online:
            tkey = view.tile_key
            want = []
            for tx in range(x0, x1 + 1):
                for ty in range(y0, y1 + 1):
                    try:
                        key = f"{tkey}_{z}_{tx}_{ty}"
                        pm = QPixmapCache.find(key)  # PyQt6: (str) -> QPixmap
                        if pm is not None and not pm.isNull():
                            painter.drawPixmap(tx * TILE, ty * TILE, pm)
                        else:
                            want.append((tx, ty))
                            # placeholder
                            painter.fillRect(QRectF(tx * TILE, ty * TILE, TILE, TILE), QColor("#DCE7D2"))
                            painter.setPen(QPen(QColor("#A9BF94"), 1))
                            painter.drawRect(tx * TILE, ty * TILE, TILE, TILE)
                    except Exception:
                        want.append((tx, ty))
            if len(want) > 256:
                want = want[:256]  # çerçeve başına istek sınırı
            view.request_tiles(z, want)

    def _draw_grid(self, painter, exposed):
        """Enlem/boylam ızgarası (çevrimdışı ve tile üstü hafif)."""
        painter.save()
        pen = QPen(QColor(70, 90, 60, 120), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        font = painter.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        painter.setFont(font)

        lon0, lat1 = pixel_to_lonlat(exposed.left(), exposed.top(), self.z)
        lon1, lat0 = pixel_to_lonlat(exposed.right(), exposed.bottom(), self.z)
        step = self._grid_step(lon1 - lon0, lat1 - lat0)
        # dikey çizgiler
        lo = math.floor(lon0 / step) * step
        while lo <= lon1:
            x, _ = lonlat_to_pixel(lo, (lat0 + lat1) / 2, self.z)
            painter.drawLine(QPointF(x, exposed.top()), QPointF(x, exposed.bottom()))
            txt = f"{lo:.2f}°"
            painter.setPen(QColor("#33452B"))
            painter.drawText(QPointF(x + 3, exposed.top() + 12), txt)
            painter.setPen(pen)
            lo += step
        la = math.floor(lat0 / step) * step
        while la <= lat1:
            _, y = lonlat_to_pixel((lon0 + lon1) / 2, la, self.z)
            painter.drawLine(QPointF(exposed.left(), y), QPointF(exposed.right(), y))
            txt = f"{la:.2f}°"
            painter.setPen(QColor("#33452B"))
            painter.drawText(QPointF(exposed.left() + 3, y - 3), txt)
            painter.setPen(pen)
            la += step
        painter.restore()

    @staticmethod
    def _grid_step(dlon, dlat):
        span = max(dlon, dlat)
        for s in (10.0, 5.0, 2.0, 1.0, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01, 0.005):
            if span / s <= 4.0:
                return s
        return 0.005


class MapCanvas(QGraphicsView):
    status_message = pyqtSignal(str)
    parcel_drawn = pyqtSignal(object)   # dict(ada, parsel, coords, area)
    coordinate_picked = pyqtSignal(float, float)  # lon, lat (haritadan seçim)
    parcel_selected = pyqtSignal(object)  # parsel dict (haritada parsele tıklama)
    zoom_changed = pyqtSignal(int)      # aktif zoom seviyesi (tekerlek / buton)

    MODE_PAN = "pan"
    MODE_MARK = "mark"
    MODE_PICK = "pick"      # tek tıkla koordinat seç
    MODE_DRAW = "draw"
    MODE_RECT = "rect"      # tam 4 köşe ile parsel
    MODE_MEASURE = "measure"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.online = True
        self.zoom = 11
        self.center_lonlat = (32.48, 37.87)
        self.mode = self.MODE_PAN

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # Devasa scene rect'i nedeniyle QGraphicsView cok buyuk bir minimum boyut
        # dayatir (tam ekranda duzeni bozuyor); makul bir minimum ile kisitla.
        self.setMinimumSize(320, 240)

        self.tile_layer = TileLayer(self, self.zoom)
        self.scene.addItem(self.tile_layer)
        self.setSceneRect(QRectF(0, 0, 2 ** self.zoom * TILE, 2 ** self.zoom * TILE))

        self._net = QNetworkAccessManager(self)
        self._net.finished.connect(self._tile_received)
        self._pending = set()
        self._highlight_id = None

        self.tile_source = DEFAULT_TILE_SOURCE
        self.tile_key = TILE_SOURCES[self.tile_source]["key"]
        self.tile_url = TILE_SOURCES[self.tile_source]["url"]

        self._markers = []
        self._parcels = []
        self._draw_pts = []
        self._measure_pts = []
        self._item_refs = []

        self.setMouseTracking(True)
        self.apply_transform()

    # ------------------------------------------------------------------
    # görünüm yönetimi
    # ------------------------------------------------------------------
    def apply_transform(self):
        self.setSceneRect(QRectF(0, 0, 2 ** self.zoom * TILE, 2 ** self.zoom * TILE))
        self.tile_layer.z = self.zoom
        self.tile_layer.setZValue(-10)
        self.tile_layer.prepareGeometryChange()
        self.resetTransform()
        x, y = lonlat_to_pixel(*self.center_lonlat, self.zoom)
        self.centerOn(x, y)
        self.refresh_items()
        self.tile_layer.update()
        self.status_message.emit(self._pos_text())
        self.zoom_changed.emit(self.zoom)

    def set_center(self, lon, lat, zoom=None):
        if zoom is not None:
            self.zoom = max(MIN_Z, min(MAX_Z, zoom))
        self.center_lonlat = (lon, lat)
        self.apply_transform()

    def set_tile_source(self, name):
        """Harita katmanını değiştirir (Google uydu, OSM, Esri uydu vb.)."""
        src = TILE_SOURCES.get(name)
        if not src:
            return
        self.tile_source = name
        self.tile_key = src["key"]
        self.tile_url = src["url"]
        self.tile_layer.update()
        self.status_message.emit(f"Harita katmanı: {name}")

    def zoom_in(self):
        if self.zoom < MAX_Z:
            self.zoom += 1
            self.apply_transform()

    def zoom_out(self):
        if self.zoom > MIN_Z:
            self.zoom -= 1
            self.apply_transform()

    def fit_bounds(self, lon_min, lat_min, lon_max, lat_max, margin=0.06):
        """Verilen coğrafi sınırları görünüme sığdırır (otomatik zoom + merkez)."""
        vw = max(100, self.viewport().width())
        vh = max(100, self.viewport().height())
        best = MIN_Z
        for z in range(MAX_Z, MIN_Z - 1, -1):
            x0, y0 = lonlat_to_pixel(lon_min, lat_max, z)
            x1, y1 = lonlat_to_pixel(lon_max, lat_min, z)
            w, h = x1 - x0, y0 - y1
            if w * (1 + margin) <= vw and h * (1 + margin) <= vh:
                best = z
                break
        self.zoom = best
        self.center_lonlat = ((lon_min + lon_max) / 2, (lat_min + lat_max) / 2)
        self.apply_transform()

    def fit_turkiye(self):
        """Tüm Türkiye'yi haritada gösterir."""
        self.fit_bounds(*TURKIYE_BOUNDS)

    def set_online(self, on):
        self.online = on
        self.tile_layer.update()

    def _pos_text(self):
        lon, lat = self.center_lonlat
        try:
            z = tm_zone_for_lon(lon, width3=True)
            x, y = lonlat_to_tm(lon, lat, zone=z)
            tm = f"TM{z}: X={x:,.1f} Y={y:,.1f}"
        except Exception:
            tm = ""
        return f"Merkez: {lat:.5f}°K, {lon:.5f}°D   |   Zoom: {self.zoom}   |   {tm}"

    # ------------------------------------------------------------------
    # tile indirme
    # ------------------------------------------------------------------
    def request_tiles(self, z, tiles):
        for tx, ty in tiles:
            key = (z, tx, ty)
            if key in self._pending:
                continue
            self._pending.add(key)
            url = QUrl(self.tile_url.format(z=z, x=tx, y=ty))
            req = QNetworkRequest(url)
            req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, UA)
            self._net.get(req)

    def _tile_received(self, reply):
        key = None
        try:
            tz, tx, ty = _parse_tile_url(reply.url().toString())
            key = (tz, tx, ty)
            data = bytes(reply.readAll())
            if reply.error() == reply.NetworkError.NoError and data:
                _ensure_cache()
                path = os.path.join(CACHE_DIR, self.tile_key, str(tz), str(tx), f"{ty}.png")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                if tz == self.zoom:
                    pm = QPixmap()
                    pm.loadFromData(data)
                    QPixmapCache.insert(f"{self.tile_key}_{tz}_{tx}_{ty}", pm)
                    self.tile_layer.update()
        except Exception:
            pass
        finally:
            if key is not None and key in self._pending:
                self._pending.discard(key)
            reply.deleteLater()

    # ------------------------------------------------------------------
    # veri katmanları
    # ------------------------------------------------------------------
    def set_markers(self, markers):
        self._markers = markers
        self.refresh_items()

    def add_marker(self, lon, lat, label, color=DANGER):
        self._markers.append({"lon": lon, "lat": lat, "label": label, "color": color})
        self.refresh_items()

    def clear_markers(self):
        self._markers = []
        self.refresh_items()

    def set_parcels(self, parcels, highlight_id=None):
        self._parcels = parcels
        self._highlight_id = highlight_id
        self.refresh_items()

    def refresh_items(self):
        for it in self._item_refs:
            self.scene.removeItem(it)
        self._item_refs = []

        # işaretçiler
        for m in self._markers:
            x, y = lonlat_to_pixel(m["lon"], m["lat"], self.zoom)
            item = MarkerItem(m["lon"], m["lat"], m["label"], m.get("color", DANGER))
            item.setPos(x, y)
            self.scene.addItem(item)
            self._item_refs.append(item)

        # parseller
        for p in self._parcels:
            coords = p.get("koordinatlar") or []
            if len(coords) < 3:
                continue
            pts = [QPointF(*lonlat_to_pixel(lo, la, self.zoom)) for lo, la in coords]
            poly = QPolygonF(pts)
            item = ParcelItem(p, highlighted=(getattr(self, "_highlight_id", None) == p.get("id")))
            item.setPolygon(poly)
            self.scene.addItem(item)
            self._item_refs.append(item)

        # çizim noktaları
        for pt in self._draw_pts:
            x, y = lonlat_to_pixel(pt[0], pt[1], self.zoom)
            e = QGraphicsEllipseItem(-5, -5, 10, 10)
            e.setPen(QPen(QColor("#2E7D32"), 2))
            e.setBrush(QBrush(QColor(PRIMARY_LIGHT)))
            e.setPos(x, y)
            self.scene.addItem(e)
            self._item_refs.append(e)
        if len(self._draw_pts) >= 3:
            pts = [QPointF(*lonlat_to_pixel(lo, la, self.zoom)) for lo, la in self._draw_pts]
            preview = QGraphicsPolygonItem(QPolygonF(pts))
            c = QColor(PRIMARY)
            c.setAlpha(50)
            preview.setBrush(QBrush(c))
            preview.setPen(QPen(QColor(PRIMARY_DARK), 1, Qt.PenStyle.DashLine))
            self.scene.addItem(preview)
            self._item_refs.append(preview)

        # ölçüm noktaları
        for i, pt in enumerate(self._measure_pts):
            x, y = lonlat_to_pixel(pt[0], pt[1], self.zoom)
            e = QGraphicsEllipseItem(-5, -5, 10, 10)
            e.setPen(QPen(QColor("#1565C0"), 2))
            e.setBrush(QBrush(QColor("#90CAF9")))
            e.setPos(x, y)
            self.scene.addItem(e)
            self._item_refs.append(e)
            if i > 0:
                p0 = self._measure_pts[i - 1]
                x0, y0 = lonlat_to_pixel(p0[0], p0[1], self.zoom)
                path = QPainterPath(QPointF(x0, y0))
                path.lineTo(QPointF(x, y))
                seg = QGraphicsPathItem(path)
                seg.setPen(QPen(QColor("#1565C0"), 2))
                seg.setBrush(Qt.BrushStyle.NoBrush)
                self.scene.addItem(seg)
                self._item_refs.append(seg)
                d = haversine(p0[0], p0[1], pt[0], pt[1])
                lbl = QGraphicsSimpleTextItem(f"{d:,.0f} m")
                lbl.setBrush(QBrush(QColor("#0D47A1")))
                lbl.setPos((x0 + x) / 2, (y0 + y) / 2)
                self.scene.addItem(lbl)
                self._item_refs.append(lbl)

    def clear_drawing(self):
        self._draw_pts = []
        self._measure_pts = []
        self.refresh_items()

    def set_mode(self, mode):
        self.mode = mode
        cross = mode in (self.MODE_PICK, self.MODE_DRAW, self.MODE_RECT, self.MODE_MEASURE)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == self.MODE_PAN else QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor if cross else Qt.CursorShape.OpenHandCursor)
        if mode not in (self.MODE_DRAW, self.MODE_RECT):
            self._draw_pts = []
        if mode != self.MODE_MEASURE:
            self._measure_pts = []
        self.refresh_items()
        if mode == self.MODE_PICK:
            self.status_message.emit("Koordinat seçimi: haritaya tıklayın — WGS84 ve TM3 değerleri hesaplanır.")
        elif mode == self.MODE_RECT:
            self.status_message.emit("4 köşe parsel: köşelere SIRAYLA 4 kez tıklayın — 4. tıklamada otomatik kaydedilir.")

    # ------------------------------------------------------------------
    # olaylar
    # ------------------------------------------------------------------
    def wheelEvent(self, event):
        """Fare orta tekerleği ile yakınlaştırma/uzaklaştırma.
        Klasik tekerlek (angleDelta) ve dokunmatik yüzey (pixelDelta) desteklenir;
        zoom imlecin altındaki coğrafi nokta sabit kalacak şekilde yapılır."""
        angle = event.angleDelta().y()
        px = event.pixelDelta().y()
        if angle == 0 and px == 0:
            return
        if angle:
            steps = max(1, abs(angle) // 120)
            direction = 1 if angle > 0 else -1
        else:
            steps = max(1, abs(px) // 40)
            direction = 1 if px > 0 else -1
        # imlecin altındaki coğrafi konum (zoom merkezi)
        pos = self.mapToScene(event.position().toPoint())
        lon, lat = pixel_to_lonlat(pos.x(), pos.y(), self.zoom)
        new_z = max(MIN_Z, min(MAX_Z, self.zoom + direction * steps))
        if new_z != self.zoom:
            self.zoom = new_z
            self.center_lonlat = (lon, lat)
            self.apply_transform()
        event.accept()

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        lon, lat = pixel_to_lonlat(pos.x(), pos.y(), self.zoom)
        try:
            z = tm_zone_for_lon(lon, width3=True)
            x, y = lonlat_to_tm(lon, lat, zone=z)
            txt = f"  {lat:.6f}°K  {lon:.6f}°D   |   TM{z}: X {x:,.1f}  Y {y:,.1f}"
        except Exception:
            txt = f"  {lat:.6f}°K  {lon:.6f}°D"
        self.status_message.emit(txt)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Gez (pan) modunda parsele tıklamak parseli seçer (özet/hesaba yansır)
            if self.mode == self.MODE_PAN:
                for it in self.items(event.position().toPoint()):
                    if isinstance(it, ParcelItem):
                        self.parcel_selected.emit(it.parcel)
                        break
            pos = self.mapToScene(event.position().toPoint())
            lon, lat = pixel_to_lonlat(pos.x(), pos.y(), self.zoom)
            if self.mode == self.MODE_MARK:
                label, ok = QInputDialog.getText(self, "İşaretçi", "İşaretçi etiketi:")
                if ok and label.strip():
                    self.add_marker(lon, lat, label.strip())
                return
            if self.mode == self.MODE_PICK:
                self.add_marker(lon, lat, f"Seçim ({lat:.5f}, {lon:.5f})", color="#1565C0")
                self.coordinate_picked.emit(lon, lat)
                return
            if self.mode in (self.MODE_DRAW, self.MODE_RECT):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._finish_draw()
                else:
                    self._draw_pts.append([lon, lat])
                    if self.mode == self.MODE_RECT and len(self._draw_pts) >= 4:
                        self._finish_draw()  # 4. köşe: otomatik tamamla → kayıt penceresi
                    else:
                        self.refresh_items()
                return
            if self.mode == self.MODE_MEASURE:
                self._measure_pts.append([lon, lat])
                if len(self._measure_pts) >= 2:
                    d = haversine(self._measure_pts[0][0], self._measure_pts[0][1], lon, lat)
                    self.status_message.emit(f"Ölçüm: {d:,.1f} m")
                if len(self._measure_pts) >= 3:
                    area = polygon_area_m2(self._measure_pts)
                    self.status_message.emit(f"Ölçüm: alan {format_area(area)}")
                self.refresh_items()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.mode in (self.MODE_DRAW, self.MODE_RECT):
            self._finish_draw()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _finish_draw(self):
        if len(self._draw_pts) < 3:
            return
        pts = [list(p) for p in self._draw_pts]
        area = polygon_area_m2(pts)
        # çizilen alanın ortasındaki en yakın ili öneri olarak ver
        varsayilan_il = ""
        try:
            clat = sum(p[1] for p in pts) / len(pts)
            clon = sum(p[0] for p in pts) / len(pts)
            nc, _km = nearest_city(clat, clon)
            if nc:
                varsayilan_il = nc
        except Exception:
            pass
        dlg = ParcelSaveDialog(self, varsayilan_il=varsayilan_il)
        if dlg.exec():
            ada, parsel, il, ilce, mahalle = dlg.values()
            self.parcel_drawn.emit({"ada": ada, "parsel": parsel,
                                    "il": il, "ilce": ilce, "mahalle": mahalle,
                                    "coords": pts, "area": area})
        self._draw_pts = []
        self.refresh_items()

    # ------------------------------------------------------------------
    # içe/dışa aktarma
    # ------------------------------------------------------------------
    def export_geojson(self, path, parcels):
        feats = []
        for p in parcels:
            coords = p.get("koordinatlar") or []
            if len(coords) < 3:
                continue
            feats.append({
                "type": "Feature",
                "properties": {"ada": p["ada"], "parsel": p["parsel"],
                               "il": p.get("il", ""), "ilce": p.get("ilce", ""),
                               "mahalle": p.get("mahalle", ""),
                               "alan_m2": round(p.get("alan_m2") or 0, 2)},
                "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]},
            })
        gj = {"type": "FeatureCollection", "name": "ProSU_Parseller",
              "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
              "features": feats}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gj, f, ensure_ascii=False, indent=2)
        return len(feats)

    def import_geojson(self, path, crs="WGS84", tm_zone=30):
        """GeoJSON içe aktarır; Polygon/MultiPolygon desteklenir.
        crs 'WGS84' veya 'TM' olabilir. Döndürür: (parseller, hata_msj)"""
        with open(path, "r", encoding="utf-8") as f:
            gj = json.load(f)
        if gj.get("type") != "FeatureCollection":
            return None, "Dosya bir FeatureCollection değil."
        out = []
        for feat in gj.get("features", []):
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            polys = []
            if geom.get("type") == "Polygon":
                # coordinates: her biri bir halka (ring) olan liste
                polys = list(geom.get("coordinates") or [])
            elif geom.get("type") == "MultiPolygon":
                polys = [c[0] for c in (geom.get("coordinates") or [])]
            else:
                continue
            for ring in polys:
                if len(ring) < 4:
                    continue
                coords = []
                for pt in ring[:-1]:
                    xx, yy = pt[0], pt[1]
                    if crs.upper().startswith("TM"):
                        if isinstance(tm_zone, str):
                            tm_zone = int(tm_zone.split()[0])
                        lon, lat = tm_to_lonlat(float(xx), float(yy), tm_zone)
                    else:
                        lon, lat = float(xx), float(yy)
                    coords.append([lon, lat])
                out.append({
                    "ada": str(props.get("ada", props.get("ADA", ""))),
                    "parsel": str(props.get("parsel", props.get("PARSEL", ""))),
                    "il": str(props.get("il", props.get("IL", ""))),
                    "ilce": str(props.get("ilce", props.get("ILCE", ""))),
                    "mahalle": str(props.get("mahalle", props.get("MAHALLE", ""))),
                    "koordinatlar": coords,
                    "alan_m2": round(polygon_area_m2(coords), 2),
                })
        if not out:
            return None, "İçeride çokgen bulunamadı."
        return out, None

    def import_csv(self, path, crs="WGS84", tm_zone=30):
        """CSV içe aktarır. Sütunlar: lon,lat[,ada,parsel] veya x,y[,ada,parsel].
        Ada/Parsel sütunu yoksa satır adı kullanılır."""
        import csv
        parcels = {}
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            cols = [c.strip().lower() for c in reader.fieldnames]
            has_xy = "x" in cols and "y" in cols
            has_lonlat = ("lon" in cols or "longitude" in cols or "boylam" in cols) and \
                         ("lat" in cols or "latitude" in cols or "enlem" in cols)
            if not (has_xy or has_lonlat):
                return None, "CSV'de x/y (TM) veya lon/lat (WGS84) sütunları bulunamadı."
            for row in reader:
                try:
                    if has_xy:
                        xx, yy = float(row["x"]), float(row["y"])
                        if crs.upper().startswith("TM"):
                            zz = int(tm_zone.split()[0]) if isinstance(tm_zone, str) else tm_zone
                            lon, lat = tm_to_lonlat(xx, yy, zz)
                        else:
                            lon, lat = xx, yy
                    else:
                        lon = float(row.get("lon") or row.get("longitude") or row.get("boylam"))
                        lat = float(row.get("lat") or row.get("latitude") or row.get("enlem"))
                except (TypeError, ValueError):
                    continue
                ada = row.get("ada", row.get("ADA", "")) or ""
                parsel = row.get("parsel", row.get("PARSEL", "")) or ""
                key = (str(ada), str(parsel))
                if key not in parcels:
                    parcels[key] = {"ada": str(ada), "parsel": str(parsel),
                                    "il": row.get("il", "") or "", "ilce": row.get("ilce", "") or "",
                                    "mahalle": row.get("mahalle", "") or "",
                                    "koordinatlar": []}
                parcels[key]["koordinatlar"].append([lon, lat])
        out = []
        for p in parcels.values():
            if len(p["koordinatlar"]) >= 3:
                p["alan_m2"] = round(polygon_area_m2(p["koordinatlar"]), 2)
                out.append(p)
        if not out:
            return None, "Yeterli köşe noktasına sahip parsel bulunamadı."
        return out, None
