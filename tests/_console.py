# -*- coding: utf-8 -*-
"""Windows konsol kodlaması yardımcısı (test betikleri için ortak).

GitHub Actions `windows-latest` runner'ında konsol kod sayfası cp1252'dir.
Türkçe karakterli `print()` çağrıları (ı ğ ş İ ç ö) bu kodlayıcıda kodlanamayacağı
için `UnicodeEncodeError` atar ve betik ilk satırda çöker — bu yüzden
`smoke_test.py` 1 saniyede düşüyordu (CI run #1 bu hatayı yakaladı).

`tests/conftest.py` yalnızca pytest ile koşulan test modülleri için çalışır;
doğrudan `python tests/smoke_test.py` diye çalıştırılan betikler için değil.
O yüzden çözümü bu ortak modüle aldık.
"""
import sys

__all__ = ["force_utf8_console"]


def force_utf8_console() -> None:
    """stdout/stderr'i UTF-8'e sabitle; yapılamazsa sessizce devam et.

    Sadece konsol çıktısını etkiler; uygulamanın kendi davranışını değiştirmez.
    `reconfigure` Python 3.7+'da var, platformdan bağımsızdır.
    """
    for _s in (sys.stdout, sys.stderr):
        if _s is None or not hasattr(_s, "reconfigure"):
            continue
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # Yazılı standart akış çoktan değiştirilmiş/kilitli olabilir;
            # testi düşürmeye değmeyecek kadar önemsiz.
            pass
