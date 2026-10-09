# -*- mode: python ; coding: utf-8 -*-
"""
ProSU — Tek exe derleme tanımı (PyInstaller).

Kullanım:
    python -m PyInstaller ProSU.spec --noconfirm --clean
Çıktı: dist/ProSU.exe  (kurulum gerektirmeyen, tek dosya)

Not: Uygulama veritabanını ve raporları exe'nin YANINDAKI data/ ve raporlar/
klasörlerine yazar (bkz. app/paths.py) — taşınabilir dağıtım.
"""
import os

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[(os.path.join("assets", "icon.png"), "assets")],
    hiddenimports=[
        "PyQt6.QtPrintSupport",
        "PyQt6.QtNetwork",
        "PyQt6.QtSvg",
        "requests",
        # yeni rapor export formatları (app/report.py)
        "openpyxl",
        "reportlab",
        "reportlab.pdfgen",
        "reportlab.platypus",
        "reportlab.lib",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ProSU",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                # pencere uygulaması (konsol açmaz)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join("assets", "icon.ico"),
)
