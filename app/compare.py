# -*- coding: utf-8 -*-
"""Bitki karşılaştırma diyaloğu: aynı konum/iklim için birden fazla bitkinin
su ihtiyacını hesaplar, tablo olarak gösterir ve HTML/CSV raporu üretir."""
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QComboBox, QPushButton, QLabel, QListWidget,
                             QListWidgetItem, QTableWidget, QTableWidgetItem,
                             QMessageBox, QHeaderView, QAbstractItemView,
                             QSplitter, QWidget, QFileDialog)

from .calculations import compute_water_need
from .plants_data import KATEGORILER
from .report import build_compare_html, save_compare_csv

RISK_SIRA = {"yuksek": 0, "orta": 1, "dusuk": 2}

BASLIKLAR = ["Bitki", "Kategori", "Sezon (gün)", "ETc (mm)", "Etkili Yağış (mm)",
             "Net (mm)", "Brüt (mm)", "Net (m³)", "Brüt (m³)", "Aralık (gün)",
             "Sulama (adet)", "Su Stresi Riski", "Tuzluluk Riski", "Ağaç başına (L/sulama)"]


class CompareDialog(QDialog):
    """Aynı nokta için farklı bitkilerin su ihtiyacını karşılaştırır."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("⚖️ Bitki Su İhtiyacı Karşılaştırma")
        self.resize(1080, 620)
        self.results = []
        self._plants = []
        self._checked = set()

        # ---- sol: bitki seçimi ----
        left = QWidget()
        left.setMinimumWidth(330)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        g_filt = QGroupBox("Filtre")
        fl = QHBoxLayout(g_filt)
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("Tümü", None)
        for k in KATEGORILER:
            self.cat_combo.addItem(k, k)
        self.cat_combo.currentIndexChanged.connect(self._fill_list)
        b_all = QPushButton("Tümünü Seç")
        b_all.clicked.connect(self._select_all)
        b_none = QPushButton("Temizle")
        b_none.clicked.connect(self._select_none)
        fl.addWidget(self.cat_combo, 1)
        fl.addWidget(b_all)
        fl.addWidget(b_none)
        ll.addWidget(g_filt)

        self.plant_list = QListWidget()
        self.plant_list.itemChanged.connect(self._remember_checks)
        ll.addWidget(self.plant_list, 1)

        g_bilgi = QGroupBox("Karşılaştırma Notu")
        nl = QVBoxLayout(g_bilgi)
        n = QLabel("Tüm bitkiler aynı konum/iklim ve aynı hesap parametreleriyle "
                   "(toprak, sistem, alan, MAD, debi) hesaplanır; dikim tarihi her "
                   "bitkinin önerilen ekim ayına göre alınır. Seçili bitkileri işaretleyip "
                   "\"Karşılaştır\"a basın.")
        n.setWordWrap(True)
        n.setObjectName("muted")
        nl.addWidget(n)
        ll.addWidget(g_bilgi)

        # ---- sağ: sonuç tablosu ----
        self.table = QTableWidget(0, len(BASLIKLAR))
        self.table.setHorizontalHeaderLabels(BASLIKLAR)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(True)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(self.table)
        split.setSizes([360, 720])

        # ---- alt: butonlar ----
        btn_row = QHBoxLayout()
        b_cmp = QPushButton("⚖️ Karşılaştır")
        b_cmp.setObjectName("primary")
        b_cmp.clicked.connect(self._compare)
        b_html = QPushButton("📄 HTML Rapor")
        b_html.clicked.connect(self._save_html)
        b_csv = QPushButton("💾 CSV Dışa Aktar")
        b_csv.clicked.connect(self._save_csv)
        b_kapat = QPushButton("Kapat")
        b_kapat.clicked.connect(self.accept)
        btn_row.addWidget(b_cmp)
        btn_row.addWidget(b_html)
        btn_row.addWidget(b_csv)
        btn_row.addStretch(1)
        btn_row.addWidget(b_kapat)

        lay = QVBoxLayout(self)
        lay.addWidget(split, 1)
        lay.addLayout(btn_row)

        self._fill_list()

    # ---- bitki listesi ----
    def _fill_list(self):
        self.plant_list.itemChanged.disconnect(self._remember_checks)
        self.plant_list.clear()
        kat = self.cat_combo.currentData()
        self._plants = [p for p in self.parent().db.list_plants()
                        if not kat or p["kategori"] == kat]
        for p in self._plants:
            it = QListWidgetItem(f"{p['ad']}  —  {p.get('latin', '')}")
            it.setData(Qt.ItemDataRole.UserRole, p["id"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if p["id"] in self._checked
                             else Qt.CheckState.Unchecked)
            self.plant_list.addItem(it)
        self.plant_list.itemChanged.connect(self._remember_checks)

    def _remember_checks(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._checked.add(pid)
        else:
            self._checked.discard(pid)

    def _select_all(self):
        for i in range(self.plant_list.count()):
            it = self.plant_list.item(i)
            it.setCheckState(Qt.CheckState.Checked)
            self._checked.add(it.data(Qt.ItemDataRole.UserRole))

    def _select_none(self):
        for i in range(self.plant_list.count()):
            it = self.plant_list.item(i)
            it.setCheckState(Qt.CheckState.Unchecked)
            self._checked.discard(it.data(Qt.ItemDataRole.UserRole))

    def _selected_plants(self):
        ids = {it.data(Qt.ItemDataRole.UserRole)
               for it in (self.plant_list.item(i) for i in range(self.plant_list.count()))
               if it.checkState() == Qt.CheckState.Checked}
        return [p for p in self.parent().db.list_plants() if p["id"] in ids]

    # ---- hesap ----
    def _compare(self):
        plants = self._selected_plants()
        if not plants:
            QMessageBox.information(self, "Seçim Yok", "Karşılaştırmak için en az bir bitki seçin.")
            return
        parent = self.parent()
        parent._sync_climate_from_ui()
        yil = parent.date_plant.date().year()
        opts_base = {
            "alan_da": parent.area_spin.value(),
            "eto_method": parent.eto_method.currentText(),
            "rain_method": parent.rain_method.currentText(),
            "toprak": parent.soil_combo.currentText(),
            "sistem": parent.system_combo.currentText(),
            "mad": parent.mad_spin.value(),
            "debi": parent.debi_spin.value(),
            "ecw": parent.ecw_spin.value(),
        }
        self.results = []
        for p in plants:
            opts = dict(opts_base)
            opts["ekim_tarihi"] = date(yil, int(p["ekim_ay"]), 1)
            try:
                r = compute_water_need(dict(p), parent.climate, opts)
            except Exception:
                continue
            self.results.append({
                "plant": r["plant"],
                "tuzluluk": (r.get("tuzluluk") or {}).get("seviye"),
                "sezon": r["season_days"],
                "et": r["tot_et"], "pe": r["tot_pe"],
                "net": r["tot_net"], "gross": r["tot_gross"],
                "m3_net": r["total_m3_net"], "m3_gross": r["total_m3_gross"],
                "aralik": r["interval"], "sulama": r["irrigation_count"],
                "risk": (r.get("kritik") or {}).get("seviye"),
                "agac_l": (r.get("per_tree") or {}).get("sulama_brut_litre"),
                "alan_da": r["alan_da"], "toprak": r["toprak"], "sistem": r["sistem"],
                "mad": r["mad"], "eto_method": r["opts"].get("eto_method", ""),
            })
        if not self.results:
            QMessageBox.warning(self, "Hesap Hatası",
                                "Seçili bitkiler için hesaplama yapılamadı.")
            return
        self._fill_table()
        self.parent().statusBar().showMessage(
            f"Karşılaştırma tamam: {len(self.results)} bitki hesaplandı.", 5000)

    def _fill_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))
        risk_etiket = {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}
        for i, r in enumerate(self.results):
            vals = [r["plant"]["ad"], r["plant"].get("kategori", ""), r["sezon"],
                    round(r["et"], 1), round(r["pe"], 1), round(r["net"], 1),
                    round(r["gross"], 1), round(r["m3_net"], 1), round(r["m3_gross"], 1),
                    r["aralik"], r["sulama"],
                    risk_etiket.get(r["risk"], ""),
                    risk_etiket.get(r.get("tuzluluk"), ""),
                    (f"{r['agac_l']:,.0f}" if r.get("agac_l") else "")]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)

    # ---- dışa aktarım ----
    def _konum(self):
        parent = self.parent()
        parent._sync_climate_from_ui()
        return parent._current_konum()

    def _config(self):
        from .config import load_config
        return load_config()

    def _save_html(self):
        if not self.results:
            QMessageBox.information(self, "Sonuç Yok", "Önce \"⚖️ Karşılaştır\"a basın.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Karşılaştırma Raporu (HTML)", "karsilastirma.html",
            "HTML dosyası (*.html)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_compare_html(self.results, self._konum(), self._config()))
        self.parent().statusBar().showMessage(f"Rapor kaydedildi: {path}", 5000)
        QMessageBox.information(self, "Kaydedildi", f"Rapor kaydedildi:\n{path}")

    def _save_csv(self):
        if not self.results:
            QMessageBox.information(self, "Sonuç Yok", "Önce \"⚖️ Karşılaştır\"a basın.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Karşılaştırma Raporu (CSV)", "karsilastirma.csv",
            "CSV dosyası (*.csv)")
        if not path:
            return
        save_compare_csv(self.results, self._konum(), self._config(), path=path)
        self.parent().statusBar().showMessage(f"Rapor kaydedildi: {path}", 5000)
        QMessageBox.information(self, "Kaydedildi", f"Rapor kaydedildi:\n{path}")
