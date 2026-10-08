# -*- coding: utf-8 -*-
"""ProSU ana pencere: sayfalar, navigasyon ve aksiyonların bağlanması."""
import os
import shutil
from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QColor, QPainter, QFont
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QPushButton, QLabel, QComboBox,
                             QDoubleSpinBox, QSpinBox, QDateEdit, QGroupBox,
                             QLineEdit, QTableWidget, QTableWidgetItem,
                             QScrollArea, QFileDialog, QMessageBox, QListWidget,
                             QListWidgetItem, QCheckBox, QButtonGroup,
                             QHeaderView, QAbstractItemView, QTextEdit, QFrame,
                             QGridLayout, QSizePolicy, QApplication)

from .database import get_db, DB_PATH
from .calculations import (compute_water_need, monthly_eto, AY_AD, SOILS,
                           IRRIGATION_SYSTEMS, ETO_METHODS, RAIN_METHODS,
                           effective_rainfall)
from .climate import (ClimateData, REGIONS, fetch_openmeteo, REGIONAL_CLIMATE)
from .coords import (CITIES, ILLER, format_area, tm_zone_for_lon, lonlat_to_tm,
                      nearest_city)
from .dialogs import PlantEditDialog, CoordinateDialog, ClimateEditDialog
from .compare import CompareDialog
from .mapwidget import MapCanvas, TILE_SOURCES, DEFAULT_TILE_SOURCE, lonlat_to_pixel, pixel_to_lonlat
from .config import TELIF
from .report import save_report_html, save_report_csv, REPORT_DIR
from .theme import QSS, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, BG_DARK


class ClickableLabel(QLabel):
    """Tıklandığında clicked sinyali üreten etiket (kopyala gibi etkileşimler için)."""
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)

CITY_REGION = {
    "Adana": "Akdeniz (Antalya)", "Antalya": "Akdeniz (Antalya)", "Mersin": "Akdeniz (Antalya)",
    "Hatay": "Akdeniz (Antalya)", "Osmaniye": "Akdeniz (Antalya)",
    "İzmir": "Ege (İzmir)", "Aydın": "Ege (İzmir)", "Muğla": "Ege (İzmir)",
    "Manisa": "Ege (İzmir)", "Denizli": "Ege (İzmir)",
    "Trabzon": "Karadeniz (Trabzon)", "Rize": "Karadeniz (Trabzon)", "Ordu": "Karadeniz (Trabzon)",
    "Giresun": "Karadeniz (Trabzon)", "Samsun": "Karadeniz (Trabzon)", "Zonguldak": "Karadeniz (Trabzon)",
    "Şanlıurfa": "GAP (Şanlıurfa)", "Gaziantep": "GAP (Şanlıurfa)", "Diyarbakır": "GAP (Şanlıurfa)",
    "Mardin": "GAP (Şanlıurfa)", "Siirt": "GAP (Şanlıurfa)",
    "Erzurum": "Doğu Anadolu (Erzurum)", "Ağrı": "Doğu Anadolu (Erzurum)",
    "Van": "Doğu Anadolu (Erzurum)", "Muş": "Doğu Anadolu (Erzurum)",
    "Bursa": "Marmara (Bursa)", "Edirne": "Marmara (Bursa)", "Tekirdağ": "Marmara (Bursa)",
    "Kırklareli": "Marmara (Bursa)", "Kocaeli": "Marmara (Bursa)", "Sakarya": "Marmara (Bursa)",
    "Balıkesir": "Marmara (Bursa)", "Çanakkale": "Marmara (Bursa)",
    "Konya": "İç Anadolu (Konya)", "Ankara": "İç Anadolu (Konya)", "Eskişehir": "İç Anadolu (Konya)",
    "Kayseri": "İç Anadolu (Konya)", "Sivas": "İç Anadolu (Konya)", "Nevşehir": "İç Anadolu (Konya)",
    "Niğde": "İç Anadolu (Konya)", "Afyonkarahisar": "İç Anadolu (Konya)", "Uşak": "İç Anadolu (Konya)",
    "Kütahya": "İç Anadolu (Konya)", "Yozgat": "İç Anadolu (Konya)", "Tokat": "İç Anadolu (Konya)",
    "Amasya": "İç Anadolu (Konya)",
}


class FetchThread(QThread):
    """Open-Meteo'dan iklim verisi çeken arka plan iş parçacığı."""
    done = pyqtSignal(object, str)

    def __init__(self, lat, lon, alt, parent=None):
        super().__init__(parent)
        self.lat, self.lon, self.alt = lat, lon, alt

    def run(self):
        try:
            c = fetch_openmeteo(self.lat, self.lon, self.alt)
            self.done.emit(c, "" if c else "Veri alınamadı")
        except Exception as e:
            self.done.emit(None, str(e))


class ReverseGeocodeThread(QThread):
    """Parsel köşe koordinatlarından il/ilçe/mahalle bilgisini Nominatim
    (OpenStreetMap) ile arka planda çözer. Sonuç: {(lon, lat): {il, ilce, mahalle}}"""
    done = pyqtSignal(dict)

    def __init__(self, coords, cache, parent=None):
        super().__init__(parent)
        self.coords = coords          # [(lon, lat), ...] (5 ondalık yuvarlanmış)
        self.cache = cache

    def run(self):
        import time
        import requests
        out = {}
        for lon, lat in self.coords:
            key = (round(lon, 5), round(lat, 5))
            if key in self.cache:
                out[key] = self.cache[key]
                continue
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"format": "jsonv2", "lat": lat, "lon": lon,
                            "accept-language": "tr", "zoom": 14},
                    headers={"User-Agent": "ProSU-Tarim/1.0 (tarim su yonetimi)"},
                    timeout=8)
                j = r.json()
                a = j.get("address") or {}
                sonuc = {
                    "il": (a.get("province") or a.get("state") or a.get("region") or ""),
                    "ilce": (a.get("county") or a.get("district")
                             or a.get("city_district") or ""),
                    "mahalle": (a.get("neighbourhood") or a.get("suburb")
                                 or a.get("quarter") or a.get("village")
                                 or a.get("town") or ""),
                }
                self.cache[key] = sonuc
                out[key] = sonuc
            except Exception:
                pass
            time.sleep(1.1)  # Nominatim: saniyede en fazla 1 istek
        self.done.emit(out)


