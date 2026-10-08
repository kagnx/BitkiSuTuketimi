# -*- coding: utf-8 -*-
"""
Türkiye'de yetiştirilen bitki türlerinin su ihtiyacı hesabı için temel veri seti.

Kc (bitki katsayısı) değerleri ağırlıklı olarak FAO-56 (Crop Evapotranspiration)
dokümanındaki tablo değerlerine dayanır; kaynağı belirtilmemiş olanlar bölgesel
tarım literatürü esas alınarak verilmiş makul tahminlerdir ve uygulama içinden
düzenlenebilir.

Kc değerleri: kc_ini (başlangıç), kc_mid (orta sezon), kc_end (sezon sonu)
Evre süreleri (gün): L_ini, L_dev, L_mid, L_late
boy   : bitki boyu (m) — FAO-56 kc düzeltmesi için
kok   : etkili kök derinliği (m) — sulama aralığı hesabı için
ekim_ay: varsayılan dikim/ekim ayı (1-12)
sira / sira_arasi: sıra arası ve sıra üzeri mesafe (m) — ağaç/meyve için
"""

KATEGORILER = [
    "Sebze",
    "Meyve",
    "Tarla Bitkisi",
    "Süs Bitkisi",
    "Tıbbi ve Aromatik Bitki",
    "Endüstri Bitkisi",
    "Ağaç (Orman / Süs)",
]

B = {
    "Sebze": [],
    "Meyve": [],
    "Tarla Bitkisi": [],
    "Süs Bitkisi": [],
    "Tıbbi ve Aromatik Bitki": [],
    "Endüstri Bitkisi": [],
    "Ağaç (Orman / Süs)": [],
}


# Belirli bitkiler için açıkça tanımlanmış kritik dönem override'ları (ad -> (ad, merkez))
OVERRIDE = {}

# Kategori bazlı varsayılan kritik dönem (su stresine en duyarlı evre)
# kritik_merkez: sezon uzunluğunun yüzdesi (0.0-1.0) olarak dönem merkezi
KRITIK_DEFAULT = {
    "Sebze": ("Çiçeklenme / Meyve Tutumu", 0.55),
    "Meyve": ("Çiçeklenme / Meyve Tutumu", 0.30),
    "Tarla Bitkisi": ("Başaklanma / Çiçeklenme", 0.55),
    "Süs Bitkisi": ("Çiçeklenme", 0.50),
    "Tıbbi ve Aromatik Bitki": ("Çiçeklenme", 0.50),
    "Endüstri Bitkisi": ("Çiçeklenme", 0.55),
    "Ağaç (Orman / Süs)": ("Yaprak Açımı / Çiçeklenme", 0.30),
}


# ---- Tuz toleransı (ECe, dS/m) ----
# FAO Ayers & Westcot (1985, Irrigation and Drainage Paper 29) ve FAO-56
# eklerindeki bitki tuz toleransı eşikleri esas alınmıştır. ECe, verim düşüşünün
# başladığı toprak tuzluluğudur (dS/m).
TUZ_ECE_KATEGORI = {
    "Sebze": 1.5,
    "Meyve": 1.7,
    "Tarla Bitkisi": 3.0,
    "Süs Bitkisi": 2.0,
    "Tıbbi ve Aromatik Bitki": 3.0,
    "Endüstri Bitkisi": 5.0,
    "Ağaç (Orman / Süs)": 2.0,
}

# Bitki adı alt-dizisine göre eşik override'ları (ilk eşleşen geçerli)
TUZ_ECE_ALT = [
    ("fasulye", 1.0), ("havuç", 1.0), ("çilek", 1.0), ("soğan", 1.2),
    ("marul", 1.3), ("biberiye", 2.5), ("biber", 1.5), ("patlıcan", 1.5),
    ("hıyar", 2.5), ("domates", 2.5), ("kabak", 3.2), ("kavun", 2.2),
    ("karpuz", 2.0), ("brokoli", 2.8), ("lahana", 1.8), ("bezelye", 1.5),
    ("buğday", 6.0), ("arpa", 8.0), ("mısır", 1.7), ("çeltik", 3.0),
    ("nohut", 1.8), ("mercimek", 1.8), ("ayçiçeği", 1.7), ("soya", 5.0),
    ("yonca", 2.0), ("pamuk", 7.7), ("pancar", 7.0), ("tütün", 1.7),
    ("susam", 1.7), ("sorgum", 6.8), ("yer fıstığı", 3.2),
    ("antep fıstığı", 4.0), ("zeytin", 3.0), ("üzüm", 1.5), ("elma", 1.7),
    ("armut", 1.7), ("kiraz", 1.5), ("vişne", 1.5), ("erik", 1.5),
    ("kayısı", 1.6), ("şeftali", 1.7), ("nektarin", 1.7), ("badem", 1.5),
    ("ceviz", 1.7), ("fındık", 1.5), ("incir", 1.8), ("portakal", 1.7),
    ("limon", 1.7), ("mandalina", 1.7), ("greyfurt", 1.7),
]


def bitki_tuz_esik(ad, kategori):
    """Bitki adı ve kategorisine göre tuz toleransı eşiği (ECe, dS/m)."""
    a = (ad or "").lower()
    for alt, ece in TUZ_ECE_ALT:
        if alt in a:
            return ece
    return TUZ_ECE_KATEGORI.get(kategori, 2.0)


