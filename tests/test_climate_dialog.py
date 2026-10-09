# -*- coding: utf-8 -*-
"""ClimateEditDialog regresyon testleri.

Eski hata: tablo 6 kolonluyken 7 veri başlığı veriliyordu; Yağış (p) kolonu
hiç oluşmadığından OK düğmesinde item(r, 6) -> None oluyor ve
'NoneType' object has no attribute 'text' uyarısı çıkıyordu.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QApplication, QDialog

from app.climate import ClimateData
from app.dialogs import ClimateEditDialog

app = QApplication.instance() or QApplication([])


class _FakeBox:
    """Modal QMessageBox.warning yerine kullanı: testleri kilitlemez."""
    shown = []

    @staticmethod
    def warning(parent, title, text):
        _FakeBox.shown.append((title, text))


@pytest.fixture()
def fake_box(monkeypatch):
    _FakeBox.shown.clear()
    monkeypatch.setattr("app.dialogs.QMessageBox", _FakeBox)
    return _FakeBox


def _accepted(dialog):
    return dialog.result() == int(QDialog.DialogCode.Accepted)


def test_tablo_yedi_kolon_ve_yagis_okunabilir():
    d = ClimateEditDialog(None, ClimateData())
    assert d.table.columnCount() == 7
    it = d.table.item(0, 6)
    assert it is not None
    assert float(it.text().replace(",", ".")) == pytest.approx(ClimateData().p[0])


def test_gecerli_duzenleme_kabul_ve_kayit():
    clim = ClimateData()
    d = ClimateEditDialog(None, clim)
    d.table.item(0, 6).setText("42,5")
    d._ok()
    assert _accepted(d)
    assert clim.p[0] == pytest.approx(42.5)


def test_bos_hucrede_cokme_yok_uyari_var(fake_box):
    clim = ClimateData()
    eski_rh = list(clim.rh)
    d = ClimateEditDialog(None, clim)
    d.table.takeItem(2, 3)  # Nem hücresini tamamen kaldır
    d._ok()
    assert not _accepted(d)
    assert fake_box.shown, "uyarı gösterilmeli"
    assert fake_box.shown[0][0] == "Geçersiz Değer"
    assert clim.rh == eski_rh


def test_gecersiz_sayi_hucreyi_soyler(fake_box):
    d = ClimateEditDialog(None, ClimateData())
    d.table.item(3, 1).setText("abc")
    d._ok()
    assert not _accepted(d)
    assert "Tmax" in fake_box.shown[0][1]


def test_nem_araligi_kontrolu(fake_box):
    d = ClimateEditDialog(None, ClimateData())
    d.table.item(1, 3).setText("150")
    d._ok()
    assert not _accepted(d)
    assert "Nem" in fake_box.shown[0][1]


def test_tmax_tmin_tutarliligi(fake_box):
    clim = ClimateData()
    eski_tmax = clim.tmax[0]
    d = ClimateEditDialog(None, clim)
    d.table.item(0, 1).setText("1.0")
    d.table.item(0, 2).setText("5.0")
    d._ok()
    assert not _accepted(d)
    assert "Tmax" in fake_box.shown[0][1]
    assert clim.tmax[0] == pytest.approx(eski_tmax)


def test_hatada_kismi_guncelleme_yok(fake_box):
    """Geçersiz satır varsa hiçbir satır climate'a yazılmamalı."""
    clim = ClimateData()
    eski_p0 = clim.p[0]
    d = ClimateEditDialog(None, clim)
    d.table.item(0, 6).setText("99.9")  # geçerli
    d.table.item(5, 1).setText("")      # geçersiz
    d._ok()
    assert not _accepted(d)
    assert clim.p[0] == pytest.approx(eski_p0)
