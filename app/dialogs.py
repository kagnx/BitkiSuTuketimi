# -*- coding: utf-8 -*-
"""Yardımcı diyaloglar: bitki düzenleme, koordinat girişi."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QPushButton, QLabel, QTextEdit, QDialogButtonBox,
                             QGroupBox, QMessageBox, QGridLayout, QRadioButton,
                             QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt

from .calculations import AY_AD
from .coords import dms_to_decimal, tm_to_lonlat, lonlat_to_tm, TM3_ZONES
from .plants_data import KATEGORILER


class PlantEditDialog(QDialog):
    """Bitki ekleme/düzenleme diyaloğu."""

    def __init__(self, parent=None, plant=None):
        super().__init__(parent)
        self.setWindowTitle("Bitki Düzenle" if plant else "Yeni Bitki")
        self.resize(460, 560)
        self.plant = plant or {}
        form = QFormLayout()

        self.ad = QLineEdit(self.plant.get("ad", ""))
        self.latin = QLineEdit(self.plant.get("latin", ""))
        self.kategori = QComboBox()
        self.kategori.addItems(KATEGORILER)
        if self.plant.get("kategori"):
            self.kategori.setCurrentText(self.plant["kategori"])

        self.kc_ini = QDoubleSpinBox(); self.kc_ini.setRange(0.05, 1.5); self.kc_ini.setSingleStep(0.05)
        self.kc_mid = QDoubleSpinBox(); self.kc_mid.setRange(0.05, 1.5); self.kc_mid.setSingleStep(0.05)
        self.kc_end = QDoubleSpinBox(); self.kc_end.setRange(0.05, 1.5); self.kc_end.setSingleStep(0.05)
        for w, k in ((self.kc_ini, "kc_ini"), (self.kc_mid, "kc_mid"), (self.kc_end, "kc_end")):
            w.setValue(float(self.plant.get(k, 0.7)))

        self.L_ini = QSpinBox(); self.L_ini.setRange(1, 300)
        self.L_dev = QSpinBox(); self.L_dev.setRange(1, 300)
        self.L_mid = QSpinBox(); self.L_mid.setRange(1, 300)
        self.L_late = QSpinBox(); self.L_late.setRange(1, 300)
        for w, k in ((self.L_ini, "L_ini"), (self.L_dev, "L_dev"), (self.L_mid, "L_mid"), (self.L_late, "L_late")):
            w.setValue(int(self.plant.get(k, 30)))

        self.boy = QDoubleSpinBox(); self.boy.setRange(0.1, 30); self.boy.setValue(float(self.plant.get("boy", 1.0))); self.boy.setSuffix(" m")
        self.kok = QDoubleSpinBox(); self.kok.setRange(0.1, 3); self.kok.setValue(float(self.plant.get("kok", 0.7))); self.kok.setSuffix(" m")
        self.ekim_ay = QComboBox()
        self.ekim_ay.addItems([f"{i+1} - {AY_AD[i]}" for i in range(12)])
        self.ekim_ay.setCurrentIndex(int(self.plant.get("ekim_ay", 4)) - 1)

        self.kritik_ad = QLineEdit(self.plant.get("kritik_ad", "Çiçeklenme"))
        self.kritik_merkez = QSpinBox()
        self.kritik_merkez.setRange(5, 95)
        self.kritik_merkez.setSuffix(" % (sezon konumu)")
        self.kritik_merkez.setValue(int(round(float(self.plant.get("kritik_merkez", 0.5)) * 100)))

        self.sira = QDoubleSpinBox(); self.sira.setRange(0, 30); self.sira.setDecimals(1)
        self.sira.setValue(float(self.plant.get("sira") or 0)); self.sira.setSuffix(" m")
        self.sira_arasi = QDoubleSpinBox(); self.sira_arasi.setRange(0, 30); self.sira_arasi.setDecimals(1)
        self.sira_arasi.setValue(float(self.plant.get("sira_arasi") or 0)); self.sira_arasi.setSuffix(" m")

        self.kaynak = QComboBox()
        self.kaynak.addItems(["FAO-56", "Tahmini", "Yerel Araştırma", "Diğer"])
        if self.plant.get("kaynak"):
            self.kaynak.setCurrentText(self.plant["kaynak"])
        self.aciklama = QTextEdit(self.plant.get("aciklama", ""))
        self.aciklama.setMaximumHeight(70)

        form.addRow("Türkçe Adı *", self.ad)
        form.addRow("Latince Adı", self.latin)
        form.addRow("Kategori", self.kategori)
        form.addRow("Kc başlangıç", self.kc_ini)
        form.addRow("Kc orta sezon", self.kc_mid)
        form.addRow("Kc sezon sonu", self.kc_end)
        form.addRow("Evre: başlangıç (gün)", self.L_ini)
        form.addRow("Evre: gelişme (gün)", self.L_dev)
        form.addRow("Evre: orta (gün)", self.L_mid)
        form.addRow("Evre: son (gün)", self.L_late)
        form.addRow("Bitki boyu", self.boy)
        form.addRow("Etkili kök derinliği", self.kok)
        form.addRow("Varsayılan dikim ayı", self.ekim_ay)
        form.addRow("Kritik dönem adı (su stresi)", self.kritik_ad)
        form.addRow("Kritik dönem konumu", self.kritik_merkez)
        form.addRow("Sıra arası (ağaçlar)", self.sira)
        form.addRow("Sıra üzeri (ağaçlar)", self.sira_arasi)
        form.addRow("Kc kaynağı", self.kaynak)
        form.addRow("Açıklama", self.aciklama)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self._validate)
        btn.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btn)

    def _validate(self):
        if not self.ad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Bitki adı zorunludur.")
            return
        self.accept()

    def data(self):
        ekim_idx = self.ekim_ay.currentIndex() + 1
        return {
            "ad": self.ad.text().strip(),
            "latin": self.latin.text().strip(),
            "kategori": self.kategori.currentText(),
            "kc_ini": self.kc_ini.value(), "kc_mid": self.kc_mid.value(), "kc_end": self.kc_end.value(),
            "L_ini": self.L_ini.value(), "L_dev": self.L_dev.value(),
            "L_mid": self.L_mid.value(), "L_late": self.L_late.value(),
            "boy": self.boy.value(), "kok": self.kok.value(), "ekim_ay": ekim_idx,
            "sira": self.sira.value() or None, "sira_arasi": self.sira_arasi.value() or None,
            "kaynak": self.kaynak.currentText(), "aciklama": self.aciklama.toPlainText().strip(),
            "kritik_ad": self.kritik_ad.text().strip() or "Çiçeklenme",
            "kritik_merkez": self.kritik_merkez.value() / 100.0,
        }


class ClimateEditDialog(QDialog):
    """12 aylık iklim verisi düzenleme tablosu."""

    KEYS = ("tmax", "tmin", "rh", "u2", "n", "p")
    KOLON_AD = ("Tmax", "Tmin", "Nem", "Rüzgâr", "Güneşlenme", "Yağış")

    def __init__(self, parent=None, climate=None):
        super().__init__(parent)
        self.setWindowTitle("İklim Verilerini Düzenle")
        self.resize(760, 420)
        self.climate = climate
        # ÖNEMLİ: Ay + 6 veri kolonu (tmax, tmin, rh, u2, n, p) = 7 kolon.
        # Eski hata: QTableWidget(12, 6) ile 6 kolon açılıyor, "Yağış (p)"
        # kolonu (sütun 6) hiç oluşmadığından OK'te item(r, 6) → None →
        # 'NoneType' object has no attribute 'text' hatası veriyordu.
        self.table = QTableWidget(12, 7)
        self.table.setHorizontalHeaderLabels(
            ["Ay", "Tmax (°C)", "Tmin (°C)", "Nem (%)", "Rüzgâr (m/s)", "Güneşlenme (saat)", "Yağış (mm)"])
        headers = self.table.horizontalHeader()
        headers.setStretchLastSection(True)
        keys = self.KEYS
        for r in range(12):
            self.table.setItem(r, 0, QTableWidgetItem(AY_AD[r]))
            self.table.item(r, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)
            for c, k in enumerate(keys, start=1):
                # None değerleri güvenli biçimde göster (boş hücre → uyarı)
                val = None
                if climate is not None:
                    arr = getattr(climate, k, None)
                    if isinstance(arr, (list, tuple)) and r < len(arr):
                        val = arr[r]
                txt = "" if val is None else f"{float(val):.2f}"
                it = QTableWidgetItem(txt)
                self.table.setItem(r, c, it)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self._ok)
        btn.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table)
        lay.addWidget(btn)

    def _ok(self):
        """Hücreleri güvenli okur ve doğrular.

        - item() None olabilir (boş/silinmiş hücre) → NoneType çökmesi yerine
          anlaşılır Türkçe uyarı verir.
        - Tüm satırlar geçmeden climate nesnesine ATAMA YAPILMAZ
          (kısmi güncelleme olmaz).
        """
        keys = self.KEYS
        yeni = {}
        try:
            for r in range(12):
                satir = {}
                for c, k in enumerate(keys, start=1):
                    it = self.table.item(r, c)
                    if it is None:
                        raise ValueError(
                            f"{AY_AD[r]} — {self.KOLON_AD[c - 1]}: hücre boş, "
                            f"sayısal bir değer girin.")
                    txt = it.text().strip().replace(",", ".")
                    if not txt:
                        raise ValueError(
                            f"{AY_AD[r]} — {self.KOLON_AD[c - 1]}: değer boş, "
                            f"sayısal bir değer girin.")
                    try:
                        v = float(txt)
                    except ValueError:
                        raise ValueError(
                            f"{AY_AD[r]} — {self.KOLON_AD[c - 1]}: "
                            f"geçersiz sayı ({it.text().strip()!r}).")
                    if k == "rh" and not (0 <= v <= 100):
                        raise ValueError(f"{AY_AD[r]}: Nem 0-100 arasında olmalı.")
                    if k in ("u2", "n", "p") and v < 0:
                        raise ValueError(
                            f"{AY_AD[r]} — {self.KOLON_AD[c - 1]} negatif olamaz.")
                    satir[k] = v
                if satir["tmax"] < satir["tmin"]:
                    raise ValueError(
                        f"{AY_AD[r]}: Tmax ({satir['tmax']:.1f}), "
                        f"Tmin'den ({satir['tmin']:.1f}) küçük olamaz.")
                yeni[r] = satir
        except (ValueError, AttributeError, TypeError) as e:
            QMessageBox.warning(self, "Geçersiz Değer", str(e))
            return
        # tüm satırlar geçerli → toplu atama
        for r, satir in yeni.items():
            for k, v in satir.items():
                getattr(self.climate, k)[r] = v
        self.accept()


class CoordinateDialog(QDialog):
    """Koordinat girişi: WGS84 (ondalık/DMS) veya TM (X,Y) → WGS84 (lon, lat)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Koordinat Gir")
        self.resize(420, 320)
        self.result_lonlat = None

        grp = QGroupBox("Koordinat Sistemi")
        self.rb_wgs = QRadioButton("WGS84 — Enlem/Boylam")
        self.rb_tm = QRadioButton("TM (Gauss-Krüger) — X, Y")
        self.rb_wgs.setChecked(True)
        lay_g = QVBoxLayout(grp)
        lay_g.addWidget(self.rb_wgs)
        lay_g.addWidget(self.rb_tm)

        g_wgs = QGridLayout()
        self.enlem = QLineEdit(); self.enlem.setPlaceholderText("Örn: 37.8667 veya 37 52 00.0")
        self.boylam = QLineEdit(); self.boylam.setPlaceholderText("Örn: 32.4833 veya 32 29 00.0")
        g_wgs.addWidget(QLabel("Enlem (K)"), 0, 0)
        g_wgs.addWidget(self.enlem, 0, 1)
        g_wgs.addWidget(QLabel("Boylam (D)"), 1, 0)
        g_wgs.addWidget(self.boylam, 1, 1)
        lbl_w = QLabel("Ondalık (37.8667) veya DMS (37 52 00.0) biçiminde girebilirsiniz.")
        lbl_w.setObjectName("muted")
        g_wgs.addWidget(lbl_w, 2, 0, 1, 2)

        g_tm = QGridLayout()
        self.x = QLineEdit(); self.x.setPlaceholderText("X (sağa) — Örn: 507123.45")
        self.y = QLineEdit(); self.y.setPlaceholderText("Y (yukarı) — Örn: 4192000.00")
        self.zone = QComboBox()
        self.zone.addItems([str(z) for z in TM3_ZONES])
        self.zone.setCurrentText("30")
        g_tm.addWidget(QLabel("X"), 0, 0)
        g_tm.addWidget(self.x, 0, 1)
        g_tm.addWidget(QLabel("Y"), 1, 0)
        g_tm.addWidget(self.y, 1, 1)
        g_tm.addWidget(QLabel("TM3 Dilimi (meridyen °D)"), 2, 0)
        g_tm.addWidget(self.zone, 2, 1)

        self.stack_widget = QGroupBox()
        self.stack_widget.setLayout(g_wgs)
        self.stack_tm = QGroupBox()
        self.stack_tm.setLayout(g_tm)
        self.stack_tm.hide()

        def _toggle():
            self.stack_widget.setVisible(self.rb_wgs.isChecked())
            self.stack_tm.setVisible(self.rb_tm.isChecked())
        self.rb_wgs.toggled.connect(_toggle)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self._ok)
        btn.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(grp)
        lay.addWidget(self.stack_widget)
        lay.addWidget(self.stack_tm)
        lay.addWidget(btn)

    def _parse_dms(self, txt):
        txt = txt.strip().replace(",", ".")
        parts = txt.split()
        if len(parts) == 1:
            return float(txt)
        if len(parts) == 2:
            return dms_to_decimal(float(parts[0]), float(parts[1]), 0)
        if len(parts) == 3:
            return dms_to_decimal(float(parts[0]), float(parts[1]), float(parts[2]))
        raise ValueError("Geçersiz format")

    def _ok(self):
        try:
            if self.rb_wgs.isChecked():
                lat = self._parse_dms(self.enlem.text())
                lon = self._parse_dms(self.boylam.text())
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("Enlem/boylam aralık dışında")
                self.result_lonlat = (lon, lat)
            else:
                x = float(self.x.text().replace(",", "."))
                y = float(self.y.text().replace(",", "."))
                z = int(self.zone.currentText())
                lon, lat = tm_to_lonlat(x, y, z)
                self.result_lonlat = (lon, lat)
        except ValueError as e:
            QMessageBox.warning(self, "Geçersiz Koordinat", str(e))
            return
        self.accept()