def P(ad, latin, kat, kc_ini, kc_mid, kc_end, li, ld, lm, ll, boy=1.0, kok=0.7,
      ekim_ay=4, sira=None, sira_arasi=None, kaynak="FAO-56", aciklama="",
      kritik_ad=None, kritik_merkez=None):
    explicit = kritik_ad is not None or kritik_merkez is not None
    if kritik_ad is None or kritik_merkez is None:
        ka, km = KRITIK_DEFAULT.get(kat, ("Çiçeklenme", 0.50))
        kritik_ad = kritik_ad or ka
        if kritik_merkez is None:
            kritik_merkez = km
    if explicit:
        OVERRIDE[ad] = (kritik_ad, kritik_merkez)
    B[kat].append({
        "ad": ad, "latin": latin, "kategori": kat,
        "kc_ini": kc_ini, "kc_mid": kc_mid, "kc_end": kc_end,
        "L_ini": li, "L_dev": ld, "L_mid": lm, "L_late": ll,
        "boy": boy, "kok": kok, "ekim_ay": ekim_ay,
        "sira": sira, "sira_arasi": sira_arasi,
        "kaynak": kaynak, "aciklama": aciklama,
        "kritik_ad": kritik_ad, "kritik_merkez": kritik_merkez,
    })


# ============================== SEBZELER ==============================
P("Domates (Tarla)", "Solanum lycopersicum", "Sebze", 0.6, 1.15, 0.8, 30, 40, 40, 25, boy=1.0, kok=0.7, ekim_ay=4, aciklama="Sırık/yer domatesi, tarla üretimi")
P("Domates (Sera)", "Solanum lycopersicum", "Sebze", 0.6, 1.05, 0.9, 30, 40, 60, 25, boy=1.5, kok=0.7, ekim_ay=3, aciklama="Örtü altı üretim, sera içi Kc daha düşüktür")
P("Biber (Dolmalık/Kapya)", "Capsicum annuum", "Sebze", 0.6, 1.05, 0.9, 30, 40, 40, 20, boy=0.7, kok=0.6, ekim_ay=4, aciklama="Tarla biberi")
P("Patlıcan", "Solanum melongena", "Sebze", 0.6, 1.05, 0.9, 30, 40, 40, 25, boy=0.8, kok=0.6, ekim_ay=4)
P("Hıyar / Salatalık", "Cucumis sativus", "Sebze", 0.6, 1.0, 0.75, 25, 35, 50, 20, boy=0.4, kok=0.5, ekim_ay=4)
P("Karpuz", "Citrullus lanatus", "Sebze", 0.4, 1.0, 0.75, 20, 30, 40, 20, boy=0.3, kok=0.8, ekim_ay=4)
P("Kavun", "Cucumis melo", "Sebze", 0.5, 1.05, 0.75, 30, 40, 40, 20, boy=0.3, kok=0.8, ekim_ay=4)
P("Kabak (Sakız/Yazlık)", "Cucurbita pepo", "Sebze", 0.5, 0.95, 0.75, 25, 35, 40, 20, boy=0.4, kok=0.6, ekim_ay=4)
P("Balkabağı (Helvacıkabağı)", "Cucurbita moschata", "Sebze", 0.5, 1.0, 0.8, 20, 40, 40, 20, boy=0.4, kok=0.8, ekim_ay=5, kaynak="Tahmini")
P("Domates (Salçalık)", "Solanum lycopersicum", "Sebze", 0.6, 1.15, 0.8, 30, 40, 50, 25, boy=0.8, kok=0.7, ekim_ay=4, aciklama="Bursa/Balıkesir salçalık üretimi")
P("Soğan (Kuru)", "Allium cepa", "Sebze", 0.7, 1.05, 0.75, 15, 25, 70, 40, boy=0.4, kok=0.5, ekim_ay=3)
P("Soğan (Yeşil)", "Allium cepa", "Sebze", 0.7, 1.0, 0.75, 15, 20, 40, 20, boy=0.3, kok=0.4, ekim_ay=3)
P("Sarımsak", "Allium sativum", "Sebze", 0.7, 1.0, 0.7, 25, 30, 50, 35, boy=0.5, kok=0.5, ekim_ay=10, aciklama="Sonbahar ekimi")
P("Pırasa", "Allium porrum", "Sebze", 0.7, 1.0, 0.95, 30, 40, 50, 35, boy=0.5, kok=0.5, ekim_ay=3)
P("Havuç", "Daucus carota", "Sebze", 0.7, 1.05, 0.95, 20, 30, 50, 30, boy=0.4, kok=0.6, ekim_ay=4)
P("Turp", "Raphanus sativus", "Sebze", 0.6, 0.9, 0.8, 10, 15, 20, 10, boy=0.3, kok=0.4, ekim_ay=3, kaynak="Tahmini")
P("Lahana (Beyaz)", "Brassica oleracea var. capitata", "Sebze", 0.7, 1.05, 0.95, 25, 35, 50, 25, boy=0.5, kok=0.6, ekim_ay=3)
P("Karnabahar", "Brassica oleracea var. botrytis", "Sebze", 0.7, 1.05, 0.95, 25, 35, 50, 20, boy=0.5, kok=0.6, ekim_ay=3)
P("Brokoli", "Brassica oleracea var. italica", "Sebze", 0.7, 1.05, 0.95, 25, 35, 50, 20, boy=0.5, kok=0.6, ekim_ay=3)
P("Marul (Kıvırcık)", "Lactuca sativa", "Sebze", 0.7, 1.0, 0.95, 20, 30, 15, 10, boy=0.3, kok=0.3, ekim_ay=3)
P("Ispanak", "Spinacia oleracea", "Sebze", 0.7, 1.0, 0.95, 20, 20, 25, 10, boy=0.3, kok=0.4, ekim_ay=3)
P("Maydanoz", "Petroselinum crispum", "Sebze", 0.7, 1.0, 0.9, 20, 30, 40, 20, boy=0.3, kok=0.4, ekim_ay=3, kaynak="Tahmini")
P("Taze Fasulye", "Phaseolus vulgaris", "Sebze", 0.5, 1.05, 0.9, 20, 30, 40, 20, boy=0.4, kok=0.5, ekim_ay=4)
P("Kuru Fasulye", "Phaseolus vulgaris", "Sebze", 0.4, 1.15, 0.35, 20, 30, 40, 20, boy=0.5, kok=0.6, ekim_ay=5)
P("Bezelye", "Pisum sativum", "Sebze", 0.5, 1.15, 1.0, 20, 30, 35, 15, boy=0.6, kok=0.5, ekim_ay=3)
P("Bamya", "Abelmoschus esculentus", "Sebze", 0.35, 1.1, 0.9, 25, 35, 45, 25, boy=0.8, kok=0.7, ekim_ay=5, kaynak="Tahmini")
P("Enginar", "Cynara cardunculus", "Sebze", 0.5, 1.0, 0.95, 25, 35, 60, 40, boy=1.0, kok=0.8, ekim_ay=9)
P("Kuşkonmaz", "Asparagus officinalis", "Sebze", 0.5, 0.95, 0.3, 25, 35, 50, 40, boy=1.2, kok=1.0, ekim_ay=4)
P("Kereviz", "Apium graveolens", "Sebze", 0.7, 1.05, 0.95, 25, 40, 45, 20, boy=0.4, kok=0.5, ekim_ay=4)
P("Pancar (Kırmızı)", "Beta vulgaris", "Sebze", 0.5, 1.1, 0.95, 15, 25, 50, 20, boy=0.4, kok=0.6, ekim_ay=4)
P("Şalgam", "Brassica rapa", "Sebze", 0.5, 1.1, 0.95, 15, 20, 40, 15, boy=0.4, kok=0.5, ekim_ay=4)
P("Roka", "Eruca sativa", "Sebze", 0.7, 1.0, 0.9, 10, 15, 10, 5, boy=0.2, kok=0.3, ekim_ay=3, kaynak="Tahmini")
P("Çerezlik Kabak Çekirdeği", "Cucurbita pepo", "Sebze", 0.5, 0.95, 0.7, 25, 35, 40, 20, boy=0.4, kok=0.6, ekim_ay=4, kaynak="Tahmini", aciklama="Nevşehir/Kayseri çerezlik kabak")