class BarChart(QWidget):
    """Aylık gruplu çubuk grafik."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.series = []   # (ad, QColor, değerler)
        self.setMinimumHeight(220)

    def set_data(self, labels, series):
        self.labels = labels
        self.series = series
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin_l, margin_r, margin_t, margin_b = 46, 8, 20, 26
        if not self.labels or not self.series:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Hesaplama yapıldığında grafik burada görünür")
            return
        maxv = max(max(s[2]) for s in self.series) or 1.0
        maxv = maxv * 1.15
        n = len(self.labels)
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b
        group_w = plot_w / n
        n_ser = len(self.series)
        bar_w = min(26.0, group_w / (n_ser + 0.6))

        # eksenler (tüm koordinatlar int olmalı — PyQt6 QPainter)
        p.setPen(QColor("#9AAE88"))
        p.drawLine(margin_l, margin_t, margin_l, margin_t + plot_h)
        p.drawLine(margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h)
        for i in range(5):
            y = int(margin_t + plot_h - plot_h * i / 4)
            v = maxv * i / 4
            p.setPen(QColor("#B9C9A8"))
            p.drawLine(margin_l, y, margin_l + plot_w, y)
            p.setPen(QColor("#6B7A5E"))
            p.drawText(2, y + 4, f"{v:.0f}")

        # çubuklar
        bar_w_i = max(1, int(bar_w) - 1)
        for i, lbl in enumerate(self.labels):
            cx = margin_l + group_w * i + group_w / 2
            for s, (name, color, vals) in enumerate(self.series):
                v = vals[i]
                bh = int(plot_h * v / maxv)
                x = int(cx - (n_ser * bar_w) / 2 + s * bar_w)
                y = int(margin_t + plot_h - bh)
                c = QColor(color)
                p.setPen(c.darker(130))
                p.setBrush(c)
                p.drawRoundedRect(x, y, bar_w_i, max(1, bh), 2, 2)
            p.setPen(QColor("#33452B"))
            p.drawText(int(cx - 12), int(h - 8), lbl[:3])

        # lejant
        lx = margin_l
        for name, color, vals in self.series:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(int(lx), 4, 12, 12)
            p.setPen(QColor("#33452B"))
            p.drawText(int(lx + 16), 14, name)
            lx += 16 + p.fontMetrics().horizontalAdvance(name) + 16
        p.end()


def _kpi_card(title, value, obj="big"):
    card = QFrame()
    card.setStyleSheet(f"QFrame {{ background: white; border: 1px solid #D8E3CC; border-radius: 10px; }}")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 10)
    t = QLabel(title)
    t.setObjectName("muted")
    v = QLabel(value)
    v.setObjectName(obj)
    v.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(v)
    return card


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProSU — Tarımsal Su İhtiyacı Hesaplama Sistemi")
        self.resize(1280, 800)
        self.setStyleSheet(QSS)

        self.db = get_db()
        self.climate = ClimateData()
        self.last_result = None
        self.last_ekstra = {}
        self._fetch_thread = None
        self._rg_thread = None
        self._rg_pending = []
        self._rg_cache = {}

        self._build_sidebar()
        self._build_pages()
        self._build_statusbar()

        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)
        self.refresh_dashboard()
        self.refresh_plant_table()
        self.refresh_parcel_list()
        self.refresh_reports()
        self.populate_plant_combo()
        self.populate_cities()
        self.refresh_parcels_on_map()

    # ------------------------------------------------------------------
    # iskelet
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 20, 12, 16)
        lay.setSpacing(6)

        title = QLabel("🌱 ProSU")
        title.setObjectName("appTitle")
        sub = QLabel("Tarımsal Su Yönetimi")
        sub.setObjectName("appSub")
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(16)

        self.nav_buttons = []
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        items = [
            ("🏠  Ana Sayfa", 0),
            ("🌿  Bitki Veritabanı", 1),
            ("💧  Su İhtiyacı Hesabı", 2),
            ("🗺️  Harita & Parsel", 3),
            ("📄  Raporlar", 4),
            ("⚙️  Ayarlar", 5),
        ]
        for text, idx in items:
            b = QPushButton(text)
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.stack.setCurrentIndex(i))
            self.nav_group.addButton(b)
            self.nav_buttons.append(b)
            lay.addWidget(b)
        lay.addStretch(1)

        self.central = QWidget()
        root = QHBoxLayout(self.central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(side)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.setCentralWidget(self.central)

    def _page_container(self, key):
        """Sayfa widget'ına başlık + içerik sarmalayıcı layout kurar."""
        w = self.pages[key]
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(12)
        return w, lay

    def _build_pages(self):
        self.pages = {}
        for name in ("dashboard", "plants", "calc", "map", "reports", "settings"):
            w = QWidget()
            self.stack.addWidget(w)
            self.pages[name] = w
        self._build_dashboard()
        self._build_plants_page()
        self._build_calc_page()
        self._build_map_page()
        self._build_reports_page()
        self._build_settings_page()

    def _build_statusbar(self):
        self.statusBar().showMessage("Hazır — Türkiye bitki su ihtiyacı hesaplama sistemi")
        self.parcel_status = QLabel("🗺️ Parsel seçilmedi")
        self.parcel_status.setObjectName("muted")
        self.parcel_status.setStyleSheet(
            "QLabel { color: #33691E; font-weight: 600; padding: 0 8px; }")
        self.statusBar().addPermanentWidget(self.parcel_status)

    def _update_parcel_status(self):
        """Durum çubuğundaki kalıcı parsel göstergesini günceller."""
        pid = self._selected_parcel_id()
        if pid is None:
            self.parcel_status.setText("🗺️ Parsel seçilmedi")
            return
        p = self.db.find_parcel_by_id(pid)
        if not p:
            self.parcel_status.setText("🗺️ Parsel seçilmedi")
            return
        alan = format_area(p.get("alan_m2") or 0) if p.get("alan_m2") else "Alan yok"
        txt = f"🗺️ Ada {p['ada']} / Parsel {p['parsel']}"
        yer = [str(p[k]) for k in ("il", "ilce", "mahalle") if p.get(k)]
        if yer:
            txt += " • " + " / ".join(yer)
        self.parcel_status.setText(f"{txt} • {alan}")

    # ==================================================================
    # ANA SAYFA
    # ==================================================================
    def _build_dashboard(self):
        w, lay = self._page_container("dashboard")

        title = QLabel("Ana Sayfa")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        self.dash_cards = QHBoxLayout()
        lay.addLayout(self.dash_cards)

        info = QGroupBox("Nasıl çalışır?")
        il = QVBoxLayout(info)
        il.addWidget(QLabel("1️⃣ Bitki Veritabanı'ndan bitki seçin veya yeni bitki ekleyin (FAO-56 Kc katsayıları)."))
        il.addWidget(QLabel("2️⃣ Su İhtiyacı Hesabı sayfasında konum, iklim ve sulama sistemi belirleyip hesaplayın."))
        il.addWidget(QLabel("3️⃣ Harita & Parsel sayfasında ada/parsel veya koordinat ile parselinizi gösterin; rapor oluşturun."))
        lay.addWidget(info)

        act = QGroupBox("Hızlı İşlemler")
        al = QHBoxLayout(act)
        for text, idx in [("💧 Su İhtiyacı Hesapla", 2), ("🗺️ Haritayı Aç", 3),
                          ("🌿 Bitki Veritabanı", 1), ("📄 Raporlar", 4)]:
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, i=idx: self.stack.setCurrentIndex(i))
            al.addWidget(b)
        lay.addWidget(act)
        lay.addStretch(1)

        # sol alt köşe: yanıp sönen telif etiketi
        bot = QHBoxLayout()
        self.blink_label = QLabel(TELIF)
        self.blink_label.setStyleSheet("color: #1B5E20; font-weight: 700; font-size: 12px;")
        self.blink_label.setToolTip("Program bilgisi")
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(650)
        self._blink_timer.timeout.connect(self._blink_tick)
        self._blink_timer.start()
        bot.addWidget(self.blink_label)
        bot.addStretch(1)
        lay.addLayout(bot)

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        self.blink_label.setStyleSheet(
            f"color: {'#1B5E20' if self._blink_on else '#A5C48E'}; font-weight: 700; font-size: 12px;")

    def refresh_dashboard(self):
        # eski kartları temizle
        while self.dash_cards.count():
            it = self.dash_cards.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        counts = self.db.plant_count_by_category()
        n_plant = sum(counts.values())
        n_parcel = len(self.db.list_parcels())
        cards = [
            ("Toplam Bitki Türü", str(n_plant)),
            ("Bitki Kategorisi", str(len(counts))),
            ("Kayıtlı Parsel", str(n_parcel)),
        ]
        if self.last_result:
            p = self.last_result["plant"]
            cards.insert(0, ("Son Hesap", f"{p['ad']}\n{self.last_result['total_m3_net']:,.0f} m³ net"))
        for t, v in cards:
            self.dash_cards.addWidget(_kpi_card(t, v))
        self.dash_cards.addStretch(1)

    # ==================================================================
    # BİTKİ VERİTABANI
    # ==================================================================
    def _build_plants_page(self):
        w, lay = self._page_container("plants")
        title = QLabel("Bitki Veritabanı")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Türkiye'de yetiştirilen bitkilerin FAO-56 bitki katsayıları ve büyüme evreleri. "
                     "Değerleri düzenleyebilir, yeni bitki ekleyebilirsiniz.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        bar = QHBoxLayout()
        self.plant_search = QLineEdit()
        self.plant_search.setPlaceholderText("Bitki adı, latince ad veya açıklamada ara…")
        self.plant_search.textChanged.connect(self.refresh_plant_table)
        self.plant_cat = QComboBox()
        self.plant_cat.addItem("Tüm Kategoriler", "")
        for k in ("Sebze", "Meyve", "Tarla Bitkisi", "Süs Bitkisi",
                  "Tıbbi ve Aromatik Bitki", "Endüstri Bitkisi", "Ağaç (Orman / Süs)"):
            self.plant_cat.addItem(k, k)
        self.plant_cat.currentIndexChanged.connect(self.refresh_plant_table)
        btn_add = QPushButton("➕ Yeni Bitki")
        btn_add.clicked.connect(self._add_plant)
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.clicked.connect(self._edit_plant)
        btn_del = QPushButton("🗑️ Sil")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete_plant)
        btn_calc = QPushButton("💧 Hesaplamada Aç")
        btn_calc.clicked.connect(self._plant_to_calc)
        bar.addWidget(self.plant_search, 2)
        bar.addWidget(self.plant_cat)
        bar.addWidget(btn_add)
        bar.addWidget(btn_edit)
        bar.addWidget(btn_del)
        bar.addWidget(btn_calc)
        lay.addLayout(bar)

        self.plant_table = QTableWidget(0, 10)
        self.plant_table.setHorizontalHeaderLabels(
            ["ID", "Ad", "Latince Ad", "Kategori", "Kc İni", "Kc Mid", "Kc Son",
             "Evre (gün)", "Dikim Ayı", "Kaynak"])
        self.plant_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.plant_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plant_table.setAlternatingRowColors(True)
        hh = self.plant_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.plant_table.setColumnWidth(0, 50)
        self.plant_table.doubleClicked.connect(lambda _: self._edit_plant())
        lay.addWidget(self.plant_table, 1)

    def _selected_plant_id(self):
        row = self.plant_table.currentRow()
        if row < 0:
            return None
        return int(self.plant_table.item(row, 0).text())

    def refresh_plant_table(self):
        cat = self.plant_cat.currentData() if hasattr(self.plant_cat, "currentData") else ""
        rows = self.db.list_plants(kategori=cat, arama=self.plant_search.text().strip())
        self.plant_table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            vals = [p["id"], p["ad"], p["latin"], p["kategori"],
                    f"{p['kc_ini']:.2f}", f"{p['kc_mid']:.2f}", f"{p['kc_end']:.2f}",
                    f"{p['L_ini']}+{p['L_dev']}+{p['L_mid']}+{p['L_late']}",
                    f"{p['ekim_ay']} ({AY_AD[p['ekim_ay']-1]})", p["kaynak"]]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setData(Qt.ItemDataRole.UserRole, p["id"])
                self.plant_table.setItem(r, c, it)

    def _add_plant(self):
        dlg = PlantEditDialog(self)
        if dlg.exec():
            self.db.add_plant(dlg.data())
            self.refresh_plant_table()
            self.populate_plant_combo()
            self.refresh_dashboard()
            self.statusBar().showMessage("Bitki eklendi", 3000)

    def _edit_plant(self):
        pid = self._selected_plant_id()
        if pid is None:
            QMessageBox.information(self, "Seçim Yok", "Önce bir bitki seçin.")
            return
        p = self.db.get_plant(pid)
        dlg = PlantEditDialog(self, p)
        if dlg.exec():
            self.db.update_plant(pid, dlg.data())
            self.refresh_plant_table()
            self.populate_plant_combo()
            self.statusBar().showMessage("Bitki güncellendi", 3000)

    def _delete_plant(self):
        pid = self._selected_plant_id()
        if pid is None:
            QMessageBox.information(self, "Seçim Yok", "Önce bir bitki seçin.")
            return
        p = self.db.get_plant(pid)
        if QMessageBox.question(self, "Sil", f"'{p['ad']}' silinsin mi?") == QMessageBox.StandardButton.Yes:
            self.db.delete_plant(pid)
            self.refresh_plant_table()
            self.populate_plant_combo()
            self.refresh_dashboard()

    def _plant_to_calc(self):
        pid = self._selected_plant_id()
        if pid is None:
            QMessageBox.information(self, "Seçim Yok", "Önce bir bitki seçin.")
            return
        for i in range(self.plant_combo.count()):
            if self.plant_combo.itemData(i) == pid:
                self.plant_combo.setCurrentIndex(i)
                break
        self.stack.setCurrentIndex(2)

    # ==================================================================
    # SU İHTİYACI HESABI
    # ==================================================================
    def _build_calc_page(self):
        w, lay = self._page_container("calc")
        title = QLabel("Su İhtiyacı Hesabı")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("FAO-56 Penman-Monteith / Hargreaves yöntemiyle bitki su tüketimi (ETc), "
                     "etkili yağış ve net/brüt sulama suyu ihtiyacı hesabı.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(14)

        # ---- sol: form ----
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_w = QWidget()
        fl = QVBoxLayout(form_w)
        fl.setContentsMargins(0, 0, 6, 0)

        g_plant = QGroupBox("🌿 Bitki")
        gpl = QVBoxLayout(g_plant)
        self.plant_combo = QComboBox()
        self.plant_combo.setMinimumWidth(240)
        self.plant_combo.currentIndexChanged.connect(self._plant_changed)
        self.kategori_lbl = QLabel("")
        self.kategori_lbl.setObjectName("muted")
        self.kategori_lbl.setWordWrap(True)
        gpl.addWidget(self.plant_combo)
        gpl.addWidget(self.kategori_lbl)
        fl.addWidget(g_plant)

        g_loc = QGroupBox("📍 Konum ve İklim")
        gl = QGridLayout(g_loc)
        self.city_combo = QComboBox()
        self.city_combo.setEditable(True)
        self.city_combo.currentTextChanged.connect(self._city_changed)
        self.lat_spin = QDoubleSpinBox(); self.lat_spin.setRange(-90, 90); self.lat_spin.setDecimals(5)
        self.lon_spin = QDoubleSpinBox(); self.lon_spin.setRange(-180, 180); self.lon_spin.setDecimals(5)
        self.alt_spin = QDoubleSpinBox(); self.alt_spin.setRange(-100, 5000); self.alt_spin.setSuffix(" m")
        self.region_combo = QComboBox()
        self.region_combo.addItem("— Bölgesel ön tanım yok —", None)
        for r in REGIONS:
            self.region_combo.addItem(r, r)
        self.region_combo.currentIndexChanged.connect(self._region_changed)
        gl.addWidget(QLabel("Şehir"), 0, 0)
        gl.addWidget(self.city_combo, 0, 1)
        gl.addWidget(QLabel("Enlem"), 1, 0)
        gl.addWidget(self.lat_spin, 1, 1)
        gl.addWidget(QLabel("Boylam"), 2, 0)
        gl.addWidget(self.lon_spin, 2, 1)
        gl.addWidget(QLabel("Yükseklik"), 3, 0)
        gl.addWidget(self.alt_spin, 3, 1)
        gl.addWidget(QLabel("İklim Bölgesi"), 4, 0)
        gl.addWidget(self.region_combo, 4, 1)
        self.btn_fetch = QPushButton("🌐 İnternetten İklim Getir")
        self.btn_fetch.clicked.connect(self._fetch_climate)
        gl.addWidget(self.btn_fetch, 5, 0, 1, 2)
        self.btn_edit_climate = QPushButton("✏️ İklim Verilerini Düzenle (12 ay)")
        self.btn_edit_climate.clicked.connect(self._edit_climate)
        gl.addWidget(self.btn_edit_climate, 6, 0, 1, 2)
        fl.addWidget(g_loc)

        g_opt = QGroupBox("⚙️ Hesap Parametreleri")
        go = QGridLayout(g_opt)
        self.eto_method = QComboBox()
        self.eto_method.addItems(ETO_METHODS)
        self.rain_method = QComboBox()
        self.rain_method.addItems(RAIN_METHODS)
        self.soil_combo = QComboBox()
        self.soil_combo.addItems(list(SOILS.keys()))
        self.system_combo = QComboBox()
        self.system_combo.addItems(list(IRRIGATION_SYSTEMS.keys()))
        self.system_combo.setCurrentText("Damla Sulama")
        self.mad_spin = QDoubleSpinBox(); self.mad_spin.setRange(0.1, 1.0); self.mad_spin.setDecimals(2)
        self.mad_spin.setValue(0.5); self.mad_spin.setSuffix("  (%50)")
        self.date_plant = QDateEdit()
        self.date_plant.setCalendarPopup(True)
        self.date_plant.setDisplayFormat("dd.MM.yyyy")
        self.date_plant.setDate(QDate(2024, 4, 1))
        self.area_spin = QDoubleSpinBox(); self.area_spin.setRange(0.1, 100000)
        self.area_spin.setValue(10.0); self.area_spin.setSuffix(" da")
        self.debi_spin = QDoubleSpinBox(); self.debi_spin.setRange(0.1, 10000)
        self.debi_spin.setValue(15.0); self.debi_spin.setSuffix(" m³/sa")
        self.debi_spin.setToolTip("Pompa / sistem debisi — sulama süresi hesabında kullanılır.")
        self.ecw_spin = QDoubleSpinBox(); self.ecw_spin.setRange(0.0, 20.0)
        self.ecw_spin.setDecimals(2); self.ecw_spin.setSingleStep(0.1)
        self.ecw_spin.setValue(1.0); self.ecw_spin.setSuffix(" dS/m")
        self.ecw_spin.setToolTip("Sulama suyunun elektriksel iletkenliği (ECw). Tuzluluk/yıkama "
                                 "uyarısında kullanılır; bilinmiyorsa 1.0 dS/m varsayılır.")
        go.addWidget(QLabel("ETo Yöntemi"), 0, 0)
        go.addWidget(self.eto_method, 0, 1)
        go.addWidget(QLabel("Etkili Yağış"), 1, 0)
        go.addWidget(self.rain_method, 1, 1)
        go.addWidget(QLabel("Toprak"), 2, 0)
        go.addWidget(self.soil_combo, 2, 1)
        go.addWidget(QLabel("Sulama Sistemi"), 3, 0)
        go.addWidget(self.system_combo, 3, 1)
        go.addWidget(QLabel("MAD (izin verilen tüketim)"), 4, 0)
        go.addWidget(self.mad_spin, 4, 1)
        go.addWidget(QLabel("Dikim / Ekim Tarihi"), 5, 0)
        go.addWidget(self.date_plant, 5, 1)
        go.addWidget(QLabel("Parsel Alanı"), 6, 0)
        go.addWidget(self.area_spin, 6, 1)
        go.addWidget(QLabel("Sistem Debisi (m³/sa)"), 7, 0)
        go.addWidget(self.debi_spin, 7, 1)
        go.addWidget(QLabel("Sulama Suyu EC"), 8, 0)
        go.addWidget(self.ecw_spin, 8, 1)
        fl.addWidget(g_opt)

        btn_calc = QPushButton("💧 HESAPLA")
        btn_calc.setMinimumHeight(44)
        btn_calc.clicked.connect(self.run_calculation)
        fl.addWidget(btn_calc)
        fl.addStretch(1)
        form_scroll.setWidget(form_w)
        body.addWidget(form_scroll, 0)

        # ---- sağ: sonuçlar ----
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        res_w = QWidget()
        rl = QVBoxLayout(res_w)
        rl.setContentsMargins(0, 0, 0, 0)

        self.result_title = QLabel("Sonuçlar — henüz hesaplama yapılmadı")
        self.result_title.setObjectName("cardTitle")
        rl.addWidget(self.result_title)

        kpi_row = QHBoxLayout()
        self.kpi_labels = {}
        for key, t in [("et", "Sezon ETc (mm)"), ("pe", "Etkili Yağış (mm)"),
                       ("net", "Net İhtiyaç (mm)"), ("gross", "Brüt İhtiyaç (mm)"),
                       ("m3net", "Net (m³)"), ("m3gross", "Brüt (m³)")]:
            card = _kpi_card(t, "—")
            self.kpi_labels[key] = card.findChildren(QLabel)[1]
            kpi_row.addWidget(card)
        rl.addLayout(kpi_row)

        self.chart = BarChart()
        rl.addWidget(self.chart)

        # Neden ETc? bilgi kutusu
        etc_info = QFrame()
        etc_info.setStyleSheet(
            "QFrame { background: #EAF4E0; border: 1px solid #AED581; border-radius: 8px; }")
        il = QVBoxLayout(etc_info)
        il.setContentsMargins(12, 8, 12, 8)
        lbl_t = QLabel("💧 Neden ETc? — Gerçek Bitki Su Tüketimi")
        lbl_t.setStyleSheet("font-weight: 700; color: #33691E;")
        lbl_d = QLabel(
            "ETo, tüm yeşil alanlar için genel bir atmosferik su kaybıdır (referans çim). "
            "ETc ise bu değere bitki katsayısı (Kc) ve gelişim evresi uygulanarak hedeflenen "
            "mahsulün gerçek ihtiyacını verir: her bitki suyu farklı hızda kullanır, bu da "
            "fazla/eksik sulamayı önler, bitki stresi yaşamaz ve verim yükselir.")
        lbl_d.setWordWrap(True)
        lbl_d.setObjectName("muted")
        il.addWidget(lbl_t)
        il.addWidget(lbl_d)
        rl.addWidget(etc_info)

        self.result_info = QLabel("")
        self.result_info.setObjectName("muted")
        self.result_info.setWordWrap(True)
        rl.addWidget(self.result_info)

        self.risk_label = QLabel("")
        self.risk_label.setWordWrap(True)
        rl.addWidget(self.risk_label)

        self.tuz_label = QLabel("")
        self.tuz_label.setWordWrap(True)
        rl.addWidget(self.tuz_label)

        # otomatik sulama planı önerisi (risk seviyesine göre)
        self.plan_label = QLabel("")
        self.plan_label.setWordWrap(True)
        self.plan_label.setStyleSheet(
            "QLabel { background: #E8F5E9; border: 1px solid #7CB342; border-radius: 8px;"
            " padding: 10px; color: #1B5E20; font-weight: 600; }")
        rl.addWidget(self.plan_label)

        self.plan_table = QTableWidget(0, 6)
        self.plan_table.setHorizontalHeaderLabels(
            ["Ay", "Sulama (adet)", "Aralık (gün)", "Brüt (mm)", "Hacim (m³)", "Süre (sa)"])
        self.plan_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.plan_table.setAlternatingRowColors(True)
        self.plan_table.setMaximumHeight(180)
        hhp = self.plan_table.horizontalHeader()
        hhp.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self.plan_table)

        self.stage_table = QTableWidget(0, 5)
        self.stage_table.setHorizontalHeaderLabels(
            ["Gelişim Evresi", "Süre (gün)", "Kc (baş→son)", "ETc (mm)", "Pay (%)"])
        self.stage_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stage_table.setAlternatingRowColors(True)
        self.stage_table.setMaximumHeight(170)
        hh2 = self.stage_table.horizontalHeader()
        hh2.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self.stage_table)

        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(["Ay", "ETc (mm)", "Etkili Yağış (mm)", "Net (mm)", "Brüt (mm)"])
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setMaximumHeight(300)
        hh = self.result_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self.result_table)

        act_row = QHBoxLayout()
        b_map = QPushButton("🗺️ Haritada Göster")
        b_map.clicked.connect(self._show_on_map)
        b_html = QPushButton("📄 HTML Rapor")
        b_html.clicked.connect(self._make_html_report)
        b_pdf = QPushButton("📕 PDF Rapor")
        b_pdf.clicked.connect(self._make_pdf_report)
        b_csv = QPushButton("📊 CSV Dışa Aktar")
        b_csv.clicked.connect(self._make_csv_report)
        b_cmp = QPushButton("⚖️ Bitki Karşılaştır")
        b_cmp.setToolTip("Aynı konum/iklim için farklı bitkilerin su ihtiyacını karşılaştırır")
        b_cmp.clicked.connect(self._open_compare)
        act_row.addWidget(b_map)
        act_row.addWidget(b_html)
        act_row.addWidget(b_pdf)
        act_row.addWidget(b_csv)
        act_row.addWidget(b_cmp)
        act_row.addStretch(1)
        rl.addLayout(act_row)
        rl.addStretch(1)
        res_scroll.setWidget(res_w)
        body.addWidget(res_scroll, 1)

        lay.addLayout(body, 1)

    # ---- hesap yardımcıları ----
    def populate_plant_combo(self, select_id=None):
        self.plant_combo.blockSignals(True)
        self.plant_combo.clear()
        for p in self.db.list_plants():
            self.plant_combo.addItem(f"{p['ad']}  —  {p.get('latin','')}", p["id"])
        if select_id is not None:
            for i in range(self.plant_combo.count()):
                if self.plant_combo.itemData(i) == select_id:
                    self.plant_combo.setCurrentIndex(i)
                    break
        self.plant_combo.blockSignals(False)
        self._plant_changed()

    def _plant_changed(self):
        pid = self.plant_combo.currentData()
        if pid is None:
            self.kategori_lbl.setText("")
            return
        p = self.db.get_plant(pid)
        self.kategori_lbl.setText(
            f"Kategori: {p['kategori']}  •  Kc: {p['kc_ini']:.2f}/{p['kc_mid']:.2f}/{p['kc_end']:.2f}  "
            f"•  Sezon: {p['L_ini']+p['L_dev']+p['L_mid']+p['L_late']} gün  •  Kaynak: {p['kaynak']}")
        # dikim tarihi ayını varsayılana çek
        d = self.date_plant.date()
        self.date_plant.setDate(QDate(d.year(), int(p["ekim_ay"]), 1))

    def populate_cities(self):
        self.city_combo.blockSignals(True)
        self.city_combo.clear()
        self.city_combo.addItem("Konya")
        for c in sorted(CITIES):
            if c != "Konya":
                self.city_combo.addItem(c)
        self.city_combo.setCurrentText("Konya")
        self.city_combo.blockSignals(False)
        self._city_changed()

    def _city_changed(self):
        city = self.city_combo.currentText().strip()
        if city in CITIES:
            lat, lon, alt = CITIES[city]
            self.lat_spin.setValue(lat)
            self.lon_spin.setValue(lon)
            self.alt_spin.setValue(alt)
            self.climate.set_city(city)
            region = CITY_REGION.get(city)
            if region:
                idx = self.region_combo.findData(region)
                if idx >= 0:
                    self.region_combo.setCurrentIndex(idx)
                    return
        self.region_combo.setCurrentIndex(0)

    def _region_changed(self):
        region = self.region_combo.currentData()
        if region:
            self.climate.load_region(region)
            self.statusBar().showMessage(f"İklim verisi: {region}", 3000)

    def _sync_climate_from_ui(self):
        self.climate.lat = self.lat_spin.value()
        self.climate.lon = self.lon_spin.value()
        self.climate.alt = self.alt_spin.value()

    def _edit_climate(self):
        self._sync_climate_from_ui()
        dlg = ClimateEditDialog(self, self.climate)
        dlg.exec()

    def _fetch_climate(self):
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        self._sync_climate_from_ui()
        self.statusBar().showMessage("İklim verisi internetten getiriliyor…")
        self.btn_fetch.setEnabled(False)
        self._fetch_thread = FetchThread(self.climate.lat, self.climate.lon, self.climate.alt, self)
        self._fetch_thread.done.connect(self._fetch_done)
        self._fetch_thread.start()

    def _fetch_done(self, climate, error):
        self.btn_fetch.setEnabled(True)
        if climate is None:
            QMessageBox.warning(self, "İklim Getirilemedi",
                                f"Çevrimiçi iklim verisi alınamadı.\n{error}\n\n"
                                "İnternet bağlantısını kontrol edin veya bölgesel ön tanımları / "
                                "manuel düzenlemeyi kullanın.")
            return
        self.climate = climate
        self.lat_spin.setValue(climate.lat)
        self.lon_spin.setValue(climate.lon)
        self.alt_spin.setValue(climate.alt)
        self.region_combo.setCurrentIndex(0)
        self.statusBar().showMessage(
            f"İklim verisi getirildi — yıllık yağış: {climate.annual_precip():.0f} mm", 5000)

    def run_calculation(self):
        pid = self.plant_combo.currentData()
        if pid is None:
            QMessageBox.information(self, "Bitki Seçin", "Lütfen bir bitki seçin.")
            return
        plant = self.db.get_plant(pid)
        self._sync_climate_from_ui()
        opts = {
            "ekim_tarihi": self.date_plant.date().toPyDate(),
            "alan_da": self.area_spin.value(),
            "eto_method": self.eto_method.currentText(),
            "rain_method": self.rain_method.currentText(),
            "toprak": self.soil_combo.currentText(),
            "sistem": self.system_combo.currentText(),
            "mad": self.mad_spin.value(),
            "debi": self.debi_spin.value(),
            "ecw": self.ecw_spin.value(),
        }
        try:
            res = compute_water_need(plant, self.climate, opts)
        except Exception as e:
            QMessageBox.critical(self, "Hesap Hatası", f"Hesaplama sırasında hata:\n{e}")
            return
        res["konum"] = self._current_konum()
        self.last_result = res
        self._show_result(res)
        self.refresh_dashboard()

    def _current_konum(self):
        """Hesapta kullanılan konum/şehir bilgisini derler (raporlar için)."""
        lat = self.climate.lat
        lon = self.climate.lon
        alt = self.climate.alt
        sehir = self.city_combo.currentText().strip()
        if sehir not in CITIES:
            sehir = None
        nc, km = nearest_city(lat, lon)
        if sehir is None and nc:
            sehir = nc
        if self.climate.ad == "Çevrimiçi İklim":
            iklim = "Çevrimiçi (Open-Meteo)"
        else:
            iklim = self.region_combo.currentData() or "Manuel / ön tanım"
        parsel = None
        pid = self._selected_parcel_id()
        if pid is not None:
            p = self.db.find_parcel_by_id(pid)
            if p:
                parsel = {"ada": p.get("ada", ""), "no": p.get("parsel", ""),
                          "il": p.get("il", ""), "ilce": p.get("ilce", ""),
                          "mahalle": p.get("mahalle", "")}
        return {
            "sehir": sehir,
            "en_yakin": nc,
            "mesafe_km": round(km, 1) if nc else None,
            "lat": lat, "lon": lon, "alt": alt,
            "iklim": iklim,
            "parsel": parsel,
        }

    def _show_result(self, res):
        p = res["plant"]
        self.result_title.setText(f"Sonuçlar — {p['ad']} ({p.get('latin','')})")
        self.kpi_labels["et"].setText(f"{res['tot_et']:,.0f} mm")
        self.kpi_labels["pe"].setText(f"{res['tot_pe']:,.0f} mm")
        self.kpi_labels["net"].setText(f"{res['tot_net']:,.0f} mm")
        self.kpi_labels["gross"].setText(f"{res['tot_gross']:,.0f} mm")
        self.kpi_labels["m3net"].setText(f"{res['total_m3_net']:,.0f} m³")
        self.kpi_labels["m3gross"].setText(f"{res['total_m3_gross']:,.0f} m³")

        # grafik
        labels = [m["ay"] for m in res["monthly"]]
        self.chart.set_data(labels, [
            ("ETc", "#7CB342", [m["et"] for m in res["monthly"]]),
            ("Net İhtiyaç", "#33691E", [m["net"] for m in res["monthly"]]),
            ("Brüt İhtiyaç", "#AED581", [m["gross"] for m in res["monthly"]]),
        ])

        self.result_info.setText(self._summary_info_text(res))

        # gelişim evresi dökümü (ETc'nin evrelere dağılımı)
        sd = res.get("stage_breakdown", [])
        self.stage_table.setRowCount(len(sd))
        # kritik dönem merkezinin bulunduğu evre satırını vurgula
        L = [int(res["plant"]["L_ini"]), int(res["plant"]["L_dev"]),
             int(res["plant"]["L_mid"]), int(res["plant"]["L_late"])]
        k_c = int(float(res["plant"].get("kritik_merkez") or 0.5) * sum(L))
        if k_c < L[0]:
            kritik_stage = 0
        elif k_c < L[0] + L[1]:
            kritik_stage = 1
        elif k_c < L[0] + L[1] + L[2]:
            kritik_stage = 2
        else:
            kritik_stage = 3
        for r, s in enumerate(sd):
            vals = [s["ad"], f"{s['gun']}", f"{s['kc_bas']:.2f} → {s['kc_son']:.2f}",
                    f"{s['et_mm']:,.1f}", f"%{s['oran']:.0f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if r == kritik_stage:
                    it.setBackground(QColor("#FFF3CD"))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.stage_table.setItem(r, c, it)

        # kritik dönem (çiçeklenme vb.) su stresi uyarısı
        kr = res.get("kritik")
        if kr:
            renk = {"yuksek": "#C62828", "orta": "#B26A00", "dusuk": "#2E7D32"}.get(kr["seviye"], "#2E7D32")
            self.risk_label.setStyleSheet(f"color: {renk}; font-weight: 700;")
            self.risk_label.setText(
                f"⚠️ {kr['mesaj']}\n"
                f"🗓️ {kr['ad']} dönemi: {kr['bas_tarih'].strftime('%d.%m.%Y')} – "
                f"{kr['son_tarih'].strftime('%d.%m.%Y')} ({kr['gun']} gün) • "
                f"dönem ETc {kr['et_mm']:,.0f} mm, net ihtiyaç {kr['net_mm']:,.0f} mm, "
                f"yağış karşılama %{kr['pe_cover']:.0f}, tepe günlük ihtiyaç {kr['tepe_gunluk_net']:.1f} mm")
        else:
            self.risk_label.setText("")

        # tuzluluk / su kalitesi uyarısı
        tz = res.get("tuzluluk")
        if tz:
            tz_renk = {"yuksek": "#C62828", "orta": "#B26A00", "dusuk": "#2E7D32"}.get(tz["seviye"], "#2E7D32")
            tz_bg = {"yuksek": "#FDE7E7", "orta": "#FFF3CD", "dusuk": "#E7F4E7"}.get(tz["seviye"], "#E7F4E7")
            tz_sev = {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}.get(tz["seviye"], tz["seviye"])
            self.tuz_label.setStyleSheet(
                f"QLabel {{ background: {tz_bg}; border: 1px solid {tz_renk}; "
                f"border-radius: 8px; padding: 10px; color: {tz_renk}; font-weight: 600; }}")
            lr = tz.get("lr_acik") or (f"%{tz['lr']:.0f}" if tz.get("lr") is not None else "-")
            txt = (f"🧂 Tuzluluk riski: {tz_sev} — {tz['mesaj']}\n"
                   f"Tolerans: {tz['sinif']} (ECe eşiği {tz['ece']:.1f} dS/m) • "
                   f"Sulama suyu EC: {tz['ecw']:.2f} dS/m • Yıkama gereksinimi (FAO): {lr}")
            if tz.get("oneriler"):
                txt += f"\n💡 {tz['oneriler'][0]}"
            self.tuz_label.setText(txt)
        else:
            self.tuz_label.setText("")

        # otomatik sulama planı (risk seviyesine göre aralık / süre / miktar)
        pl = res.get("plan")
        if pl:
            self.plan_label.setText(f"💧 {pl['tavsiye']}")
            rows = pl.get("ay", [])
            self.plan_table.setRowCount(len(rows))
            for r, m in enumerate(rows):
                vals = [m["ay"], m["sulama"], m["aralik"], m["brut_mm"], m["hacim_m3"], m["sure_sa"]]
                for c, v in enumerate(vals):
                    it = QTableWidgetItem(f"{v:,.1f}" if isinstance(v, float) else str(v))
                    self.plan_table.setItem(r, c, it)
        else:
            self.plan_label.setText("")
            self.plan_table.setRowCount(0)
        for r, m in enumerate(res["monthly"]):
            for c, v in enumerate([m["ay"], m["et"], m["pe"], m["net"], m["gross"]]):
                it = QTableWidgetItem(f"{v:,.1f}" if isinstance(v, float) else str(v))
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, None)
                self.result_table.setItem(r, c, it)

        self.statusBar().showMessage(
            f"Hesap tamam: {p['ad']} — net {res['total_m3_net']:,.0f} m³ / brüt {res['total_m3_gross']:,.0f} m³", 6000)

    def _summary_info_text(self, res):
        """Sonuç özet kutusu metni (sezon + konum + parsel + ağaç bilgisi)."""
        peak = res["peak_day"].strftime("%d.%m") if res.get("peak_day") else "-"
        info = (f"Sezon uzunluğu: {res['season_days']} gün  •  Ortalama Kc: {res['kc_avg']:.2f}  "
                f"•  En yoğun gün: {peak} ({res['peak_daily_net']:.1f} mm/gün)  •  "
                f"Sulama aralığı: {res['interval']} gün (~{res['irrigation_count']} sulama)")
        ko = res.get("konum")
        if ko:
            loc = ko.get("sehir") or "Harita Seçimi"
            if ko.get("en_yakin") and (not ko.get("sehir") or ko["en_yakin"] != ko["sehir"]):
                loc += f" (en yakın il: {ko['en_yakin']} ~{ko['mesafe_km']:.1f} km)"
            elif ko.get("mesafe_km") is not None and ko.get("sehir"):
                loc += f" (şehir merkezine ~{ko['mesafe_km']:.1f} km)"
            info += (f"\n📍 {loc} • {ko['lat']:.5f}°K, {ko['lon']:.5f}°D • "
                     f"{ko['alt']:,.0f} m • {ko.get('iklim', '')}")
            psel = ko.get("parsel")
            if psel and psel.get("ada"):
                yer = "/".join(str(psel[k]) for k in ("il", "ilce", "mahalle") if psel.get(k))
                info += (f"\n🗺️ Parsel: Ada {psel['ada']} / Parsel {psel['no']}"
                         + (f" ({yer})" if yer else ""))
        if res.get("per_tree"):
            pt = res["per_tree"]
            info += (f"\n🌳 Ağaç başına: {pt['alan_m2']:.1f} m² alan • sezon {pt['sezon_net_litre']:,.0f} L net / "
                     f"{pt['sezon_brut_litre']:,.0f} L brüt • sulama başına {pt['sulama_brut_litre']:,.0f} L")
        return info

    def _apply_parcel_area(self, parcel):
        """Seçili parselin alanını (m²) hesap alanına (da) aktarır."""
        try:
            m2 = float(parcel.get("alan_m2") or 0)
        except (TypeError, ValueError):
            return
        if m2 > 0:
            self.area_spin.setValue(round(m2 / 1000.0, 2))

    def _show_corner_coords(self, pid):
        """Parselin köşe koordinatlarını (WGS84 + TM3) panelde gösterir."""
        p = self.db.find_parcel_by_id(pid) if pid is not None else None
        coords = (p or {}).get("koordinatlar") or []
        if not coords:
            self.corner_hint.setText(
                "Bu parselin köşe koordinatı yok." if pid is not None
                else "Parseli odaklayın — köşe koordinatları burada görünür.")
            self.corner_hint.show()
            self.corner_table.hide()
            return
        self.corner_hint.hide()
        self.corner_table.setRowCount(len(coords))
        for i, (lon, lat) in enumerate(coords):
            try:
                z = tm_zone_for_lon(lon, width3=True)
                x, y = lonlat_to_tm(lon, lat, zone=z)
                tm = f"TM{z}: X {x:,.1f}  Y {y:,.1f}"
            except Exception:
                tm = "—"
            vals = [f"{i + 1}", f"{lat:.5f}°K, {lon:.5f}°D", tm]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.corner_table.setItem(i, c, it)
        self.corner_table.show()

    def _parcel_list_changed(self, current, _prev):
        """Parsel listesinde seçilen parselin alanını hesap alanına aktarır,
        durum çubuğunu ve köşe koordinat panelini günceller."""
        self._update_parcel_status()
        if current is None:
            self._show_corner_coords(None)
            return
        pid = current.data(Qt.ItemDataRole.UserRole)
        p = self.db.find_parcel_by_id(pid)
        if p:
            self._apply_parcel_area(p)
            self._show_corner_coords(pid)

    def _map_parcel_selected(self, parcel):
        """Haritada parsele tıklandığında parseli seçili yapar; varsa mevcut
        sonucun özet kutusuna yansıtır."""
        pid = parcel.get("id")
        if pid is None:
            return
        # parsel listesinde seç (current item) — _selected_parcel_id için
        for i in range(self.parcel_list.count()):
            it = self.parcel_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == pid:
                self.parcel_list.setCurrentItem(it)
                self.parcel_list.scrollToItem(it)
                break
        self.refresh_parcels_on_map(highlight_id=pid)
        self._apply_parcel_area(parcel)
        self._update_parcel_status()
        self._show_corner_coords(pid)
        ada, no = parcel.get("ada", ""), parcel.get("parsel", "")
        alan = parcel.get("alan_m2") or 0
        msg = f"Parsel seçildi: Ada {ada} / Parsel {no}"
        if alan:
            msg += f" — alanı hesaba aktarıldı ({float(alan)/1000.0:.2f} da)"
        msg += " — hesap/raporlarda kullanılır"
        self.statusBar().showMessage(msg, 6000)
        # mevcut sonucun özetine yansıt (hesabı yeniden çalıştırmadan)
        if self.last_result:
            psel = {"ada": str(ada), "no": str(no), "mahalle": parcel.get("mahalle", "")}
            self.last_result.setdefault("konum", {})["parsel"] = psel
            self.result_info.setText(self._summary_info_text(self.last_result))

    def _show_on_map(self):
        if not self.last_result:
            return
        self.stack.setCurrentIndex(3)
        lat, lon = self.climate.lat, self.climate.lon
        self.map.set_center(lon, lat, zoom=12)
        self.map.clear_markers()
        p = self.last_result["plant"]
        self.map.add_marker(lon, lat, f"{p['ad']} — {self.last_result['total_m3_net']:,.0f} m³ net")

    def _make_html_report(self):
        if not self.last_result:
            QMessageBox.information(self, "Hesap Yok", "Önce hesaplama yapın.")
            return
        from .config import load_config
        path = save_report_html(self.last_result, self.last_ekstra, load_config())
        QMessageBox.information(self, "Rapor Oluşturuldu", f"Rapor kaydedildi:\n{path}")
        self.refresh_reports()

    def _make_csv_report(self):
        if not self.last_result:
            QMessageBox.information(self, "Hesap Yok", "Önce hesaplama yapın.")
            return
        from .config import load_config
        path = save_report_csv(self.last_result, config=load_config())
        QMessageBox.information(self, "CSV Kaydedildi", f"CSV kaydedildi:\n{path}")
        self.refresh_reports()

    def _open_compare(self):
        """Aynı konum için bitki karşılaştırma diyaloğunu açar."""
        self._sync_climate_from_ui()
        dlg = CompareDialog(self)
        dlg.exec()

    def _make_pdf_report(self):
        if not self.last_result:
            QMessageBox.information(self, "Hesap Yok", "Önce hesaplama yapın.")
            return
        from .config import load_config
        from .report import build_report_html, REPORT_DIR
        from .pdfexport import html_to_pdf
        html_doc = build_report_html(self.last_result, self.last_ekstra, load_config())
        os.makedirs(REPORT_DIR, exist_ok=True)
        name = f"su_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = os.path.join(REPORT_DIR, name)
        try:
            html_to_pdf(html_doc, path)
        except Exception as e:
            QMessageBox.warning(self, "PDF Hatası", f"PDF üretilemedi:\n{e}")
            return
        QMessageBox.information(self, "PDF Oluşturuldu", f"PDF kaydedildi:\n{path}")
        self.refresh_reports()

    def _html_selected_to_pdf(self):
        it = self.report_list.currentItem()
        src = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not src or not src.lower().endswith(".html"):
            QMessageBox.information(self, "Seçim Yok", "Önce bir HTML rapor seçin.")
            return
        pdf_path = src.rsplit(".", 1)[0] + ".pdf"
        try:
            with open(src, encoding="utf-8") as f:
                html_doc = f.read()
            from .pdfexport import html_to_pdf
            html_to_pdf(html_doc, pdf_path)
        except Exception as e:
            QMessageBox.warning(self, "PDF Hatası", f"PDF üretilemedi:\n{e}")
            return
        QMessageBox.information(self, "PDF Oluşturuldu", f"PDF kaydedildi:\n{pdf_path}")
        self.refresh_reports()

    def _load_report_cfg(self):
        from .config import load_config
        cfg = load_config()
        self.chk_kurumsal.setChecked(bool(cfg.get("rapor_kurumsal")))
        self.kurum_ad.setText(cfg.get("kurum_ad") or "")
        self.kurum_alt.setText(cfg.get("kurum_alt") or "")
        self.imza_ad.setText(cfg.get("imza_ad") or "")
        self.imza_unvan.setText(cfg.get("imza_unvan") or "")
        self.logo_yolu.setText(cfg.get("logo_yolu") or "")
        self.imza_yolu.setText(cfg.get("imza_yolu") or "")

    def _save_report_cfg(self):
        from .config import save_config
        save_config({
            "rapor_kurumsal": self.chk_kurumsal.isChecked(),
            "kurum_ad": self.kurum_ad.text().strip(),
            "kurum_alt": self.kurum_alt.text().strip(),
            "imza_ad": self.imza_ad.text().strip(),
            "imza_unvan": self.imza_unvan.text().strip(),
            "logo_yolu": self.logo_yolu.text().strip(),
            "imza_yolu": self.imza_yolu.text().strip(),
        })
        self.statusBar().showMessage("Kurumsal rapor bilgileri kaydedildi", 3000)

    def _pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Logo Görseli", "", "Görseller (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.logo_yolu.setText(path)

    def _pick_imza(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "İmza Görseli", "", "Görseller (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.imza_yolu.setText(path)

    # ==================================================================
    # HARİTA & PARSEL
    # ==================================================================
    def _build_map_page(self):
        w, lay = self._page_container("map")
        title = QLabel("Harita & Parsel")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Ada/parsel veya koordinat (WGS84 / TM) ile parselleri haritada gösterin; "
                     "parsel çizin, GeoJSON/CSV içe aktarın.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(12)

        # sol: araçlar + parsel listesi
        left = QWidget()
        left.setFixedWidth(300)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        g_tools = QGroupBox("Araçlar")
        tl = QVBoxLayout(g_tools)
        tl.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        modes = [("✋ Gez", MapCanvas.MODE_PAN, "Kaydırma / yakınlaştırma"),
                 ("📍 İşaretle", MapCanvas.MODE_MARK, "Tıklayın → işaretçi ekle"),
                 ("🎯 Koordinat Seç", MapCanvas.MODE_PICK,
                  "Tıklayın → WGS84 + TM3 koordinatı seçilir, hesaplamada kullanılabilir"),
                 ("🟩 4 Köşe Parsel", MapCanvas.MODE_RECT,
                  "Köşelere sırayla 4 kez tıklayın → parsel otomatik kaydedilir"),
                 ("✏️ Parsel Çiz", MapCanvas.MODE_DRAW, "Köşelere tıklayın, çift tık ile kapat"),
                 ("📏 Ölç", MapCanvas.MODE_MEASURE, "İki nokta mesafe, üç+ nokta alan")]
        for text, mode, tip in modes:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.mode_group.addButton(b)
            b.clicked.connect(lambda _=False, m=mode: self.map.set_mode(m))
            tl.addWidget(b)
        if modes:
            self.mode_group.buttons()[0].setChecked(True)
        self.btn_online = QCheckBox("Harita katmanı (OSM) açık")
        self.btn_online.setChecked(True)
        self.btn_online.toggled.connect(lambda v: self.map.set_online(v))
        tl.addWidget(self.btn_online)
        ll.addWidget(g_tools)

        g_city = QGroupBox("Konum")
        cl = QGridLayout(g_city)
        self.map_city = QComboBox()
        self.map_city.addItem("Konya")
        for c in sorted(CITIES):
            if c != "Konya":
                self.map_city.addItem(c)
        self.map_city.setCurrentText("Konya")
        self.map_city.currentTextChanged.connect(self._map_city_changed)
        self.btn_coord = QPushButton("🧭 Koordinat Gir")
        self.btn_coord.clicked.connect(self._goto_coordinate)
        cl.addWidget(self.map_city, 0, 0)
        cl.addWidget(self.btn_coord, 0, 1)
        ll.addWidget(g_city)

        # haritadan seçilen koordinat paneli
        g_pick = QGroupBox("📌 Haritadan Seçilen Koordinat")
        pl = QVBoxLayout(g_pick)
        self.pick_coord_lbl = QLabel(
            "Önce araç çubuğundan \"🎯 Koordinat Seç\"e geçin, sonra haritaya tıklayın.\n"
            "WGS84 ve TM3 değerleri otomatik hesaplanır.")
        self.pick_coord_lbl.setWordWrap(True)
        self.pick_coord_lbl.setObjectName("muted")
        pl.addWidget(self.pick_coord_lbl)
        pbtn = QHBoxLayout()
        b_use = QPushButton("🌍 Hesaplamada Kullan")
        b_use.clicked.connect(self._use_picked_coord)
        b_clr = QPushButton("🧹 Temizle")
        b_clr.clicked.connect(lambda: self.map.clear_markers())
        pbtn.addWidget(b_use)
        pbtn.addWidget(b_clr)
        pl.addLayout(pbtn)
        ll.addWidget(g_pick)

        g_search = QGroupBox("Ada / Parsel Ara")
        sl = QGridLayout(g_search)
        self.search_ada = QLineEdit()
        self.search_ada.setPlaceholderText("Ada No")
        self.search_parsel = QLineEdit()
        self.search_parsel.setPlaceholderText("Parsel No")
        btn_find = QPushButton("🔍 Ara")
        btn_find.clicked.connect(self._find_parcel)
        sl.addWidget(self.search_ada, 0, 0)
        sl.addWidget(self.search_parsel, 0, 1)
        sl.addWidget(btn_find, 0, 2)
        ll.addWidget(g_search)

        g_corn = QGroupBox("📍 Köşe Koordinatları (WGS84 + TM)")
        cl = QVBoxLayout(g_corn)
        self.corner_hint = QLabel("Parseli odaklayın — köşe koordinatları burada görünür.")
        self.corner_hint.setWordWrap(True)
        self.corner_hint.setObjectName("muted")
        cl.addWidget(self.corner_hint)
        self.corner_table = QTableWidget(0, 3)
        self.corner_table.setHorizontalHeaderLabels(["Köşe", "WGS84 (Enlem, Boylam)", "TM3 (X, Y)"])
        self.corner_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.corner_table.setAlternatingRowColors(True)
        self.corner_table.setMaximumHeight(170)
        self.corner_table.hide()
        hhc = self.corner_table.horizontalHeader()
        hhc.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cl.addWidget(self.corner_table)
        ll.addWidget(g_corn)

        g_import = QGroupBox("Veri Aktarımı")
        il = QGridLayout(g_import)
        b_gj = QPushButton("📂 GeoJSON İçe")
        b_gj.clicked.connect(lambda: self._import_file("geojson"))
        b_csv = QPushButton("📂 CSV İçe")
        b_csv.clicked.connect(lambda: self._import_file("csv"))
        b_exp = QPushButton("💾 GeoJSON Dışa")
        b_exp.clicked.connect(self._export_geojson)
        il.addWidget(b_gj, 0, 0)
        il.addWidget(b_csv, 0, 1)
        il.addWidget(b_exp, 1, 0, 1, 2)
        ll.addWidget(g_import)

        self.parcel_group = QGroupBox("Parsel Listesi")
        g_list = self.parcel_group
        gl2 = QVBoxLayout(g_list)
        self.il_combo = QComboBox()
        self.il_combo.addItem("🏙️ Tüm İller", None)
        for il_adi in ILLER:
            self.il_combo.addItem(il_adi, il_adi)
        self.il_combo.currentIndexChanged.connect(lambda _: self.refresh_parcel_list())
        gl2.addWidget(self.il_combo)
        self.parcel_search = QLineEdit()
        self.parcel_search.setPlaceholderText("🔍 Ada / Parsel / İl / İlçe / Mahalle ara…")
        self.parcel_search.setClearButtonEnabled(True)
        self.parcel_search.textChanged.connect(lambda _: self.refresh_parcel_list())
        gl2.addWidget(self.parcel_search)
        self.parcel_summary_row = QWidget()
        row_count = QHBoxLayout(self.parcel_summary_row)
        row_count.setContentsMargins(0, 0, 0, 0)
        self.parcel_summary_lbl = ClickableLabel("")
        self.parcel_summary_lbl.setObjectName("muted")
        self.parcel_summary_lbl.setToolTip("Sayaç ve toplam alanı panoya kopyalamak için tıklayın")
        self.parcel_summary_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parcel_summary_lbl.clicked.connect(self._copy_total_area)
        row_count.addWidget(self.parcel_summary_lbl, 1)
        gl2.addWidget(self.parcel_summary_row)
        self.parcel_empty_lbl = QLabel("Henüz parsel yok — çizin veya içe aktarın")
        self.parcel_empty_lbl.setObjectName("muted")
        self.parcel_empty_lbl.hide()
        gl2.addWidget(self.parcel_empty_lbl)
        self.parcel_list = QListWidget()
        self.parcel_list.itemDoubleClicked.connect(lambda _: self._parcel_focus())
        self.parcel_list.currentItemChanged.connect(self._parcel_list_changed)
        gl2.addWidget(self.parcel_list)
        row = QHBoxLayout()
        b_show = QPushButton("Haritada Göster")
        b_show.clicked.connect(self._parcel_show)
        b_focus = QPushButton("🔍 Odakla")
        b_focus.setToolTip("Seçili parseli çevreleyecek şekilde yakınlaştırıp ortalar")
        b_focus.clicked.connect(self._parcel_focus)
        b_del = QPushButton("Sil")
        b_del.setObjectName("danger")
        b_del.clicked.connect(self._parcel_delete)
        row.addWidget(b_show)
        row.addWidget(b_focus)
        row.addWidget(b_del)
        gl2.addLayout(row)
        ll.addWidget(g_list, 1)

        # Sol panel uzun; pencere kısa olduğunda butonlar sıkışmasın/kırpılmasın diye
        # kaydırılabilir bir alana koy (içerik doğal boyutunda kalır, gerektikçe kaydırılır).
        left_scroll = QScrollArea()
        left_scroll.setWidget(left)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(300)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(left_scroll)

        # sağ: harita + görünüm araç çubuğu
        right = QWidget()
        rr = QVBoxLayout(right)
        rr.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        b_zin = QPushButton("➕")
        b_zin.setToolTip("Yakınlaştır")
        b_zin.clicked.connect(lambda: self.map.zoom_in())
        b_zout = QPushButton("➖")
        b_zout.setToolTip("Uzaklaştır")
        b_zout.clicked.connect(lambda: self.map.zoom_out())
        b_tr = QPushButton("🗺️ Türkiye'yi Göster")
        b_tr.setToolTip("Tüm Türkiye'yi görünüme sığdır")
        b_tr.clicked.connect(lambda: self.map.fit_turkiye())
        self.map_layer = QComboBox()
        self.map_layer.addItems(list(TILE_SOURCES.keys()))
        self.map_layer.setCurrentText(DEFAULT_TILE_SOURCE)
        self.map_layer.setToolTip("Harita katmanı (uydu / etiketli)")
        self.map_layer.setMinimumWidth(150)
        bar.addWidget(b_zin)
        bar.addWidget(b_zout)
        bar.addWidget(b_tr)
        bar.addWidget(QLabel("Katman:"))
        bar.addWidget(self.map_layer)
        self.zoom_lbl = QLabel("Zoom: 11")
        self.zoom_lbl.setObjectName("muted")
        self.zoom_lbl.setMinimumWidth(60)
        bar.addWidget(self.zoom_lbl)
        bar.addStretch(1)
        b_exp_csv = QPushButton("💾 CSV")
        b_exp_csv.setObjectName("ghost")
        b_exp_csv.setToolTip("Filtreye uyan parselleri CSV olarak dışa aktar")
        b_exp_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        b_exp_csv.clicked.connect(self._export_parcels_csv)
        bar.addWidget(b_exp_csv)
        rr.addLayout(bar)

        self.map = MapCanvas()
        self.map.status_message.connect(self.statusBar().showMessage)
        self.map.parcel_drawn.connect(self._parcel_drawn)
        self.map.coordinate_picked.connect(self._coordinate_picked)
        self.map.parcel_selected.connect(self._map_parcel_selected)
        self.map.zoom_changed.connect(lambda z: self.zoom_lbl.setText(f"Zoom: {z}"))
        self.map_layer.currentTextChanged.connect(self.map.set_tile_source)
        rr.addWidget(self.map, 1)
        body.addWidget(right, 1)

        lay.addLayout(body, 1)

    def _map_city_changed(self):
        city = self.map_city.currentText()
        if city in CITIES:
            lat, lon, alt = CITIES[city]
            self.map.set_center(lon, lat, zoom=11)

    def _goto_coordinate(self):
        dlg = CoordinateDialog(self)
        if dlg.exec() and dlg.result_lonlat:
            lon, lat = dlg.result_lonlat
            self.map.set_center(lon, lat, zoom=15)
            self.map.add_marker(lon, lat, f"Konum ({lat:.5f}, {lon:.5f})")
            city, km = self._activate_city_for_point(lon, lat)
            if city:
                self.statusBar().showMessage(
                    f"Koordinata gidildi: {lat:.6f}°K, {lon:.6f}°D — "
                    f"Şehir: {city} (~{km:.1f} km) hesap sayfasında aktif, "
                    "hesaplama buna göre yapılacak", 6000)
            else:
                self.statusBar().showMessage(
                    f"Koordinata gidildi: {lat:.6f}°K, {lon:.6f}°D", 4000)

    def _coordinate_picked(self, lon, lat):
        """Haritaya tıklandığında koordinatı gösterir (WGS84 + TM3 + şehir)."""
        self._picked = (lon, lat)
        try:
            z = tm_zone_for_lon(lon, width3=True)
            x, y = lonlat_to_tm(lon, lat, zone=z)
            tm_txt = f"TM{z}: X {x:,.2f}  Y {y:,.2f}"
        except Exception:
            tm_txt = "TM dönüşümü yapılamadı"
        city, km = nearest_city(lat, lon)
        if city:
            city_txt = f"🏙️ Şehir: {city}  (~{km:.1f} km)\n\n"
        else:
            city_txt = ""
        self.pick_coord_lbl.setText(
            f"🌐 WGS84\nEnlem (K): {lat:.6f}°\nBoylam (D): {lon:.6f}°\n\n"
            f"🧭 {tm_txt}\n\n{city_txt}"
            "\"🌍 Hesaplamada Kullan\" ile su ihtiyacı hesabına aktarın.")
        msg = f"Koordinat seçildi: {lat:.6f}°K, {lon:.6f}°D"
        if city:
            msg += f" — Şehir: {city} (~{km:.1f} km)"
        self.statusBar().showMessage(msg, 4000)

    def _activate_city_for_point(self, lon, lat, alt=None):
        """Noktanın ait olduğu şehri hesap sayfasında anında aktif yapar.
        Şehrin bölgesel iklim verisi yüklenir; koordinatlar şehir merkezi yerine
        seçilen noktada korunur. Şehir bulunamazsa 'Harita Seçimi' kalır.
        Döner: (şehir adı veya None, mesafe km veya None)."""
        city, km = nearest_city(lat, lon)
        if city:
            self.city_combo.setCurrentText(city)   # _city_changed: merkez + bölge iklimi
            # şehir merkezi yerine seçilen nokta kullanılsın
            self.lat_spin.setValue(lat)
            self.lon_spin.setValue(lon)
            if alt is not None:
                self.alt_spin.setValue(alt)
            self._sync_climate_from_ui()
            return city, km
        self.lat_spin.setValue(lat)
        self.lon_spin.setValue(lon)
        if alt is not None:
            self.alt_spin.setValue(alt)
        self._sync_climate_from_ui()
        self.city_combo.setCurrentText("Harita Seçimi")
        return None, None

    def _use_picked_coord(self):
        """Haritadan seçilen koordinatı hesap sayfasının konumuna uygular."""
        picked = getattr(self, "_picked", None)
        if not picked:
            QMessageBox.information(
                self, "Seçim Yok",
                "Önce \"🎯 Koordinat Seç\" aracıyla haritaya tıklayıp bir koordinat seçin.")
            return
        lon, lat = picked
        city, km = self._activate_city_for_point(lon, lat)
        self.stack.setCurrentIndex(2)
        if city:
            self.statusBar().showMessage(
                f"Hesap konumu haritadan alındı: {lat:.6f}°K, {lon:.6f}°D — "
                f"Şehir: {city} (~{km:.1f} km) aktif; hesap buna göre yapılacak. "
                "İnternetten İklim Getir ile güncel veri çekebilirsiniz", 6000)
        else:
            self.statusBar().showMessage(
                f"Hesap konumu haritadan alındı: {lat:.6f}°K, {lon:.6f}°D — "
                "İnternetten İklim Getir ile güncel veri çekebilirsiniz", 5000)

    def _fmt_area_toplam(self, m2):
        """Toplam alanı da/ha cinsinden biçimlendirir (filtre özet satırı için)."""
        if m2 <= 0:
            return "0 da"
        if m2 >= 10000:
            ha = m2 / 10000.0
            da = m2 / 1000.0
            return f"{da:,.0f} da ({ha:,.2f} ha)"
        return f"{m2 / 1000.0:,.2f} da"

    def _export_parcels_csv(self):
        """Aktif filtreye uyan parselleri CSV olarak dışa aktarır."""
        import csv as _csv
        il_txt, arama_txt = self._parcel_filter()
        parcels = self.db.list_parcels(il=il_txt, arama=arama_txt)
        if not parcels:
            QMessageBox.information(
                self, "Aktarılacak Parsel Yok",
                "Filtreye uyan parsel bulunamadı. Filtreyi genişletip tekrar deneyin.")
            return
        etiket = "tumu"
        if il_txt or arama_txt:
            etiket = (il_txt or "") + ("_" + arama_txt if arama_txt else "")
            etiket = etiket.replace(" ", "_").replace("İ", "I").replace("ı", "i")
        varsayilan = os.path.join(
            REPORT_DIR, f"parseller_{etiket}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Parsel Listesini CSV Olarak Kaydet", varsayilan,
            "CSV Dosyası (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            wr = _csv.writer(f)
            wr.writerow(["ProSU Parsel Listesi"])
            wr.writerow(["Dışa Aktarma", datetime.now().strftime("%d.%m.%Y %H:%M")])
            wr.writerow(["Filtre", (il_txt or "Tüm İller") + (f" • {arama_txt}" if arama_txt else "")])
            wr.writerow(["Parsel Sayısı", len(parcels)])
            toplam = sum(p.get("alan_m2") or 0 for p in parcels)
            wr.writerow(["Toplam Alan (m²)", f"{toplam:,.0f}"])
            wr.writerow(["Toplam Alan", self._fmt_area_toplam(toplam)])
            wr.writerow([])
            wr.writerow(["Ada", "Parsel", "İl", "İlçe", "Mahalle",
                         "Alan (m²)", "Alan (da)", "Köşe Sayısı", "Kaynak", "Tarih"])
            for p in parcels:
                wr.writerow([
                    p.get("ada", ""), p.get("parsel", ""), p.get("il", ""),
                    p.get("ilce", ""), p.get("mahalle", ""),
                    f"{p.get('alan_m2') or 0:,.0f}",
                    f"{(p.get('alan_m2') or 0) / 1000.0:,.2f}",
                    len(p.get("koordinatlar") or []),
                    p.get("kaynak", ""), p.get("tarih", ""),
                ])
        self.statusBar().showMessage(
            f"💾 {len(parcels)} parsel CSV olarak dışa aktarıldı: {path}", 5000)

    def _parcel_summary_parts(self):
        """Özet satırının iki parçası: (sayaç metni, toplam alan metni)."""
        il_txt, arama_txt = self._parcel_filter()
        total = len(self.db.list_parcels())
        shown = self.parcel_list.count()
        filt = self.db.list_parcels(il=il_txt, arama=arama_txt)
        top_m2 = sum(p.get("alan_m2") or 0 for p in filt)
        alan = self._fmt_area_toplam(top_m2)
        if il_txt or arama_txt:
            return f"{total} toplam parsel • {shown} gösteriliyor", alan
        return f"{total} parsel", alan

    def _parcel_summary_text(self):
        """Sayaç + toplam alanı tek satırda birleştirir (görünüm için)."""
        sayac, alan = self._parcel_summary_parts()
        return f"{sayac} • {alan}"

    def _copy_total_area(self):
        """Sayaç + toplam alan satırını panoya kopyalar; kısa süreliğine yeşil onay gösterir.
        Panoya değer ve alan ayrı satırlar olarak yazılır."""
        txt = self.parcel_summary_lbl.text().strip()
        if not txt or txt == "✅ Kopyalandı!":
            return
        sayac, alan = self._parcel_summary_parts()
        QApplication.clipboard().setText(f"{sayac}\n{alan}")
        self.parcel_summary_lbl.setStyleSheet(
            f"color: {PRIMARY_DARK}; font-size: 11px; font-weight: 700;")
        self.parcel_summary_lbl.setText("✅ Kopyalandı!")
        self.statusBar().showMessage(f"📋 Parsel özeti panoya kopyalandı: {sayac} • {alan}", 3000)
        QTimer.singleShot(2000, self._restore_area_label)

    def _restore_area_label(self):
        """Onay gösterildikten sonra özet satırını gerçek değere döndürür."""
        if not hasattr(self, "parcel_summary_lbl"):
            return
        self.parcel_summary_lbl.setStyleSheet("")
        self.parcel_summary_lbl.setText(self._parcel_summary_text())

    def _parcel_filter(self):
        """Aktif parsel filtresi: (il, arama metni)."""
        arama = getattr(self, "parcel_search", None)
        arama_txt = arama.text().strip() if arama else ""
        il_c = getattr(self, "il_combo", None)
        il_txt = il_c.currentData() if il_c else None
        return il_txt, arama_txt

    def refresh_parcels_on_map(self, highlight_id=None):
        """Haritaya parsel çizer; aktif il/arama filtresine uyan parselleri gösterir."""
        il_txt, arama_txt = self._parcel_filter()
        parcels = self.db.list_parcels(il=il_txt, arama=arama_txt)
        # vurgulanan parsel filtrenin dışındaysa da çiz (odak/arama çalışsın)
        if highlight_id is not None and not any(p.get("id") == highlight_id for p in parcels):
            hp = self.db.find_parcel_by_id(highlight_id)
            if hp:
                parcels = parcels + [hp]
        self.map.set_parcels(parcels, highlight_id=highlight_id)
        self.map.refresh_items()

    def refresh_parcel_list(self):
        il_txt, arama_txt = self._parcel_filter()
        total = len(self.db.list_parcels())
        self.parcel_list.clear()
        for p in self.db.list_parcels(il=il_txt, arama=arama_txt):
            area = format_area(p.get("alan_m2") or 0)
            txt = f"Ada {p['ada']} / Parsel {p['parsel']}  •  {area}"
            if p.get("mahalle"):
                txt += f"  ({p['mahalle']})"
            it = QListWidgetItem(txt)
            it.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.parcel_list.addItem(it)
        if hasattr(self, "parcel_summary_row"):
            self.parcel_summary_row.setVisible(total > 0)
        if hasattr(self, "parcel_search"):
            self.parcel_search.setEnabled(total > 0)
        if hasattr(self, "parcel_empty_lbl"):
            self.parcel_empty_lbl.setVisible(total == 0)
        if hasattr(self, "parcel_summary_lbl"):
            self.parcel_summary_lbl.setText(self._parcel_summary_text())
        if hasattr(self, "parcel_group"):
            shown = self.parcel_list.count()
            if il_txt or arama_txt:
                self.parcel_group.setTitle(f"Parsel Listesi ({shown}/{total})")
            else:
                self.parcel_group.setTitle(f"Parsel Listesi ({total})")
        self._update_parcel_status()
        self.refresh_parcels_on_map()

    def _parcel_drawn(self, data):
        self.db.add_parcel(data["ada"], data["parsel"], il=data.get("il", ""),
                           ilce=data.get("ilce", ""), mahalle=data.get("mahalle", ""),
                           coords=data["coords"], alan_m2=data["area"], kaynak="çizim")
        self.refresh_parcel_list()
        self.refresh_parcels_on_map()
        self.refresh_dashboard()
        yer = " / ".join(x for x in (data.get("il", ""), data.get("ilce", ""),
                                     data.get("mahalle", "")) if x)
        self.statusBar().showMessage(
            f"Parsel kaydedildi: Ada {data['ada']} / Parsel {data['parsel']}"
            + (f" ({yer})" if yer else "")
            + f" — {format_area(data['area'])}", 5000)

    def _find_parcel(self):
        ada = self.search_ada.text().strip()
        parsel = self.search_parsel.text().strip()
        if not ada or not parsel:
            QMessageBox.information(self, "Eksik Bilgi", "Ada ve Parsel no girin.")
            return
        p = self.db.find_parcel(ada, parsel)
        if not p:
            QMessageBox.information(
                self, "Parsel Bulunamadı",
                f"'{ada}/{parsel}' veritabanında yok.\n\n"
                "Gerçek tapu/CBS verisi TAKBİS üzerinden alınmalıdır. İsterseniz parseli "
                "harita üzerinde çizebilir ('Parsel Çiz') ya da GeoJSON/CSV olarak içe aktarabilirsiniz.")
            return
        coords = p.get("koordinatlar") or []
        if coords:
            clon = sum(c[0] for c in coords) / len(coords)
            clat = sum(c[1] for c in coords) / len(coords)
            self.map.set_center(clon, clat, zoom=16)
        self.refresh_parcels_on_map(highlight_id=p["id"])
        self.statusBar().showMessage(f"Parsel bulundu: Ada {p['ada']} / Parsel {p['parsel']}", 4000)

    def _selected_parcel_id(self):
        it = self.parcel_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _parcel_show(self):
        pid = self._selected_parcel_id()
        if pid is None:
            QMessageBox.information(self, "Seçim Yok", "Önce bir parsel seçin.")
            return
        self._fit_parcel(pid)

    def _parcel_focus(self):
        """Seçili parseli çevreleyen odak görünümü: haritaya geçip yakınlaştırır."""
        pid = self._selected_parcel_id()
        if pid is None:
            QMessageBox.information(self, "Seçim Yok", "Önce bir parsel seçin.")
            return
        self.stack.setCurrentIndex(3)
        self._fit_parcel(pid)

    def _fit_parcel(self, pid):
        """Parseli çevreleyecek zoom ve merkeze haritayı odaklar."""
        p = self.db.find_parcel_by_id(pid)
        if not p:
            return
        coords = p.get("koordinatlar") or []
        if len(coords) >= 3:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            self.map.fit_bounds(min(lons), min(lats), max(lons), max(lats), margin=0.15)
            self.refresh_parcels_on_map(highlight_id=pid)
            self._show_corner_coords(pid)
            self.statusBar().showMessage(
                f"Parsel odaklandı: Ada {p['ada']} / Parsel {p['parsel']}", 4000)
        else:
            self.map.set_center(self.climate.lon, self.climate.lat, zoom=16)
            self.refresh_parcels_on_map(highlight_id=pid)
            self._show_corner_coords(pid)

    def _parcel_delete(self):
        pid = self._selected_parcel_id()
        if pid is None:
            return
        if QMessageBox.question(self, "Sil", "Seçili parsel silinsin mi?") == QMessageBox.StandardButton.Yes:
            self.db.delete_parcel(pid)
            self.refresh_parcel_list()
            self.refresh_parcels_on_map()
            self.refresh_dashboard()

    def _import_file(self, kind):
        if kind == "geojson":
            path, _ = QFileDialog.getOpenFileName(self, "GeoJSON Seç", "", "GeoJSON (*.geojson *.json)")
            if not path:
                return
            crs, ok = QInputDialog_getItem(self, "Koordinat Sistemi", "Dosyadaki koordinatlar:",
                                           ["WGS84 (lon/lat)", "TM3-27", "TM3-30", "TM3-33",
                                            "TM3-36", "TM3-39", "TM3-42", "TM3-45"], 0, False)
            if not ok:
                return
            tm_zone = 30
            use_tm = crs.startswith("TM3")
            if use_tm:
                tm_zone = int(crs.split("-")[1])
            parcels, err = self.map.import_geojson(path, crs="TM" if use_tm else "WGS84", tm_zone=tm_zone)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "CSV Seç", "", "CSV (*.csv)")
            if not path:
                return
            crs, ok = QInputDialog_getItem(self, "Koordinat Sistemi", "CSV'deki koordinatlar:",
                                           ["WGS84 (lon/lat)", "TM3-27", "TM3-30", "TM3-33",
                                            "TM3-36", "TM3-39", "TM3-42", "TM3-45"], 0, False)
            if not ok:
                return
            tm_zone = 30
            use_tm = crs.startswith("TM3")
            if use_tm:
                tm_zone = int(crs.split("-")[1])
            parcels, err = self.map.import_csv(path, crs="TM" if use_tm else "WGS84", tm_zone=tm_zone)
        if err:
            QMessageBox.warning(self, "Aktarım Başarısız", err)
            return
        # il eksikse koordinattan en yakın il ile doldur (offline);
        # ilçe/mahalle eksikse arka planda Nominatim ile çözülür
        rg_todo = []
        for p in parcels:
            coords = p["koordinatlar"]
            clon = clat = None
            if coords:
                clon = sum(c[0] for c in coords) / len(coords)
                clat = sum(c[1] for c in coords) / len(coords)
                if not p["il"]:
                    nc, _km = nearest_city(clat, clon)
                    if nc:
                        p["il"] = nc
            pid = self.db.add_parcel(p["ada"] or "?", p["parsel"] or "?", il=p["il"],
                                     ilce=p["ilce"], mahalle=p["mahalle"],
                                     coords=coords, alan_m2=p["alan_m2"], kaynak=kind)
            if clon is not None and (not p["ilce"] or not p["mahalle"]):
                rg_todo.append((pid, round(clon, 5), round(clat, 5)))
        self.refresh_parcel_list()
        self.refresh_parcels_on_map()
        self.refresh_dashboard()
        self.statusBar().showMessage(f"{len(parcels)} parsel içe aktarıldı", 5000)
        self._start_reverse_geocode(rg_todo)

    def _start_reverse_geocode(self, todo):
        """ilçe/mahalle eksik parseller için arka plan ters jeokodlaması başlatır."""
        if todo:
            self._rg_pending.extend(todo)
        if self._rg_thread and self._rg_thread.isRunning():
            return  # devam eden iş bitince kalan işlenecek
        if not self._rg_pending:
            return
        coords = sorted({(lon, lat) for _pid, lon, lat in self._rg_pending})
        # yalnızca bu çalışmada istenecek koordinatları kuyruktan çıkar
        self._rg_pending = [(pid, lon, lat) for (pid, lon, lat) in self._rg_pending
                            if (lon, lat) not in coords]
        self._rg_thread = ReverseGeocodeThread(coords, self._rg_cache, self)
        self._rg_thread.done.connect(self._rg_done)
        self.statusBar().showMessage(
            "ilçe/mahalle bilgisi internetten tamamlanıyor…", 4000)
        self._rg_thread.start()

    def _rg_done(self, results):
        """Ters jeokodlama sonuçlarını parsel kayıtlarına uygular; kalan
        bekleyen varsa yeni çalışma başlatır."""
        if results:
            guncel = 0
            for p in self.db.list_parcels():
                coords = p.get("koordinatlar") or []
                if not coords:
                    continue
                key = (round(sum(c[0] for c in coords) / len(coords), 5),
                       round(sum(c[1] for c in coords) / len(coords), 5))
                r = results.get(key)
                if not r:
                    continue
                up = {}
                if r.get("il") and not p.get("il"):
                    up["il"] = r["il"]
                if r.get("ilce") and not p.get("ilce"):
                    up["ilce"] = r["ilce"]
                if r.get("mahalle") and not p.get("mahalle"):
                    up["mahalle"] = r["mahalle"]
                if up:
                    self.db.update_parcel_fields(p["id"], **up)
                    guncel += 1
            if guncel:
                self.refresh_parcel_list()
                self.refresh_parcels_on_map()
                self.statusBar().showMessage(
                    f"{guncel} parselin il/ilçe/mahalle bilgisi otomatik dolduruldu", 5000)
        self._start_reverse_geocode([])

    def _export_geojson(self):
        parcels = self.db.list_parcels()
        if not parcels:
            QMessageBox.information(self, "Parsel Yok", "Dışa aktarılacak parsel bulunamadı.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "GeoJSON Kaydet", "parseller.geojson", "GeoJSON (*.geojson)")
        if not path:
            return
        n = self.map.export_geojson(path, parcels)
        QMessageBox.information(self, "Dışa Aktarıldı", f"{n} parsel kaydedildi:\n{path}")

    # ==================================================================
    # RAPORLAR
    # ==================================================================
    def _build_reports_page(self):
        w, lay = self._page_container("reports")
        title = QLabel("Raporlar")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Oluşturulan HTML/CSV raporlar. Yeni rapor üretmek için önce Su İhtiyacı Hesabı yapın.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        row = QHBoxLayout()
        b_new = QPushButton("📄 HTML Rapor Oluştur (son hesap)")
        b_new.clicked.connect(self._make_html_report)
        b_pdf = QPushButton("📕 PDF Dışa Aktar (son hesap)")
        b_pdf.clicked.connect(self._make_pdf_report)
        b_csv = QPushButton("📊 CSV Dışa Aktar (son hesap)")
        b_csv.clicked.connect(self._make_csv_report)
        b_open = QPushButton("📂 Klasörü Aç")
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(REPORT_DIR)))
        b_h2p = QPushButton("📄 Seçili HTML → PDF")
        b_h2p.clicked.connect(self._html_selected_to_pdf)
        row.addWidget(b_new)
        row.addWidget(b_pdf)
        row.addWidget(b_csv)
        row.addWidget(b_h2p)
        row.addWidget(b_open)
        row.addStretch(1)
        lay.addLayout(row)

        self.report_list = QListWidget()
        self.report_list.itemDoubleClicked.connect(lambda it: QDesktopServices.openUrl(
            QUrl.fromLocalFile(it.data(Qt.ItemDataRole.UserRole))))
        lay.addWidget(self.report_list, 1)

        b_refresh = QPushButton("🔄 Listeyi Yenile")
        b_refresh.clicked.connect(self.refresh_reports)
        lay.addWidget(b_refresh)

    def refresh_reports(self):
        self.report_list.clear()
        if not os.path.isdir(REPORT_DIR):
            return
        files = sorted(os.listdir(REPORT_DIR), reverse=True)
        for f in files:
            if f.lower().endswith((".html", ".csv", ".pdf")):
                it = QListWidgetItem(f)
                it.setData(Qt.ItemDataRole.UserRole, os.path.join(REPORT_DIR, f))
                it.setToolTip(os.path.join(REPORT_DIR, f))
                self.report_list.addItem(it)

    # ==================================================================
    # AYARLAR
    # ==================================================================
    def _build_settings_page(self):
        w, lay = self._page_container("settings")
        title = QLabel("Ayarlar")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        g_map = QGroupBox("Harita")
        ml = QVBoxLayout(g_map)
        self.set_online = QCheckBox("Harita katmanı (OSM) çevrimiçi yüklensin")
        self.set_online.setChecked(True)
        self.set_online.toggled.connect(lambda v: (self.map.set_online(v), self.btn_online.setChecked(v)))
        ml.addWidget(self.set_online)
        b_clear = QPushButton("🗑️ Harita Önbelleğini Temizle")
        b_clear.clicked.connect(self._clear_tile_cache)
        ml.addWidget(b_clear)
        lay.addWidget(g_map)

        g_db = QGroupBox("Veritabanı")
        dl = QVBoxLayout(g_db)
        lbl_path = QLabel(f"Yol: {DB_PATH}")
        lbl_path.setObjectName("muted")
        lbl_path.setWordWrap(True)
        dl.addWidget(lbl_path)
        row = QHBoxLayout()
        b_backup = QPushButton("💾 Yedekle…")
        b_backup.clicked.connect(self._backup_db)
        b_reseed = QPushButton("♻️ Bitki Verisini Sıfırla")
        b_reseed.setObjectName("danger")
        b_reseed.clicked.connect(self._reseed_plants)
        row.addWidget(b_backup)
        row.addWidget(b_reseed)
        dl.addLayout(row)
        lay.addWidget(g_db)

        g_rapor = QGroupBox("📄 Rapor Kurumsal Başlık")
        rl2 = QVBoxLayout(g_rapor)
        self.chk_kurumsal = QCheckBox("Raporlara kurumsal başlık (logo, kurum adı, tarih) ve imza bloğu ekle")
        f2 = QGridLayout()
        self.logo_yolu = QLineEdit()
        self.logo_yolu.setReadOnly(True)
        self.logo_yolu.setPlaceholderText("Logo görseli seçilmedi")
        self.kurum_ad = QLineEdit()
        self.kurum_ad.setPlaceholderText("Kurum adı (örn: İl Tarım ve Orman Müdürlüğü)")
        self.kurum_alt = QLineEdit()
        self.kurum_alt.setPlaceholderText("Birim / alt yazı")
        self.imza_ad = QLineEdit()
        self.imza_ad.setPlaceholderText("İmza sahibi ad soyad")
        self.imza_unvan = QLineEdit()
        self.imza_unvan.setPlaceholderText("Unvan")
        self.imza_yolu = QLineEdit()
        self.imza_yolu.setReadOnly(True)
        self.imza_yolu.setPlaceholderText("İmza görseli seçilmedi")
        b_logo = QPushButton("📷 Logo…")
        b_logo.clicked.connect(self._pick_logo)
        b_imza = QPushButton("🖊️ İmza…")
        b_imza.clicked.connect(self._pick_imza)
        f2.addWidget(QLabel("Logo"), 0, 0)
        f2.addWidget(self.logo_yolu, 0, 1)
        f2.addWidget(b_logo, 0, 2)
        f2.addWidget(QLabel("Kurum Adı"), 1, 0)
        f2.addWidget(self.kurum_ad, 1, 1, 1, 2)
        f2.addWidget(QLabel("Birim / Alt Yazı"), 2, 0)
        f2.addWidget(self.kurum_alt, 2, 1, 1, 2)
        f2.addWidget(QLabel("İmza Sahibi"), 3, 0)
        f2.addWidget(self.imza_ad, 3, 1, 1, 2)
        f2.addWidget(QLabel("Unvan"), 4, 0)
        f2.addWidget(self.imza_unvan, 4, 1, 1, 2)
        f2.addWidget(QLabel("İmza Görseli"), 5, 0)
        f2.addWidget(self.imza_yolu, 5, 1)
        f2.addWidget(b_imza, 5, 2)
        rl2.addWidget(self.chk_kurumsal)
        rl2.addLayout(f2)
        b_save = QPushButton("💾 Kurumsal Bilgileri Kaydet")
        b_save.clicked.connect(self._save_report_cfg)
        rl2.addWidget(b_save)
        lay.addWidget(g_rapor)

        g_about = QGroupBox("Hakkında")
        al = QVBoxLayout(g_about)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(
            "ProSU — Tarımsal Su İhtiyacı Hesaplama Sistemi  (v1.0.0)\n\n"
            "• Türkiye'de yetiştirilen 120+ bitki türü için FAO-56 tabanlı su ihtiyacı hesabı\n"
            "• ETo: FAO-56 Penman-Monteith ve Hargreaves-Samani yöntemleri\n"
            "• Etkili yağış: USDA-SCS ve FAO basit yöntem\n"
            "• Harita üzerinde ada/parsel ve koordinat (WGS84/TM) gösterimi\n"
            "• OpenStreetMap katmanı (internet) ve çevrimdışı ızgara desteği\n"
            "• HTML/CSV raporlama\n\n"
            "Kc değerleri FAO-56 (Crop Evapotranspiration, 1998) esas alınarak hazırlanmıştır. "
            "Yerel iklim, çeşit ve toprak koşullarına göre değerler uygulama içinden "
            "düzenlenebilir; kritik kararlar için ziraat mühendisliği onayı önerilir.")
        al.addWidget(txt)
        self._load_report_cfg()

        # Programcı / telif bilgisi
        credit = QFrame()
        credit.setStyleSheet("QFrame { background: #E8F1DC; border: 1px solid #AED581; border-radius: 8px; }")
        cl = QVBoxLayout(credit)
        cl.setContentsMargins(12, 10, 12, 10)
        lbl1 = QLabel("👨‍💻 Programlayan: Mehmet YOLCU — Şube Müdürü")
        lbl1.setStyleSheet("font-weight: 700; color: #33691E; font-size: 13px;")
        lbl2 = QLabel("Copyright © 2026 — Her Hakkı Saklıdır!")
        lbl2.setObjectName("muted")
        cl.addWidget(lbl1)
        cl.addWidget(lbl2)
        al.addWidget(credit)
        lay.addWidget(g_about)
        lay.addStretch(1)

    def _clear_tile_cache(self):
        from PyQt6.QtGui import QPixmapCache
        QPixmapCache.clear()
        import tempfile
        cache = os.path.join(tempfile.gettempdir(), "prosu_tiles")
        if os.path.isdir(cache):
            shutil.rmtree(cache, ignore_errors=True)
        self.statusBar().showMessage("Harita önbelleği temizlendi", 3000)

    def _backup_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "Veritabanı Yedeği", "prosu_yedek.db", "SQLite (*.db)")
        if not path:
            return
        try:
            shutil.copy2(DB_PATH, path)
            QMessageBox.information(self, "Yedek Alındı", f"Yedek: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Yedekleme Hatası", str(e))

    def _reseed_plants(self):
        if QMessageBox.question(
                self, "Sıfırla",
                "Tüm bitkiler silinip fabrika verisi (FAO-56) yeniden yüklenecek. Devam?") \
                == QMessageBox.StandardButton.Yes:
            for p in self.db.list_plants():
                self.db.delete_plant(p["id"])
            self.db.seed_plants()
            self.refresh_plant_table()
            self.populate_plant_combo()
            self.refresh_dashboard()
            self.statusBar().showMessage("Bitki verisi sıfırlandı", 4000)


# yardımcılar
def QInputDialog_getItem(parent, title, label, items, current=0, editable=False):
    from PyQt6.QtWidgets import QInputDialog
    return QInputDialog.getItem(parent, title, label, items, current, editable)
