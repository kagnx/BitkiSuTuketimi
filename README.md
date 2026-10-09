# 🌱 ProSU — Tarımsal Su İhtiyacı Hesaplama Sistemi

[![CI](https://github.com/kagnx/BitkiSuTuketimi/actions/workflows/ci.yml/badge.svg)](https://github.com/kagnx/BitkiSuTuketimi/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Lisans: MIT](https://img.shields.io/badge/Lisans-MIT-4e7d2c.svg)](LICENSE)
[![FAO-56](https://img.shields.io/badge/y%C3%B6ntem-FAO--56%20Penman--Monteith-0b6e4f)](https://www.fao.org/3/x0490e/x0490e00.htm)

Türkiye'de yetiştirilen **sebze, meyve, tarla bitkisi, süs bitkisi, tıbbi-aromatik
bitki, endüstri bitkisi ve ağaç** türlerinin su ihtiyacını **FAO-56 Penman-Monteith**
yöntemiyle hesaplayan, **fıstık yeşili temalı**, PyQt6 tabanlı masaüstü uygulaması.
Parseller **ada/parsel numarası** veya **koordinat (WGS84 / TM3 / UTM)** ile harita
üzerinde gösterilir; sulama planı gün gün, ay ay dökümlenir.

> **Önemli:** Hesaplar ortalama iklim verisiyle yapılır. Kritik sulama kararları için
> ziraat mühendisi / DSİ kontrolü önerilir; uygulama karar destek aracıdır.

---

## 📑 İçindekiler

- [Özellikler](#-özellikler)
- [Kurulum](#-kurulum)
- [Hesap Yöntemi](#-hesap-yöntemi)
- [Raporlar](#-raporlar)
- [Tek Exe](#-tek-exe-kurulum-gerektirmeyen-dağıtım)
- [Testler](#-testler)
- [Proje Yapısı](#-proje-yapısı)
- [Veri Notları ve Lisans](#-veri-notları-ve-lisans)
- [Katkıda Bulunma](#-katkıda-bulunma)

---

## ✨ Özellikler

### 🌱 Bitki veritabanı — 305 bitki
- **FAO-56** katsayıları: `Kc_ini`, `Kc_mid`, `Kc_end` + **4 büyüme evresi** süresi
  (`L_ini`, `L_dev`, `L_mid`, `L_late`).
- Bitki boyu, **etkili kök derinliği**, dikim ayı, sıra aralığı, kritik dönem,
  **tuz toleransı (ECe)**.
- **7 kategori**: Sebze (70), Meyve (54), Süs Bitkisi (44), Tarla Bitkisi (41),
  Tıbbi-Aromatik (42), Endüstri (21), Ağaç (33).
- Uygulama içinden **ekleme / düzenleme / silme**; değişiklikler SQLite'da kalıcı.
- Bitki karşılaştırma aracı (su ihtiyacı + sezon uzunluğu yan yana).

### 💧 Su ihtiyacı hesabı
- **ETo**: FAO-56 Penman-Monteith (tam iklim verisi) ve **Hargreaves-Samani**
  (sadece sıcaklıkla çalışır).
- **Kc eğrisi**: 4 evreli doğrusal model + **nem/rüzgâr iklim düzeltmesi**.
- **Etkili yağış**: USDA-SCS ve FAO basit yöntemi.
- **Gün gün su dengesi**: kök bölgesi kova modeli (yağış fazlası bir sonraki güne
  devreder), derin sızıntı hesabı.
- Çıktılar: **ETc, ET0, etkili yağış, net & brüt ihtiyaç** (mm, m³/da, toplam m³),
  **ağaç başına litre**, **önerilen sulama aralığı** (MAD × toprak × kök derinliği),
  **sulama sistemi verimliliğine göre uygulanacak miktar**.

### 🧠 Karar destek
- **Su stresi skoru (0–100)**: yağış karşılama oranı, sezon sonu kök bölgesi
  bakiyesi, kritik tepe yoğunluğu, risk seviyesi ve sezon uzunluğundan oluşan
  **5 bileşenli** puan; DÜŞÜK / ORTA / YÜKSEK seviyeleri.
- **Kriter tabanlı sulama önerisi**: risk seviyesine ve verilere göre somut eylem
  listesi (sıcaklık eşiği, minimum sulama sayısı, aralık daraltma vb.).
- **Kök bölgesi / toprak stratejisi**: kök derinliği (<0,5 m / <1,0 m / ≥1,0 m) ve
  toprak dokusuna göre strateji (parça-parça uygulama, drenaj, aralık).
- **Tuzluluk uyarısı**: FAO Ayers & Westcot eşiklerine göre yıkama lavyumu önerisi.

### 🗺️ Harita ve parsel
- **OpenStreetMap** katmanı (+ Esri / Google alternatifleri); internet yoksa
  **çevrimdışı ızgara görünümüyle** çalışmaya devam eder.
- **Zoom 3–22**: butonlar, kaydırıcı, tekerlek, `+` / `−` kısayolları, çift tıkla
  odaklı yakınlaştırma, `Ctrl` + tekerlek = hızlı adım.
- **Overzoom**: kaynak kendi çözünürlük sınırına gelince (Google 20, OSM/Esri 19)
  üst kare büyütülerek 22'ye kadar sorunsuz çalışır — boş kare/404 yok.
- **Parsel işlemleri**: 4 köşe girme, haritada çizim, sürükleme, ada/parsel arama ve
  vurgulama, **GeoJSON/CSV** içe-dışa aktarma.
- **Ölçüm araçları**: mesafe (m/km) ve alan (m²/da/hektar).
- **Koordinat dönüşümü**: WGS84 ↔ **TM3** (Türkiye 27–45 dilimleri, k₀=1,0) ve
  **UTM** (k₀=0,9996); `pyproj` kuruluysa yüksek doğruluklu dönüşüm kullanılır.

### 🌤️ İklim verisi
- **Şehir seçimi** (Türkiye il merkezleri) ve **7 bölgesel ön tanım** (Akdeniz, Ege,
  Karadeniz, GAP, Marmara, İç Anadolu, Doğu Anadolu).
- **12 aylık manuel düzenleme**: en yüksek/en düşük sıcaklık, nem, rüzgâr,
  güneşlenme süresi ve **yağış** — hücre bazlı Türkçe doğrulama ve uyarılar.
- **Open-Meteo** (anahtar gerekmez, son 12 ay): `wind_speed_10m_mean` m/s olarak
  alınır, 10 m → 2 m düzeltmesi (×0,75) uygulanır; mean alanı yoksa max'a düşer.

### 📄 Raporlar ve arayüz
- **HTML, CSV, PDF, DOCX, XLSX** dışa aktarma.
- **Kurumsal başlık**: logo, kurum adı, imza alanı (`data/config.json`).
- **Fıstık yeşili tema** (`app/theme.py`), tam **Türkçe** arayüz, 5 ana sayfa.
- Veritabanı ve raporlar **exe'nin yanına** yazılır → USB bellekle taşınabilir.

---

## 🔧 Kurulum

**Gereksinimler:** Python 3.11+ (3.14 ile de test edilmiştir), Windows / Linux.

```bash
# 1) Depoyu indir
git clone https://github.com/kagnx/BitkiSuTuketimi.git
cd BitkiSuTuketimi

# 2) Sanal ortam (önerilir)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# 3) Bağımlılıklar
pip install -r requirements.txt

# 4) Çalıştır
python main.py
```

`requirements.txt`: `PyQt6>=6.6.0`, `requests>=2.31.0`

**İsteğe bağlı (ek rapor formatları ve testler):**

```bash
pip install -r requirements-dev.txt   # DOCX (reportlab) + XLSX (openpyxl) + pytest
```

Bu paketler kurulu değilse uygulama sorunsuz çalışır; yalnızca DOCX/XLSX butonları
anlaşılır bir uyarı gösterir.

---

## 🧮 Hesap Yöntemi

```text
İklim verisi (manuel / bölgesel / Open-Meteo)
        │
        ▼
monthly_eto()  ──►  12 aylık ETo   (Penman-Monteith  |  Hargreaves-Samani)
        │
        ▼
Kc eğrisi (4 evre, iklim düzeltmeli)  ──►  ETc
        │
        ▼
Etkili yağış (USDA-SCS / FAO)         ──►  Net & brüt su ihtiyacı
        │
        ▼
Gün gün kök bölgesi su bakiyesi (kova modeli)
        │
        ▼
Sulama aralığı (MAD × toprak × kök derinliği) + su stresi skoru + öneriler
        │
        ▼
Rapor: HTML / CSV / PDF / DOCX / XLSX
```

Ayrıntılar için [FAO-56](https://www.fao.org/3/x0490e/x0490e00.htm)
(Irrigation and Drainage Paper 56, 1998) kaynağına bakınız.

---

## 📊 Raporlar

| Format | İçerik |
|---|---|
| **HTML** | Kurumsal başlık/logo/imza, SVG su dengesi grafiği, aylık döküm, gelişim evresi, su stresi skoru, sulama önerisi, kök bölgesi stratejisi, tuzluluk |
| **CSV** | Aylık düz veri (tablo uygulamaları için) |
| **PDF** | Qt yazıcı motoruyla A4 çıktı |
| **DOCX** | `reportlab` ile başlıklı, renk kodlu risk bölümleri ve KPI tablosu |
| **XLSX** | `openpyxl` ile biçimlendirilmiş çalışma kitabı (aylık döküm + risk tabloları) |

Kurumsal ayarlar `data/config.json` dosyasından (uygulama içinden veya elle)
düzenlenebilir.

---

## 📦 Tek Exe (kurulum gerektirmeyen dağıtım)

```bash
pip install pyinstaller
build_exe.bat         # Windows
# bash build_exe.sh   # Linux
```

Çıktı: **`dist/ProSU.exe`** (~52 MB) — Python kurulu olmayan bilgisayarda çalışır.
İlk açılışta **305 bitkili** veritabanı otomatik oluşturulur; yeni sürümde eklenen
bitkiler mevcut veritabanına eksiksiz eklenir (kullanıcı düzenlemeleri korunur).

> Harita için internet gerekir; olmadığında ızgara görünümüyle çalışır. TAKBİS'e
> doğrudan erişim bulunmadığından ada/parsel sorguları, uygulamaya aktardığınız
> (GeoJSON/CSV) veya haritada çizdiğiniz parseller üzerinde çalışır.

---

## 🧪 Testler

24 test — hepsi CI'da her commit'te koşar.

```bash
pip install -r requirements-dev.txt

python -m pytest tests/ -v        # birim + regresyon (24 test)
python tests/smoke_test.py        # hesap, DB, koordinat, UI, harita
python tests/visual_check.py      # tema renkleri + 6 sayfa render
```

| Dosya | Kapsam |
|---|---|
| `test_u2_eto.py` | **ETo regresyonu** (Konya taban değerleri ±0,05 mm/gün), rüzgâr birimi (m/s vs km/h), Open-Meteo `mean`/`max` alanları, canlı API (ağ yoksa `skip`) |
| `test_climate_dialog.py` | İklim düzenleme diyaloğu: 7 kolon, boş/geçersiz hücrede **çökme yok**, nem aralığı, Tmax ≥ Tmin, kısmi güncelleme engeli |
| `test_map_zoom.py` | Zoom sınırları (3–22), katman native sınırları, **overzoom** indirme tutturma, ata kare matematiği |
| `test_measure_crash.py` | Ölçüm aracı çökmesi regresyonu (`setBrush` hatası), ekstrem zoom koordinatları, piksel ↔ derece round-trip |
| `smoke_test.py` | Uçtan uca: hesap → rapor → DB → koordinat → UI → harita |
| `visual_check.py` | Temanın gerçekten uygulanması, sayfaların render olması, önizleme PNG üretimi |

Testler başsız ortamda koşar (`QT_QPA_PLATFORM=offscreen`), sanal ekran gerektirmez.

---

## 📁 Proje Yapısı

```text
main.py                     # giriş noktası (QApplication)
app/
  main_window.py            # ana pencere, 5 sayfa, arka plan iş parçacıkları
  calculations.py           # ETo, Kc eğrisi, su dengesi, stres skoru (hesap motoru)
  climate.py                # iklim verisi: manuel + bölgesel + Open-Meteo
  compare.py                # bitki karşılaştırma diyaloğu
  coords.py                 # WGS84 <-> TM3 / UTM dönüşümleri, alan & mesafe
  database.py               # SQLite: bitkiler + parseller, şema migrasyonu
  dialogs.py                # bitki / iklim / koordinat / parsel diyalogları
  mapwidget.py              # OSM harita, karo katmanı, çizim, ölçüm, zoom
  plants_data.py            # FAO-56 bitki veri seti (305 bitki)
  report.py                 # HTML / CSV / DOCX / XLSX rapor üretimi
  pdfexport.py              # HTML -> PDF (QTextDocument + QPrinter)
  config.py                 # kurumsal rapor ayarları (data/config.json)
  paths.py                  # exe / kaynak çalıştırmaya göre veri klasörleri
  theme.py                  # fıstık yeşili QSS teması
tests/                      # 24 pytest testi + smoke + visual_check
assets/                     # uygulama ikonu (icon.ico / icon.png)
.github/workflows/ci.yml    # test + tek exe derleme (CI)
ProSU.spec                  # PyInstaller tanımı
build_exe.bat / build_exe.sh
LICENSE                     # MIT lisans
THIRD_PARTY_NOTICES.md      # FAO-56 / Open-Meteo / OSM lisans koşulları
requirements.txt            # çalışma zamanı bağımlılıkları
requirements-dev.txt        # test + ek rapor formatları
```

Çalışma zamanında oluşturulan klasörler (`data/`, `raporlar/`, `tile_cache/`,
`dist/`, `build/`) sürüm kontrolünde değildir — bkz. `.gitignore`.

---

## 📜 Veri Notları ve Lisans

**Lisans:** [MIT](LICENSE) © 2026 Oğuz Kaan FIRAT

Kod MIT lisanslıdır. Kullanılan **üçüncü taraf veri ve hizmetlerin** (FAO-56,
Open-Meteo, OSM, Esri/Google) lisans koşulları ayrıca belgelenmiştir:
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

| Kaynak | Kullanım | Lisans |
|---|---|---|
| **FAO-56** — Crop Evapotranspiration (1998) | Kc katsayıları, evre süreleri, kök derinliği | Kamu malı; serbest çoğaltılabilir |
| **Open-Meteo** | Çalışma zamanında geçmiş iklim verisi | CC BY 4.0 — *Weather data by Open-Meteo.com* |
| **OpenStreetMap** | Harita karoları | ODbL — © OpenStreetMap katkıcıları |
| **Esri / Google** (isteğe bağlı katman) | Alternatif harita karoları | Sağlayıcı koşulları geçerlidir; karolar yalnızca yerelde önbelleğe alınır |

- Kaynağı **"Tahmini"** olarak işaretli bitkilerin değerleri FAO-56'daki benzer
  türlere dayanır; yerel literatürle doğrulanmadan kullanılmamalıdır.
- Bu değerler Bitki Veritabanı sayfasından düzenlenebilir.

---

## 🤝 Katkıda Bulunma

1. Fork'layın, özellik dalı açın: `git checkout -b feat/yenilik`
2. Testleri çalıştırın: `python -m pytest tests/ -v`
3. Anlamlı bir commit mesajı yazın (ne + neden)
4. Pull request açın — CI'nın yeşil olması gerekir

Hata bildirimlerinde lütfen Python sürümünüzü, adımları ve mümkünse hata mesajını
ekleyin.

---

**ProSU** — sulama planlamasını veriyle yapın. 🌱