# ============================== MEYVELER ==============================
P("Elma", "Malus domestica", "Meyve", 0.95, 1.2, 0.75, 30, 70, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=2, aciklama="Örtülü topraklı bahçe (FAO-56)", kritik_ad="Çiçeklenme / Meyve Tutumu", kritik_merkez=0.25)
P("Elma (Örtüsüz Toprak)", "Malus domestica", "Meyve", 0.7, 1.15, 0.45, 30, 70, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=2, aciklama="Çıplak topraklı klasik bahçe")
P("Armut", "Pyrus communis", "Meyve", 0.95, 1.15, 0.75, 30, 70, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=2)
P("Ayva", "Cydonia oblonga", "Meyve", 0.8, 1.1, 0.8, 30, 60, 90, 30, boy=2.5, kok=1.0, ekim_ay=3, sira=4, sira_arasi=3, kaynak="Tahmini")
P("Kiraz", "Prunus avium", "Meyve", 0.95, 1.15, 0.8, 30, 70, 90, 30, boy=3.5, kok=1.2, ekim_ay=3, sira=5, sira_arasi=3, aciklama="Sert çekirdekli; Akdeniz geçit bölgesi")
P("Vişne", "Prunus cerasus", "Meyve", 0.95, 1.1, 0.8, 30, 60, 90, 30, boy=3.0, kok=1.0, ekim_ay=3, sira=4, sira_arasi=3, kaynak="Tahmini")
P("Şeftali", "Prunus persica", "Meyve", 0.9, 1.15, 0.65, 30, 60, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=3)
P("Nektarin", "Prunus persica var. nucipersica", "Meyve", 0.9, 1.15, 0.65, 30, 60, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=3)
P("Kayısı", "Prunus armeniaca", "Meyve", 0.8, 1.15, 0.85, 30, 60, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=3, aciklama="Malatya kayısısı")
P("Erik", "Prunus domestica", "Meyve", 0.8, 1.15, 0.75, 30, 60, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=3)
P("Ceviz", "Juglans regia", "Meyve", 0.6, 1.1, 0.65, 20, 60, 90, 30, boy=8.0, kok=1.5, ekim_ay=3, sira=10, sira_arasi=10, aciklama="Kapama ceviz bahçesi")
P("Badem", "Prunus dulcis", "Meyve", 0.4, 0.9, 0.6, 20, 60, 90, 30, boy=5.0, kok=1.5, ekim_ay=3, sira=6, sira_arasi=4)
P("Fındık", "Corylus avellana", "Meyve", 0.7, 0.9, 0.7, 30, 70, 90, 30, boy=4.0, kok=1.0, ekim_ay=3, sira=5, sira_arasi=4, kaynak="Tahmini", aciklama="Ordu/Giresun karadeniz fındığı")
P("Antep Fıstığı", "Pistacia vera", "Meyve", 0.5, 0.9, 0.55, 20, 60, 90, 30, boy=4.0, kok=1.5, ekim_ay=3, sira=7, sira_arasi=7, aciklama="Kurağa dayanıklı; GAÜ/Şanlıurfa")
P("Zeytin", "Olea europaea", "Meyve", 0.65, 0.7, 0.6, 30, 90, 60, 30, boy=4.0, kok=1.2, ekim_ay=3, sira=6, sira_arasi=6, aciklama="%40 örtülü toprak; zeytin az su ister")
P("Nar", "Punica granatum", "Meyve", 0.6, 1.1, 0.55, 20, 60, 90, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=4, sira_arasi=3, aciklama="Çukurova/Ege narı")
P("İncir", "Ficus carica", "Meyve", 0.6, 1.0, 0.6, 30, 60, 90, 30, boy=4.0, kok=1.2, ekim_ay=3, sira=6, sira_arasi=5, kaynak="Tahmini", aciklama="Aydın kuru inciri")
P("Portakal", "Citrus sinensis", "Meyve", 0.7, 0.65, 0.7, 30, 80, 100, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=5, sira_arasi=5, aciklama="%70 taç örtüsü (narenciye)")
P("Limon", "Citrus limon", "Meyve", 0.75, 0.7, 0.75, 30, 80, 100, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=5, sira_arasi=5)
P("Mandalina", "Citrus reticulata", "Meyve", 0.7, 0.65, 0.7, 30, 80, 100, 30, boy=3.0, kok=1.2, ekim_ay=3, sira=5, sira_arasi=5)
P("Greyfurt", "Citrus paradisi", "Meyve", 0.7, 0.65, 0.7, 30, 80, 100, 30, boy=3.5, kok=1.2, ekim_ay=3, sira=5, sira_arasi=5)
P("Üzüm (Sofralık/Şaraplık)", "Vitis vinifera", "Meyve", 0.3, 0.85, 0.45, 20, 50, 75, 30, boy=2.0, kok=1.0, ekim_ay=4, sira=3, sira_arasi=2, aciklama="Bağ; Ege/İç Anadolu", kritik_ad="Çiçeklenme / Koruk Dönemi", kritik_merkez=0.35)
P("Çilek", "Fragaria × ananassa", "Meyve", 0.4, 0.85, 0.75, 20, 25, 35, 15, boy=0.3, kok=0.3, ekim_ay=4, sira=1.2, sira_arasi=0.3, aciklama="Malçlı yüksek yastık üretimi")
P("Muz", "Musa acuminata", "Meyve", 0.5, 1.2, 1.0, 30, 60, 120, 60, boy=3.0, kok=0.8, ekim_ay=3, sira=3, sira_arasi=2, aciklama="Anamur/Alanya örtü altı muz")
P("Kivi", "Actinidia deliciosa", "Meyve", 0.4, 1.1, 0.95, 30, 60, 90, 30, boy=3.0, kok=1.0, ekim_ay=3, sira=4, sira_arasi=3, aciklama="Karadeniz sahil kivisi")
P("Trabzon Hurması", "Diospyros kaki", "Meyve", 0.6, 1.0, 0.6, 30, 60, 90, 30, boy=4.0, kok=1.2, ekim_ay=3, sira=5, sira_arasi=4, kaynak="Tahmini")
P("Yeni Dünya (Malta Eriği)", "Eriobotrya japonica", "Meyve", 0.6, 1.0, 0.7, 30, 60, 90, 30, boy=4.0, kok=1.0, ekim_ay=3, sira=5, sira_arasi=4, kaynak="Tahmini")
P("Avokado", "Persea americana", "Meyve", 0.6, 0.85, 0.75, 30, 60, 90, 30, boy=5.0, kok=1.0, ekim_ay=3, sira=5, sira_arasi=5, aciklama="Alanya/Antalya sahil kuşağı")
P("Kuşburnu", "Rosa canina", "Meyve", 0.6, 0.9, 0.7, 20, 50, 90, 30, boy=2.0, kok=1.0, ekim_ay=11, sira=2, sira_arasi=1.5, kaynak="Tahmini", aciklama="Gümüşhane/Bayburt kuşburnu bahçesi")
P("Kızılcık", "Cornus mas", "Meyve", 0.6, 0.9, 0.7, 20, 50, 80, 30, boy=3.0, kok=1.0, ekim_ay=3, sira=4, sira_arasi=3, kaynak="Tahmini")
P("Karadut", "Morus nigra", "Meyve", 0.7, 0.95, 0.7, 20, 50, 90, 30, boy=5.0, kok=1.2, ekim_ay=3, sira=5, sira_arasi=5, kaynak="Tahmini")
P("Böğürtlen", "Rubus fruticosus", "Meyve", 0.6, 0.95, 0.7, 20, 40, 60, 30, boy=1.5, kok=0.6, ekim_ay=3, sira=2, sira_arasi=1, kaynak="Tahmini")
P("Ahududu", "Rubus idaeus", "Meyve", 0.6, 0.95, 0.7, 20, 40, 60, 30, boy=1.5, kok=0.6, ekim_ay=3, sira=2, sira_arasi=0.5, kaynak="Tahmini")
P("Yaban Mersini (Likapa)", "Vaccinium corymbosum", "Meyve", 0.7, 0.95, 0.8, 20, 40, 60, 30, boy=1.5, kok=0.5, ekim_ay=3, sira=2, sira_arasi=1, kaynak="Tahmini", aciklama="Asitli toprak; Karadeniz")

