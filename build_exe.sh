#!/usr/bin/env bash
# ProSU — Tek exe derleme (Linux/macOS)
# Gereksinim:  pip install pyinstaller
# Cikti:       dist/ProSU
set -e
cd "$(dirname "$0")"
python -m PyInstaller ProSU.spec --noconfirm --clean
echo "Derleme tamamlandi: dist/ProSU"
