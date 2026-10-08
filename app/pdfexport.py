# -*- coding: utf-8 -*-
"""
HTML raporunu PDF'e dönüştürür.

Yaklaşım: QTextDocument + QPrinter (Qt'nin yerleşik PDF backend'i — ek bağımlılık
yok, yazıcı sürücüsü gerekmez). QTextDocument HTML'in alt kümesini destekler;
SVG çizimleri göstermediğinden grafik bölümü çıkarılır (veriler aylık tabloda
zaten yer alır). Kurumsal başlık ve imza HTML'e gömülü base64 görsellerle korunur.

Not: QtPrintSupport sınıflarını kullanmadan önce QApplication kurulmalıdır
(Windows'ta sıralama yanlış olursa sert çökme görülür); bu nedenle uygulama
modül yüklenirken oluşturulur.
"""
import os
import re

from PyQt6.QtWidgets import QApplication

# ÖNEMLİ: QtPrintSupport'u kullanmadan önce QApplication'ın var olduğundan emin ol
_APP = QApplication.instance() or QApplication([])

from PyQt6.QtCore import QMarginsF
from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrinter


def html_to_pdf(html, path, page_size="A4"):
    """HTML dizesini PDF dosyasına yazar. Başarısızsa RuntimeError fırlatır."""
    # QTextDocument SVG desteklemez; grafik bloğunu çıkar
    html_clean = re.sub(r"<svg.*?</svg>", "", html, flags=re.DOTALL | re.IGNORECASE)
    doc = QTextDocument()
    doc.setDocumentMargin(12)
    doc.setHtml(html_clean)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    size_id = QPageSize.PageSizeId.A3 if page_size == "A3" else QPageSize.PageSizeId.A4
    printer.setPageSize(QPageSize(size_id))
    printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
    doc.print(printer)
    if not os.path.exists(path) or os.path.getsize(path) < 200:
        raise RuntimeError("PDF dosyası üretilemedi")
    return path