# ============================== TARLA BİTKİLERİ ==============================
P("Buğday (Kışlık)", "Triticum aestivum", "Tarla Bitkisi", 0.7, 1.15, 0.4, 20, 60, 60, 40, boy=0.9, kok=1.2, ekim_ay=10, aciklama="İç Anadolu kışlık ekmeklik", kritik_ad="Başaklanma / Süt Olum", kritik_merkez=0.60)
P("Buğday (Yazlık)", "Triticum aestivum", "Tarla Bitkisi", 0.7, 1.15, 0.3, 20, 50, 60, 40, boy=0.9, kok=1.0, ekim_ay=3)
P("Arpa (Kışlık)", "Hordeum vulgare", "Tarla Bitkisi", 0.7, 1.15, 0.35, 20, 60, 60, 40, boy=0.8, kok=1.2, ekim_ay=10)
P("Çavdar", "Secale cereale", "Tarla Bitkisi", 0.7, 1.15, 0.3, 15, 30, 60, 40, boy=1.0, kok=1.2, ekim_ay=10)
P("Yulaf", "Avena sativa", "Tarla Bitkisi", 0.7, 1.15, 0.25, 20, 35, 60, 40, boy=0.9, kok=1.0, ekim_ay=10)
P("Tritikale", "×Triticosecale", "Tarla Bitkisi", 0.7, 1.15, 0.3, 20, 55, 60, 40, boy=1.0, kok=1.2, ekim_ay=10, kaynak="Tahmini")
P("Mısır (Dane)", "Zea mays", "Tarla Bitkisi", 0.3, 1.2, 0.35, 20, 40, 50, 30, boy=2.0, kok=1.0, ekim_ay=4, aciklama="Ana ürün dane mısır", kritik_ad="Tepe Püskülü / Koçan Olumu", kritik_merkez=0.60)
P("Mısır (Silajlık)", "Zea mays", "Tarla Bitkisi", 0.3, 1.2, 0.4, 25, 40, 50, 30, boy=2.0, kok=1.0, ekim_ay=4)
P("Mısır (Tatlı)", "Zea mays var. saccharata", "Tarla Bitkisi", 0.3, 1.15, 0.95, 20, 40, 50, 30, boy=1.8, kok=0.8, ekim_ay=4)
P("Çeltik (Pirinç)", "Oryza sativa", "Tarla Bitkisi", 1.05, 1.2, 0.9, 30, 30, 60, 30, boy=1.0, kok=0.6, ekim_ay=5, aciklama="Sulu (taşkın) çeltik", kritik_ad="Salkım Olumu", kritik_merkez=0.60)
P("Ayçiçeği", "Helianthus annuus", "Tarla Bitkisi", 0.35, 1.15, 0.35, 25, 35, 45, 25, boy=1.5, kok=1.2, ekim_ay=4, kritik_ad="Çiçeklenme (Tabla Oluşumu)", kritik_merkez=0.55)
P("Pamuk", "Gossypium hirsutum", "Tarla Bitkisi", 0.35, 1.15, 0.7, 30, 50, 60, 55, boy=1.2, kok=1.0, ekim_ay=5, aciklama="GAP/Çukurova pamuğu", kritik_ad="Çiçeklenme / Koza Olumu", kritik_merkez=0.50)
P("Şeker Pancarı", "Beta vulgaris var. altissima", "Tarla Bitkisi", 0.35, 1.2, 0.7, 25, 35, 60, 25, boy=0.5, kok=1.2, ekim_ay=4)
P("Soya", "Glycine max", "Tarla Bitkisi", 0.4, 1.15, 0.5, 20, 35, 60, 25, boy=0.9, kok=0.8, ekim_ay=5)
P("Yerfıstığı", "Arachis hypogaea", "Tarla Bitkisi", 0.4, 1.15, 0.6, 35, 35, 45, 25, boy=0.5, kok=0.6, ekim_ay=5)
P("Nohut", "Cicer arietinum", "Tarla Bitkisi", 0.4, 1.0, 0.35, 20, 30, 60, 40, boy=0.5, kok=1.0, ekim_ay=3, aciklama="Kuru koşul; kısmi sulama")
P("Mercimek (Kırmızı)", "Lens culinaris", "Tarla Bitkisi", 0.4, 1.1, 0.3, 20, 30, 60, 40, boy=0.4, kok=0.9, ekim_ay=3, aciklama="Güneydoğu Anadolu")
P("Susam", "Sesamum indicum", "Tarla Bitkisi", 0.35, 1.1, 0.25, 20, 30, 40, 20, boy=1.0, kok=0.9, ekim_ay=5)
P("Aspir (Yalancı Safran)", "Carthamus tinctorius", "Tarla Bitkisi", 0.35, 1.0, 0.25, 20, 35, 45, 25, boy=0.8, kok=1.2, ekim_ay=4, aciklama="Kurağa dayanıklı yağ bitkisi")
P("Kolza (Kanola)", "Brassica napus", "Tarla Bitkisi", 0.6, 1.15, 0.4, 25, 35, 45, 25, boy=1.2, kok=1.2, ekim_ay=10, aciklama="Kışlık kolza")
P("Yonca (Kuru Ot)", "Medicago sativa", "Tarla Bitkisi", 0.4, 1.2, 0.85, 10, 20, 30, 10, boy=0.8, kok=1.2, ekim_ay=4, aciklama="Tek biçim arası; sezonda çoklu biçim")
P("Yem Bitkisi (Fiğ)", "Vicia sativa", "Tarla Bitkisi", 0.4, 1.05, 0.85, 15, 20, 30, 10, boy=0.6, kok=0.8, ekim_ay=10)
P("Silajlık Sorgum", "Sorghum bicolor", "Tarla Bitkisi", 0.35, 1.0, 0.55, 20, 35, 45, 25, boy=2.0, kok=1.2, ekim_ay=5, kaynak="Tahmini")
P("Yem Pancarı", "Beta vulgaris", "Tarla Bitkisi", 0.35, 1.2, 0.7, 25, 35, 55, 25, boy=0.5, kok=1.0, ekim_ay=4, kaynak="Tahmini")
P("Kinoa", "Chenopodium quinoa", "Tarla Bitkisi", 0.5, 0.9, 0.4, 20, 30, 45, 25, boy=1.0, kok=0.9, ekim_ay=4, kaynak="Tahmini")
P("Mera / Çayır Otu", "Poaceae spp.", "Tarla Bitkisi", 0.4, 1.05, 0.85, 15, 20, 30, 15, boy=0.6, kok=0.8, ekim_ay=4, aciklama="Sulanan mera; otlatma amaçlı")

