@echo off
REM ============================================================
REM  ProSU — Tek exe derleme (Windows)
REM  Gereksinim:  pip install pyinstaller
REM  Cikti:       dist\ProSU.exe
REM ============================================================
cd /d "%~dp0"
python -m PyInstaller ProSU.spec --noconfirm --clean
echo.
echo Derleme tamamlandi: dist\ProSU.exe
pause
