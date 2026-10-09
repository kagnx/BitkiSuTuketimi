# Üçüncü Taraf Veri ve Lisans Bildirimleri

Bu dosya, **ProSU** kod tabanının (MIT — bkz. [`LICENSE`](LICENSE)) kullandığı
dış kaynaklı veri ve hizmetlerin lisans koşullarını belgeler. MIT lisansı yalnızca
bu depodaki kaynak koda uygulanır.

| Kaynak | ProSU'daki kullanımı | Lisans / koşul |
|---|---|---|
| **FAO-56** — *Crop Evapotranspiration: Guidelines for computing crop water requirements*, FAO Irrigation and Drainage Paper 56 (1998) | Kc katsayıları, büyüme evresi süreleri, etkili kök derinliği (`app/plants_data.py`) | FAO yayınları kamu malıdır, kaynak gösterilerek serbestçe çoğaltılabilir |
| **Open-Meteo** | Çalışma zamanında son 12 ayın geçmiş günlük iklim verisi (`app/climate.py`) | **CC BY 4.0** — atıf: *Weather data by Open-Meteo.com* |
| **OpenStreetMap** | Varsayılan harita karo katmanı (`app/mapwidget.py`) | **ODbL** — © OpenStreetMap katkıcıları |
| **Esri / Google** (isteğe bağlı katman) | Alternatif harita karo kaynakları | Sağlayıcı hizmet koşulları geçerlidir; karolar **yalnızca yerelde önbelleğe alınır**, proje tarafından dağıtılmaz |

## Ayrıntılar

### FAO-56
Bitki veri setindeki evapotranspirasyon katsayıları ve gelişim evresi uzunlukları
FAO-56 tablolarından alınmıştır. Kaynağı **"Tahmini"** olarak işaretlenen
değerler, FAO-56'daki benzer türlere dayanan yerel literatür tahminleridir;
doğrulanmadan kritik kararlarda kullanılmamalıdır. Bu değerler uygulamanın
Bitki Veritabanı sayfasından düzenlenebilir.

### Open-Meteo
Uygulama, kullanıcının belirttiği koordinat için geçmiş günlük sıcaklık, nem,
rüzgâr, güneşlenme süresi ve yağış verilerini [open-meteo.com](https://open-meteo.com)
üzerinden çeker (API anahtarı gerekmez). Rüzgâr hızı `wind_speed_10m_mean`
(m/s) olarak istenir ve 10 m → 2 m dönüşümü için ×0,75 çarpanı uygulanır.

Open-Meteo'yu kullanan türev çalışmalarda şu atıf yapılmalıdır:
*Weather data by [Open-Meteo.com](https://open-meteo.com)* (CC BY 4.0).

### Harita karoları
Karolar çalışma anında indirilir ve `tile_cache/` klasöründe yerelde saklanır;
bu önbellek yalnızca uygulamanın kendi çalışması içindir, yeniden dağıtım
amaçlanmaz. Uygulama çevrimdışı olduğunda karo yerine enlem/boylam ızgarası
çizilir.

---

MIT lisansının tam metni: [`LICENSE`](LICENSE)
