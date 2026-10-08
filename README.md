# 🌱 ProSU — Tarımsal Su İhtiyacı Hesaplama Sistemi

Türkiye'de yetiştirilen **sebze, meyve, tarla bitkisi, süs bitkisi, tıbbi-aromatik
bitki, endüstri bitkisi ve ağaç** türlerinin **su ihtiyacını** FAO-56 yöntemiyle
hesaplayan, **fıstık yeşili temalı**, PyQt6 tabanlı profesyonel masaüstü
uygulaması. Parseller **ada/parsel numarası** veya **koordinat (WGS84 / TM)** ile
harita üzerinde gösterilir.

## Özellikler

- **165 bitki** içeren veritabanı (FAO-56 Kc katsayıları, büyüme evreleri, kök
  derinliği, dikim aralığı); bitkiler uygulama içinden eklenebilir/düzenlenebilir.
- **ETo hesabı**: FAO-56 Penman-Monteith ve Hargreaves-Samani yöntemleri.
- **Etkili yağış**: USDA-SCS ve FAO basit yöntem.
- **Aylık su dengesi**: günlük kök bölgesi su bakiyesi (kova modeli — yağış fazlası
  sonraki güne devreder), ETc, etkili yağış, net/brüt ihtiyaç (mm + m³/da + toplam
  m³), ağaç başına litre, önerilen sulama aralığı (MAD × toprak × kök derinliği).
- **İklim verisi**: şehir seçimi, bölgesel ön tanımlar, 12 aylık manuel düzenleme
  ve Open-Meteo'dan çevrimiçi getirme (anahtar gerekmez).
- **Harita**: OpenStreetMap katmanı (çevrimdışında enlem/boylam ızgarası),
  parsel çizimi, işaretçi, mesafe/alan ölçümü, ada/parsel arama ve vurgulama,
  GeoJSON/CSV içe-dışa aktarım.
- **Raporlar**: HTML, CSV ve **PDF** dışa aktarım (kurumsal başlık/logo/imza seçeneğiyle), aylık döküm, SVG grafik, gelişim evresi dökümü ve kritik dönem su stresi riski bölümleri.
- **Fıstık yeşili tema** ve Türkçe arayüz.

## Kurulum

```bash
# 1) Bağımlılıklar (Python 3.9+ önerilir; 3.14 ile test edildi)
pip install -r requirements.txt

# 2) Çalıştırma
python main.py
```

## Tek Exe (kurulum gerektirmeyen dağıtım)

Windows'ta tek bir `ProSU.exe` üretmek için:

```bash
pip install pyinstaller
build_exe.bat        # veya: python -m PyInstaller ProSU.spec --noconfirm --clean
```

Çıktı: `dist/ProSU.exe` — Python kurulu olmayan bilgisayarda çalışır.
Uygulama veritabanını (`data/`) ve raporları (`raporlar/`) **exe'nin yanına**
yazar, böylece bir USB bellekle taşınabilir. İlk çalıştırmada 165 bitkili
veritabanı otomatik oluşur.

> Harita katmanı için internet gerekir; olmadığında uygulama ızgara görünümüyle
> çalışmaya devam eder. TAKBİS'e doğrudan erişim olmadığından ada/parsel
> sorguları, uygulama içine aktardığınız (GeoJSON/CSV) veya haritada çizdiğiniz
> parseller üzerinde çalışır.

## Veri Notları

- Kc ve evre süreleri **FAO-56 (Crop Evapotranspiration, 1998)** tablolarından
  alınmıştır; kaynağı "Tahmini" olarak işaretlenenler yerel literatüre göre
  verilmiş değerlerdir. Bitki Veritabanı sayfasından düzenlenebilir.
- Hesaplar ortalama iklim verisiyle yapılır; kritik kararlar için ziraat
  mühendisliği onayı önerilir.

## Proje Yapısı

```
main.py                 # giriş noktası
app/
  main_window.py        # ana pencere ve sayfalar
  calculations.py       # ETo, Kc eğrisi, su dengesi motoru
  climate.py            # iklim verisi (manuel + Open-Meteo)
  compare.py            # bitki karşılaştırma diyaloğu ve raporu
  coords.py             # WGS84 <-> TM dönüşüm (Krüger serisi)
  database.py           # SQLite: bitkiler + parseller
  dialogs.py            # bitki/iklim/koordinat diyalogları
  mapwidget.py          # OSM harita, parsel, ölçüm araçları
  plants_data.py        # FAO-56 bitki veri seti
  report.py             # HTML/CSV/PDF rapor üretimi
  config.py             # kurumsal rapor ayarları (data/config.json)
  paths.py              # exe/kaynak çalıştırmaya göre veri klasörü
  pdfexport.py          # HTML -> PDF (QTextDocument + QPrinter)
  theme.py              # fıstık yeşili tema
assets/                 # uygulama ikonu (icon.ico / icon.png)
ProSU.spec              # PyInstaller tek exe tanımı
build_exe.bat / .sh     # tek exe derleme betikleri
tests/                  # smoke_test.py + visual_check.py doğrulama
data/prosu.db           # çalışma zamanı veritabanı (otomatik oluşur)
raporlar/               # üretilen raporlar
```