class ParcelSaveDialog(QDialog):
    """Çizim sonrası parsel kayıt penceresi: ada, parsel, il, ilçe, mahalle."""

    def __init__(self, parent=None, varsayilan_il=""):
        super().__init__(parent)
        self.setWindowTitle("Yeni Parsel Kaydet")
        self.resize(360, 260)
        form = QFormLayout(self)
        self.ada = QLineEdit()
        self.ada.setPlaceholderText("Örn: 1234")
        self.parsel = QLineEdit()
        self.parsel.setPlaceholderText("Örn: 56")
        self.il = QLineEdit(varsayilan_il)
        self.il.setPlaceholderText("İl (otomatik doldurulabilir)")
        self.ilce = QLineEdit()
        self.ilce.setPlaceholderText("İlçe")
        self.mahalle = QLineEdit()
        self.mahalle.setPlaceholderText("Mahalle / Köy")
        form.addRow("Ada No *", self.ada)
        form.addRow("Parsel No *", self.parsel)
        form.addRow("İl", self.il)
        form.addRow("İlçe", self.ilce)
        form.addRow("Mahalle", self.mahalle)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self._ok)
        btn.rejected.connect(self.reject)
        form.addRow(btn)

    def _ok(self):
        if not (self.ada.text().strip() and self.parsel.text().strip()):
            QMessageBox.warning(self, "Eksik Bilgi", "Ada No ve Parsel No zorunludur.")
            return
        self.accept()

    def values(self):
        return (self.ada.text().strip(), self.parsel.text().strip(),
                self.il.text().strip(), self.ilce.text().strip(),
                self.mahalle.text().strip())