# ============================== SÜS BİTKİLERİ ==============================
P("Gül (Kesme Çiçek)", "Rosa hybrida", "Süs Bitkisi", 0.75, 0.95, 0.75, 20, 40, 60, 30, boy=1.0, kok=0.8, ekim_ay=4, kaynak="Tahmini")
P("Isparta Yağ Gülü", "Rosa damascena", "Süs Bitkisi", 0.6, 0.9, 0.6, 20, 40, 60, 30, boy=1.5, kok=0.8, ekim_ay=11, kaynak="Tahmini", aciklama="Gül yağı üretimi")
P("Karanfil", "Dianthus caryophyllus", "Süs Bitkisi", 0.75, 1.0, 0.8, 20, 40, 60, 30, boy=0.8, kok=0.5, ekim_ay=4, kaynak="Tahmini")
P("Lale", "Tulipa gesneriana", "Süs Bitkisi", 0.7, 1.0, 0.7, 15, 25, 40, 20, boy=0.4, kok=0.4, ekim_ay=10, kaynak="Tahmini")
P("Sümbül", "Hyacinthus orientalis", "Süs Bitkisi", 0.7, 0.9, 0.7, 15, 25, 40, 20, boy=0.3, kok=0.4, ekim_ay=10, kaynak="Tahmini")
P("Nergis", "Narcissus spp.", "Süs Bitkisi", 0.7, 0.9, 0.7, 15, 25, 40, 20, boy=0.3, kok=0.4, ekim_ay=10, kaynak="Tahmini")
P("Zambak (Lilyum)", "Lilium spp.", "Süs Bitkisi", 0.7, 1.0, 0.75, 20, 35, 50, 25, boy=0.8, kok=0.5, ekim_ay=4, kaynak="Tahmini")
P("Kasımpatı", "Chrysanthemum morifolium", "Süs Bitkisi", 0.7, 1.0, 0.75, 20, 35, 50, 25, boy=0.8, kok=0.5, ekim_ay=4, kaynak="Tahmini")
P("Gerbera", "Gerbera jamesonii", "Süs Bitkisi", 0.7, 1.05, 0.7, 20, 40, 60, 30, boy=0.5, kok=0.5, ekim_ay=4, kaynak="Tahmini")
P("Sardunya", "Pelargonium spp.", "Süs Bitkisi", 0.8, 1.0, 0.8, 20, 30, 50, 30, boy=0.4, kok=0.4, ekim_ay=4, kaynak="Tahmini")
P("Petunya", "Petunia hybrida", "Süs Bitkisi", 0.8, 1.0, 0.8, 15, 25, 45, 25, boy=0.3, kok=0.4, ekim_ay=4, kaynak="Tahmini")
P("Begonya", "Begonia spp.", "Süs Bitkisi", 0.8, 0.95, 0.8, 15, 25, 45, 25, boy=0.3, kok=0.3, ekim_ay=4, kaynak="Tahmini")
P("Çim (Soğuk İklim)", "Lolium/Festuca spp.", "Süs Bitkisi", 0.8, 1.0, 0.8, 10, 20, 30, 15, boy=0.1, kok=0.3, ekim_ay=4, aciklama="Park/bahçe çimi (çim karışımı)")
P("Çim (Sıcak İklim)", "Cynodon dactylon", "Süs Bitkisi", 0.6, 0.8, 0.6, 10, 20, 30, 15, boy=0.1, kok=0.4, ekim_ay=5, kaynak="Tahmini", aciklama="Bermuda çimi")
P("Açelya / Ormangülü", "Rhododendron spp.", "Süs Bitkisi", 0.8, 0.95, 0.8, 20, 40, 60, 30, boy=1.0, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Manolya", "Magnolia grandiflora", "Süs Bitkisi", 0.8, 1.0, 0.85, 20, 40, 70, 30, boy=6.0, kok=1.0, ekim_ay=4, kaynak="Tahmini")
P("Zakkum", "Nerium oleander", "Süs Bitkisi", 0.5, 0.75, 0.5, 20, 40, 60, 30, boy=3.0, kok=1.0, ekim_ay=4, kaynak="Tahmini", aciklama="Kurağa çok dayanıklı")
P("Çit Bitkisi (Ligustrum)", "Ligustrum vulgare", "Süs Bitkisi", 0.7, 0.9, 0.75, 20, 40, 60, 30, boy=2.0, kok=0.8, ekim_ay=4, kaynak="Tahmini")
P("Süs Kirazı", "Prunus serrulata", "Süs Bitkisi", 0.8, 1.0, 0.8, 20, 40, 70, 30, boy=4.0, kok=1.0, ekim_ay=4, kaynak="Tahmini")
P("Atatürk Çiçeği", "Euphorbia pulcherrima", "Süs Bitkisi", 0.8, 1.0, 0.8, 20, 40, 60, 30, boy=1.0, kok=0.6, ekim_ay=4, kaynak="Tahmini", aciklama="Sera süs bitkisi")

# ============================== TIBBİ VE AROMATİK ==============================
P("Lavanta", "Lavandula angustifolia", "Tıbbi ve Aromatik Bitki", 0.5, 0.8, 0.5, 30, 60, 90, 60, boy=0.7, kok=0.8, ekim_ay=4, kaynak="Tahmini", aciklama="Isparta/Burdur lavantası")
P("Adaçayı", "Salvia officinalis", "Tıbbi ve Aromatik Bitki", 0.5, 0.85, 0.5, 30, 60, 90, 60, boy=0.6, kok=0.8, ekim_ay=4, kaynak="Tahmini")
P("Kekik", "Thymus vulgaris", "Tıbbi ve Aromatik Bitki", 0.5, 0.9, 0.55, 30, 60, 90, 60, boy=0.4, kok=0.7, ekim_ay=4, kaynak="Tahmini", aciklama="Denizli/Manisa kekiği")
P("Mercanköşk", "Origanum vulgare", "Tıbbi ve Aromatik Bitki", 0.5, 0.85, 0.5, 30, 60, 90, 60, boy=0.4, kok=0.7, ekim_ay=4, kaynak="Tahmini")
P("Nane", "Mentha piperita", "Tıbbi ve Aromatik Bitki", 0.6, 1.1, 0.9, 20, 30, 40, 20, boy=0.5, kok=0.5, ekim_ay=4, aciklama="Suya duyarlı; çoklu biçim")
P("Fesleğen", "Ocimum basilicum", "Tıbbi ve Aromatik Bitki", 0.6, 1.05, 0.85, 20, 30, 40, 20, boy=0.5, kok=0.5, ekim_ay=5, kaynak="Tahmini")
P("Papatya", "Matricaria chamomilla", "Tıbbi ve Aromatik Bitki", 0.6, 0.9, 0.6, 20, 30, 40, 20, boy=0.4, kok=0.6, ekim_ay=10, kaynak="Tahmini")
P("Anason", "Pimpinella anisum", "Tıbbi ve Aromatik Bitki", 0.6, 1.0, 0.6, 20, 30, 40, 20, boy=0.5, kok=0.7, ekim_ay=4, kaynak="Tahmini")
P("Rezene", "Foeniculum vulgare", "Tıbbi ve Aromatik Bitki", 0.6, 1.0, 0.9, 25, 35, 45, 25, boy=0.8, kok=0.7, ekim_ay=4, kaynak="Tahmini")
P("Kişniş", "Coriandrum sativum", "Tıbbi ve Aromatik Bitki", 0.6, 0.95, 0.6, 20, 30, 40, 20, boy=0.6, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Dereotu", "Anethum graveolens", "Tıbbi ve Aromatik Bitki", 0.7, 0.95, 0.7, 15, 25, 30, 15, boy=0.5, kok=0.5, ekim_ay=4, kaynak="Tahmini")
P("Biberiye", "Rosmarinus officinalis", "Tıbbi ve Aromatik Bitki", 0.5, 0.85, 0.5, 30, 60, 90, 60, boy=0.8, kok=0.8, ekim_ay=4, kaynak="Tahmini")
P("Oğulotu (Melisa)", "Melissa officinalis", "Tıbbi ve Aromatik Bitki", 0.6, 1.0, 0.7, 20, 40, 60, 30, boy=0.6, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Sarı Kantaron", "Hypericum perforatum", "Tıbbi ve Aromatik Bitki", 0.6, 0.85, 0.6, 20, 40, 60, 30, boy=0.5, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Meyan Kökü", "Glycyrrhiza glabra", "Tıbbi ve Aromatik Bitki", 0.8, 1.1, 0.9, 30, 60, 90, 60, boy=1.0, kok=1.2, ekim_ay=4, kaynak="Tahmini", aciklama="Suyu seven; GAP bölgesi")
P("Safran", "Crocus sativus", "Tıbbi ve Aromatik Bitki", 0.5, 0.8, 0.5, 20, 40, 60, 30, boy=0.3, kok=0.3, ekim_ay=8, kaynak="Tahmini", aciklama="Safranbolu; kurağa dayanıklı")
P("Kimyon", "Cuminum cyminum", "Tıbbi ve Aromatik Bitki", 0.5, 0.95, 0.5, 20, 30, 40, 20, boy=0.4, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Çörek Otu", "Nigella sativa", "Tıbbi ve Aromatik Bitki", 0.6, 0.9, 0.6, 20, 30, 40, 20, boy=0.4, kok=0.6, ekim_ay=4, kaynak="Tahmini")
P("Ekinezya", "Echinacea purpurea", "Tıbbi ve Aromatik Bitki", 0.6, 0.9, 0.6, 20, 40, 60, 30, boy=0.9, kok=0.7, ekim_ay=4, kaynak="Tahmini")
P("Kediotu (Valerian)", "Valeriana officinalis", "Tıbbi ve Aromatik Bitki", 0.7, 1.05, 0.85, 20, 40, 60, 30, boy=1.0, kok=0.7, ekim_ay=4, kaynak="Tahmini")
P("Sumak", "Rhus coriaria", "Tıbbi ve Aromatik Bitki", 0.5, 0.8, 0.6, 20, 40, 60, 30, boy=2.0, kok=1.0, ekim_ay=4, kaynak="Tahmini")
P("Kapari", "Capparis spinosa", "Tıbbi ve Aromatik Bitki", 0.4, 0.7, 0.5, 20, 40, 60, 30, boy=1.0, kok=1.2, ekim_ay=4, kaynak="Tahmini", aciklama="Çok kurağa dayanıklı")

# ============================== ENDÜSTRİ BİTKİLERİ ==============================
P("Tütün", "Nicotiana tabacum", "Endüstri Bitkisi", 0.5, 1.15, 0.8, 20, 30, 30, 30, boy=1.2, kok=0.8, ekim_ay=4)
P("Şerbetçiotu (Humulus)", "Humulus lupulus", "Endüstri Bitkisi", 0.3, 1.15, 0.85, 30, 40, 60, 30, boy=4.0, kok=1.0, ekim_ay=4, aciklama="Bira endüstrisi")
P("Kenevir", "Cannabis sativa", "Endüstri Bitkisi", 0.5, 1.1, 0.5, 20, 40, 50, 30, boy=2.0, kok=0.9, ekim_ay=4, kaynak="Tahmini", aciklama="Lif/kimya endüstrisi")
P("Keten", "Linum usitatissimum", "Endüstri Bitkisi", 0.5, 1.1, 0.7, 20, 30, 50, 40, boy=0.8, kok=0.8, ekim_ay=4)
P("Çay", "Camellia sinensis", "Endüstri Bitkisi", 0.95, 1.05, 0.95, 60, 60, 70, 30, boy=1.5, kok=1.0, ekim_ay=4, aciklama="Rize/Artvin çayı; yağışla karşılanır")
P("Haşhaş", "Papaver somniferum", "Endüstri Bitkisi", 0.6, 1.0, 0.6, 20, 35, 40, 25, boy=0.9, kok=0.9, ekim_ay=10, kaynak="Tahmini", aciklama="Afyonkarahisar bölgesi")
P("Şeker Darısı (Sorgum)", "Sorghum vulgare", "Endüstri Bitkisi", 0.35, 1.0, 0.55, 20, 35, 45, 25, boy=2.0, kok=1.2, ekim_ay=5, kaynak="Tahmini")
P("Lavanta (Endüstriyel)", "Lavandula intermedia", "Endüstri Bitkisi", 0.5, 0.8, 0.5, 30, 60, 90, 60, boy=0.8, kok=0.8, ekim_ay=4, kaynak="Tahmini", aciklama="Yağ üretimi")
P("Salep Orkidesi", "Orchis anatolica", "Endüstri Bitkisi", 0.6, 0.9, 0.6, 20, 40, 60, 30, boy=0.3, kok=0.4, ekim_ay=10, kaynak="Tahmini")
P("Oğul Otu (Tıbbi)", "Melissa officinalis", "Endüstri Bitkisi", 0.6, 1.0, 0.7, 20, 40, 60, 30, boy=0.6, kok=0.6, ekim_ay=4, kaynak="Tahmini", aciklama="Yağ endüstrisi")

# ============================== AĞAÇ (ORMAN / SÜS) ==============================
P("Kızılçam", "Pinus brutia", "Ağaç (Orman / Süs)", 0.7, 0.9, 0.85, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Karaçam", "Pinus nigra", "Ağaç (Orman / Süs)", 0.7, 0.9, 0.85, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Sedir", "Cedrus libani", "Ağaç (Orman / Süs)", 0.7, 0.85, 0.8, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Ladin", "Picea orientalis", "Ağaç (Orman / Süs)", 0.8, 0.95, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Göknar", "Abies nordmanniana", "Ağaç (Orman / Süs)", 0.8, 0.95, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Servi", "Cupressus sempervirens", "Ağaç (Orman / Süs)", 0.6, 0.75, 0.7, 30, 60, 120, 60, boy=10.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Meşe", "Quercus spp.", "Ağaç (Orman / Süs)", 0.8, 1.0, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Kayın", "Fagus orientalis", "Ağaç (Orman / Süs)", 0.8, 1.0, 0.9, 30, 60, 120, 60, boy=20.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Çınar", "Platanus orientalis", "Ağaç (Orman / Süs)", 0.85, 1.0, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Kavak", "Populus spp.", "Ağaç (Orman / Süs)", 0.9, 1.1, 0.95, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=3, kaynak="Tahmini", aciklama="Suyu çok sever; ırmak kenarı")
P("Söğüt", "Salix spp.", "Ağaç (Orman / Süs)", 0.9, 1.1, 1.0, 30, 60, 120, 60, boy=12.0, kok=1.5, ekim_ay=3, kaynak="Tahmini")
P("Ihlamur", "Tilia tomentosa", "Ağaç (Orman / Süs)", 0.8, 0.95, 0.85, 30, 60, 120, 60, boy=15.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Dişbudak", "Fraxinus excelsior", "Ağaç (Orman / Süs)", 0.85, 1.0, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Akasya (Yalancı)", "Robinia pseudoacacia", "Ağaç (Orman / Süs)", 0.6, 0.8, 0.7, 30, 60, 120, 60, boy=12.0, kok=1.5, ekim_ay=11, kaynak="Tahmini")
P("Okaliptüs", "Eucalyptus camaldulensis", "Ağaç (Orman / Süs)", 0.75, 1.0, 0.8, 30, 60, 120, 60, boy=20.0, kok=1.5, ekim_ay=11, aciklama="FAO-56; suyu sever")
P("Akçaağaç", "Acer spp.", "Ağaç (Orman / Süs)", 0.8, 0.95, 0.85, 30, 60, 120, 60, boy=12.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Kestane", "Castanea sativa", "Ağaç (Orman / Süs)", 0.7, 1.0, 0.8, 30, 60, 120, 60, boy=15.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Kızılağaç", "Alnus glutinosa", "Ağaç (Orman / Süs)", 0.85, 1.0, 0.9, 30, 60, 120, 60, boy=15.0, kok=1.2, ekim_ay=11, kaynak="Tahmini")
P("Süs Erigi (Süs Erik)", "Prunus cerasifera", "Ağaç (Orman / Süs)", 0.7, 0.9, 0.7, 20, 50, 90, 30, boy=5.0, kok=1.0, ekim_ay=4, kaynak="Tahmini")
P("Palmiye", "Phoenix spp.", "Ağaç (Orman / Süs)", 0.7, 0.85, 0.7, 30, 60, 120, 60, boy=8.0, kok=1.0, ekim_ay=4, kaynak="Tahmini", aciklama="Akdeniz sahil peyzajı")

BITKILER = []
for _kat in KATEGORILER:
    BITKILER.extend(B[_kat])
