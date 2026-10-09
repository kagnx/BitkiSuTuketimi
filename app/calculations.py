# -*- coding: utf-8 -*-
"""
Su ihtiyacı hesap motoru.

- Referans evapotranspirasyon (ETo):
    * FAO-56 Penman-Monteith (tam iklim verisi)
    * Hargreaves-Samani (sadece sıcaklık)
- Bitki katsayısı (Kc) eğrisi: FAO-56 dört evreli doğrusal model + RH/rüzgâr düzeltmesi
- Etkili yağış: USDA-SCS veya FAO basit yöntem
- Net/brüt sulama suyu ihtiyacı: günlük kök bölgesi su bakiyesi (kova modeli),
  aylık döküm, sulama aralığı, ağaç başına ihtiyaç
"""
import math
from datetime import date, timedelta

GSC = 0.0820          # MJ m-2 min-1
SIGMA = 4.903e-9      # MJ K-4 m-2 day-1
ALBEDO = 0.23
AY_ORTALAMA_GUN = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
AY_GUN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
AY_AD = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

SOILS = {
    "Kumlu": 90.0,
    "Kumlu-Tınlı": 120.0,
    "Tınlı": 150.0,
    "Tınlı-Killi": 170.0,
    "Killi": 200.0,
}

IRRIGATION_SYSTEMS = {
    "Damla Sulama": 0.90,
    "Yağmurlama": 0.75,
    "Karık (Yüzey)": 0.60,
    "Salma (Yüzey)": 0.50,
}

ETO_METHODS = ["FAO-56 Penman-Monteith", "Hargreaves-Samani"]
RAIN_METHODS = ["USDA-SCS", "FAO Basit Yöntem"]


def sat_vap_pressure(t):
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def daylight_hours(lat_deg, doy):
    phi = math.radians(lat_deg)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return 24.0 / math.pi * ws


def extraterrestrial_radiation(lat_deg, doy):
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    ra = (24 * 60 / math.pi) * GSC * dr * (
        ws * math.sin(phi) * math.sin(delta) +
        math.cos(phi) * math.cos(delta) * math.sin(ws))
    return max(0.0, ra)


def fao56_eto(Tmax, Tmin, RH, u2, n, lat_deg, alt, doy, rs=None):
    """Günlük ETo (mm/gün) — FAO-56 Penman-Monteith."""
    Tmean = (Tmax + Tmin) / 2.0
    es = (sat_vap_pressure(Tmax) + sat_vap_pressure(Tmin)) / 2.0
    ea = es * RH / 100.0
    delta = 4098 * sat_vap_pressure(Tmean) / ((Tmean + 237.3) ** 2)
    P_kpa = 101.3 * ((293 - 0.0065 * alt) / 293) ** 5.26
    gamma = 0.665e-3 * P_kpa
    ra = extraterrestrial_radiation(lat_deg, doy)
    if rs is None:
        N = daylight_hours(lat_deg, doy)
        rs = (0.25 + 0.5 * n / N) * ra if N > 0 else ra * 0.5
    rso = (0.75 + 2e-5 * alt) * ra
    rns = (1 - ALBEDO) * rs
    tmaxk = Tmax + 273.16
    tmink = Tmin + 273.16
    rnl = SIGMA * ((tmaxk ** 4 + tmink ** 4) / 2.0) * (0.34 - 0.14 * math.sqrt(ea))
    if rso > 0:
        rnl *= (1.35 * rs / rso - 0.35)
    rn = rns - rnl
    g = 0.0  # günlük hesapta toprak ısı akısı ihmal edilir
    num = 0.408 * delta * (rn - g) + gamma * (900 / (Tmean + 273)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, num / den)


def hargreaves_eto(Tmax, Tmin, lat_deg, doy):
    Tmean = (Tmax + Tmin) / 2.0
    ra = extraterrestrial_radiation(lat_deg, doy)
    ra_mm = ra * 0.408
    return max(0.0, 0.0023 * (Tmean + 17.8) * math.sqrt(max(0.0, Tmax - Tmin)) * ra_mm)


def monthly_eto(clim, method="FAO-56 Penman-Monteith"):
    """12 aylık ETo listesi (mm/gün). clim: ClimateData benzeri obje."""
    out = []
    for i, doy in enumerate(AY_ORTALAMA_GUN):
        if method.startswith("Hargreaves"):
            e = hargreaves_eto(clim.tmax[i], clim.tmin[i], clim.lat, doy)
        else:
            e = fao56_eto(clim.tmax[i], clim.tmin[i], clim.rh[i], clim.u2[i],
                          clim.n[i], clim.lat, clim.alt, doy)
        out.append(e)
    return out


def effective_rainfall(p_monthly, method="USDA-SCS"):
    """Aylık etkili yağış (mm)."""
    out = []
    for p in p_monthly:
        if method.startswith("USDA"):
            if p <= 250:
                pe = p * (125 - 0.2 * p) / 125.0
            else:
                pe = 125 + 0.1 * p
        else:  # FAO basit
            pe = 0.8 * p - 25 if p >= 75 else 0.6 * p - 10
        out.append(max(0.0, pe))
    return out


def interpolate_monthly(monthly, doy):
    """12 aylık değerleri günlük değere doğrusal enterpole eder (doy 1..365)."""
    d = min(365, max(1, doy))
    # aylık orta noktaları genişlet: 15,46,...349 + 380 (sonraki yıl)
    mid = AY_ORTALAMA_GUN + [AY_ORTALAMA_GUN[0] + 365]
    vals = monthly + [monthly[0]]
    for i in range(12):
        if mid[i] <= d <= mid[i + 1]:
            span = mid[i + 1] - mid[i]
            frac = (d - mid[i]) / span
            return vals[i] + (vals[i + 1] - vals[i]) * frac
    return monthly[0]


def kc_curve(L_ini, L_dev, L_mid, L_late, kc_ini, kc_mid, kc_end, total):
    """FAO-56 dört evreli doğrusal Kc eğrisi; günlük liste döndürür."""
    kcs = []
    b1, b2, b3, b4 = L_ini, L_ini + L_dev, L_ini + L_dev + L_mid, total
    for i in range(total):
        d = i + 1
        if d <= b1:
            kcs.append(kc_ini)
        elif d <= b2:
            frac = (d - b1) / max(1, b2 - b1)
            kcs.append(kc_ini + (kc_mid - kc_ini) * frac)
        elif d <= b3:
            kcs.append(kc_mid)
        elif d <= b4:
            frac = (d - b3) / max(1, b4 - b3)
            kcs.append(kc_mid + (kc_end - kc_mid) * frac)
        else:
            kcs.append(kc_end)
    return kcs


def adjust_kc(kc, u2, rh_min, h):
    """FAO-56 eş. 72: Kc'yi ortalama rüzgâr ve min bağıl neme göre düzeltir."""
    if kc > 0.45:
        return kc + (0.04 * (u2 - 2) - 0.004 * (rh_min - 45)) * (h / 3.0) ** 0.3
    return kc


def rh_min_from_temps(tmax, tmin, rh):
    """Aylık min bağıl nem tahmini (%)."""
    es_tmax = sat_vap_pressure(tmax)
    es = (sat_vap_pressure(tmax) + sat_vap_pressure(tmin)) / 2.0
    ea = es * rh / 100.0
    return min(100.0, max(5.0, ea / es_tmax * 100.0))


TOPRAK_TUZ = {
    "Kumlu": 0.70, "Kumlu-Tınlı": 0.85, "Tınlı": 1.00,
    "Tınlı-Killi": 1.15, "Killi": 1.30,
}
SISTEM_TUZ = {
    "Damla Sulama": 0.90,
    "Yağmurlama": 1.10,
    "Karık (Yüzey)": 1.20,
    "Salma (Yüzey)": 1.40,
}


def tuzluluk_uyarisi(plant, toprak, sistem, ecw=1.0):
    """
    Toprak, sulama sistemi ve bitkinin tuz toleransına göre su kalitesi /
    tuzluluk riski değerlendirmesi ve yıkama gereksinimi (FAO yöntemi).

    Döner: {ece, sinif, ecw, lr, lr_acik, seviye, mesaj, nedenler, oneriler,
            toprak, sistem}
    """
    from .plants_data import bitki_tuz_esik
    ece = float(bitki_tuz_esik(plant.get("ad", ""), plant.get("kategori", "")))
    if ece < 1.5:
        sinif = "Hassas"
    elif ece < 3.0:
        sinif = "Orta Hassas"
    elif ece < 6.0:
        sinif = "Orta Dayanıklı"
    elif ece < 10.0:
        sinif = "Dayanıklı"
    else:
        sinif = "Çok Dayanıklı"

    ecw = max(0.0, float(ecw or 0.0))
    soil_f = TOPRAK_TUZ.get(toprak, 1.0)
    sys_f = SISTEM_TUZ.get(sistem, 1.0)
    plant_f = 1.3 if ece < 1.5 else (1.1 if ece < 3.0 else 0.9)
    puan = soil_f * sys_f * plant_f
    if puan >= 1.5:
        seviye = "yuksek"
    elif puan >= 1.05:
        seviye = "orta"
    else:
        seviye = "dusuk"

    # Yıkama gereksinimi (FAO): LR (%) = ECw / (5*ECe - ECw) * 100
    lr, lr_acik = None, ""
    den = 5.0 * ece - ecw
    if den > 0.1:
        lr = max(0.0, ecw / den * 100.0)
        lr_acik = f"%{lr:.0f}"
    else:
        lr_acik = "çok yüksek — yıkama zorunlu"

    nedenler = []
    if plant_f > 1.0:
        nedenler.append(f"Bitki tuzluluğa duyarlı ({sinif}, ECe eşiği {ece:.1f} dS/m)")
    else:
        nedenler.append(f"Bitki tuzluluğa dayanıklı ({sinif}, ECe eşiği {ece:.1f} dS/m)")
    if soil_f >= 1.15:
        nedenler.append("Ağır (killi) toprak drenajı yavaşlatır, tuz birikimi riskini artırır")
    elif soil_f <= 0.85:
        nedenler.append("Hafif (kumlu) toprakta tuz yıkanması kolaydır")
    else:
        nedenler.append("Orta bünyeli toprak — dengeli drenaj")
    if sys_f >= 1.2:
        nedenler.append("Yüzey sulama, tuz birikimini ve yıkama ihtiyacını artırır")
    elif sistem == "Yağmurlama":
        nedenler.append("Yağmurlama ile yüksek EC'li suda yaprak yanıklığı riski oluşur")
    elif sistem == "Damla Sulama":
        nedenler.append("Damlada tuzlar ıslak bölge sınırında birikir — izleme gerekir")

    oneriler = []
    if sistem == "Damla Sulama":
        oneriler.append("Damlatıcı hattının çevresinde tuz birikimini izleyin; sezon içi yıkama (leaching) yapın.")
    elif sistem == "Yağmurlama":
        oneriler.append("Yüksek EC'li suda gece/akşam saatlerinde sulayın; yaprak yanıklığını önleyin.")
    else:
        oneriler.append("Drenajı iyileştirin ve tuz birikimini önlemek için yeterli yıkama suyu verin.")
    if soil_f >= 1.15:
        oneriler.append("Killi toprakta sulama aralığını kısaltın, birim sulamada daha az su verin; drenajı artırın.")
    if lr is not None and lr >= 15:
        oneriler.append(f"Yıkama gereksinimi {lr_acik} — sulama suyunun EC değerini düşürün veya toleranslı çeşit/bitki seçin.")
    if ecw > 2.0:
        oneriler.append("Sulama suyu EC'si yüksek (>2 dS/m) — su kaynağını karıştırma veya arıtma seçeneklerini değerlendirin.")
    oneriler.append("Toprak tuzluluğunu (ECe) sezon başında ve ortasında ölçtürün.")

    if seviye == "yuksek":
        mesaj = "Tuzluluk riski yüksek: hassas bitki + ağır toprak + uygun olmayan sulama yöntemi birleşimi."
    elif seviye == "orta":
        mesaj = "Orta düzeyde tuzluluk riski var; yıkama ve izleme önerilir."
    else:
        mesaj = "Tuzluluk riski düşük; mevcut koşullar uygun."

    return {
        "ece": ece, "sinif": sinif, "ecw": ecw, "lr": lr, "lr_acik": lr_acik,
        "seviye": seviye, "mesaj": mesaj,
        "nedenler": nedenler, "oneriler": oneriler,
        "toprak": toprak, "sistem": sistem,
    }


def compute_water_need(plant, clim, opts):
    """
    Bitki ve iklim verisinden sezonluk su ihtiyacını hesaplar.

    opts: dict
        ekim_tarihi (date), alan_da (float), eto_method, rain_method,
        toprak (str), sistem (str), mad (float)

    Su bakiyesi (günlük kova modeli): depo kapasitesi TAW = kök derinliği (m) ×
    AWC (mm/m); sezon başında tarla kapasitesinde (dolu) başlar. Her gün etkili
    yağış depoyu doldurur (taşma derin perkolasyona gider), ETc önce depodan
    karşılanır; depo + yağışın karşılayamadığı kısım net sulama suyu ihtiyacıdır.
    Böylece yağışlı günün fazlası sonraki güne devreder.
    """
    lat = clim.lat
    alt = clim.alt
    eto_monthly = monthly_eto(clim, opts.get("eto_method", "FAO-56 Penman-Monteith"))
    pe_monthly = effective_rainfall(clim.p, opts.get("rain_method", "USDA-SCS"))
    # aylık etkili yağış toplamını günlük orana çevir (enterpolasyon günlük çalışır)
    pe_daily_monthly = [pe_monthly[i] / AY_GUN[i] for i in range(12)]
    rh_min_list = [rh_min_from_temps(clim.tmax[i], clim.tmin[i], clim.rh[i]) for i in range(12)]

    L = [int(plant["L_ini"]), int(plant["L_dev"]), int(plant["L_mid"]), int(plant["L_late"])]
    total = sum(L)
    kc_raw = kc_curve(*L, plant["kc_ini"], plant["kc_mid"], plant["kc_end"], total)

    # iklim ağırlıklı ortalama u2 ve rh_min (sezon boyunca)
    planting = opts["ekim_tarihi"]
    doys = [(planting + timedelta(days=i)).timetuple().tm_yday for i in range(total)]
    u2_avg = sum(interpolate_monthly(clim.u2, d) for d in doys) / max(1, total)
    rh_avg = sum(interpolate_monthly(rh_min_list, d) for d in doys) / max(1, total)
    kc_mid_adj = adjust_kc(plant["kc_mid"], u2_avg, rh_avg, plant.get("boy", 1.0))
    kc_end_adj = adjust_kc(plant["kc_end"], u2_avg, rh_avg, plant.get("boy", 1.0))

    # günlük Kc listesini düzeltilmiş orta/son değerlerle yeniden kur
    kcs = kc_curve(*L, plant["kc_ini"], kc_mid_adj, kc_end_adj, total)

    month_acc = {m: {"et": 0.0, "pe": 0.0, "net": 0.0, "gross": 0.0} for m in range(12)}
    stage_acc = [{"et": 0.0, "net": 0.0} for _ in range(4)]  # başlangıç/gelişme/orta/son
    peak_daily_net = 0.0
    peak_day_meta = None
    peak_i = 0
    kc_season_avg = 0.0

    # kritik dönem (çiçeklenme / meyve tutumu vb.) penceresi
    kritik_ad = plant.get("kritik_ad") or "Çiçeklenme"
    kritik_merkez = float(plant.get("kritik_merkez") or 0.5)
    k_half = max(4, min(45, int(total * 0.15)))
    k_c = int(kritik_merkez * total)
    k_start = max(0, k_c - k_half)
    k_end = min(total - 1, k_c + k_half)
    if k_end - k_start < 4:
        k_end = min(total - 1, k_start + 4)
    win = {"et": 0.0, "net": 0.0, "pe": 0.0, "tepe_net": 0.0}

    eff = IRRIGATION_SYSTEMS.get(opts.get("sistem", "Damla Sulama"), 0.9)
    awc = SOILS.get(opts.get("toprak", "Tınlı"), 150.0)
    mad = float(opts.get("mad", 0.5))
    root = float(plant.get("kok", 0.7))

    # --- günlük kök bölgesi su bakiyesi (kova modeli) ---
    taw = max(1.0, root * awc)   # toplam kullanılabilir su (mm) = kök(m) × AWC(mm/m)
    raw = taw * mad              # kolayca kullanılabilir su (mm)
    swc = taw                    # kök bölgesindeki su (mm); başlangıç: tarla kapasitesi
    pe_tasinan = 0.0             # depo doluyken taşan etkili yağış (mm)

    for i in range(total):
        d = planting + timedelta(days=i)
        doy = d.timetuple().tm_yday
        m = d.month - 1
        eto = interpolate_monthly(eto_monthly, doy)
        pe_day = interpolate_monthly(pe_daily_monthly, doy)
        kc = kcs[i]
        kc_season_avg += kc
        et = eto * kc
        # kova: etkili yağış önce depoya dolar, ETc depodan karşılanır;
        # depo + yağışın karşılayamadığı kısım = net sulama (fazlası birikir)
        swc_on = swc
        swc = min(taw, swc + pe_day)
        pe_tasinan += pe_day - (swc - swc_on)   # depoya girmeyen kısım taştı
        use = min(et, swc)
        swc -= use
        daily_net = et - use
        month_acc[m]["et"] += et
        month_acc[m]["pe"] += pe_day
        month_acc[m]["net"] += daily_net
        month_acc[m]["gross"] += daily_net / eff
        if i < L[0]:
            si = 0
        elif i < L[0] + L[1]:
            si = 1
        elif i < L[0] + L[1] + L[2]:
            si = 2
        else:
            si = 3
        stage_acc[si]["et"] += et
        stage_acc[si]["net"] += daily_net
        if k_start <= i <= k_end:
            win["et"] += et
            win["net"] += daily_net
            win["pe"] += pe_day
            if daily_net > win["tepe_net"]:
                win["tepe_net"] = daily_net
        if daily_net > peak_daily_net:
            peak_daily_net = daily_net
            peak_day_meta = (d, eto, kc, pe_day)
            peak_i = i

    kc_season_avg /= total
    swc_end = swc   # sezon sonundaki kök bölgesi su bakiyesi (mm)

    # sulama aralığı: en yoğun gündeki net ihtiyaca göre
    available_mm = root * awc * mad
    interval = max(1, round(available_mm / peak_daily_net)) if peak_daily_net > 0 else 0
    irrigation_count = max(0, round(total / interval)) if interval else 0

    tot_et = sum(v["et"] for v in month_acc.values())
    tot_pe = sum(v["pe"] for v in month_acc.values())
    tot_net = sum(v["net"] for v in month_acc.values())
    tot_gross = sum(v["gross"] for v in month_acc.values())

    alan_da = float(opts.get("alan_da", 10.0))
    total_m3_net = tot_net * alan_da
    total_m3_gross = tot_gross * alan_da

    # ağaç başına (meyve/bahçe bitkileri)
    per_tree = None
    if plant.get("sira") and plant.get("sira_arasi"):
        area_tree = float(plant["sira"]) * float(plant["sira_arasi"])
        per_tree = {
            "alan_m2": area_tree,
            "sezon_net_litre": tot_net * area_tree,
            "sezon_brut_litre": tot_gross * area_tree,
            "sulama_brut_litre": (tot_gross * area_tree / irrigation_count) if irrigation_count else 0.0,
        }

    # gelişim evresi dökümü (ETc'nin evreler arası dağılımı)
    evre_ad = ["Başlangıç", "Gelişme", "Orta Sezon", "Sezon Sonu"]
    evre_gun = [L[0], L[1], L[2], L[3]]
    evre_kc_bas = [plant["kc_ini"], plant["kc_ini"], kc_mid_adj, kc_mid_adj]
    evre_kc_son = [plant["kc_ini"], kc_mid_adj, kc_mid_adj, kc_end_adj]
    stage_breakdown = []
    for i in range(4):
        stage_breakdown.append({
            "ad": evre_ad[i],
            "gun": evre_gun[i],
            "kc_bas": evre_kc_bas[i],
            "kc_son": evre_kc_son[i],
            "et_mm": stage_acc[i]["et"],
            "net_mm": stage_acc[i]["net"],
            "oran": (stage_acc[i]["et"] / tot_et * 100) if tot_et > 0 else 0.0,
        })

    # -------- kritik dönem su stresi riski --------
    k_bas = planting + timedelta(days=k_start)
    k_son = planting + timedelta(days=k_end)
    k_gun = k_end - k_start + 1
    k_irr = k_gun / interval if interval > 0 else 0.0
    k_pe_cover = (win["pe"] / win["et"] * 100.0) if win["et"] > 0 else 100.0
    peak_inside = peak_daily_net > 0 and k_start <= peak_i <= k_end
    risk = 0
    nedenler = []
    if interval > 0 and k_irr < 2:
        risk += 1
        nedenler.append(f"sulama aralığı {interval} gün kritik dönemde yetersiz sıklıkta "
                        f"(~{k_irr:.0f} sulama)")
    if k_pe_cover < 20:
        risk += 1
        nedenler.append(f"yağış, kritik dönem ihtiyacının yalnızca %{k_pe_cover:.0f}'ini karşılıyor "
                        f"(sulamaya tam bağımlılık)")
    if peak_inside:
        risk += 1
        nedenler.append("sezonun en yoğun günlük su ihtiyacı kritik dönem içine denk geliyor")
    if risk >= 2:
        seviye = "yuksek"
    elif risk == 1:
        seviye = "orta"
    else:
        seviye = "dusuk"
    if seviye == "yuksek":
        mesaj = (f"Su stresi riski YÜKSEK — {kritik_ad} dönemi için sulama programını "
                 f"sıkılaştırın: " + "; ".join(nedenler) + ".")
    elif seviye == "orta":
        mesaj = (f"Su stresi riski ORTA — " + "; ".join(nedenler) + ".")
    else:
        mesaj = (f"Kritik dönem ({kritik_ad}) için sulama planı yeterli görünüyor.")
    kritik = {
        "ad": kritik_ad,
        "bas_tarih": k_bas, "son_tarih": k_son,
        "gun": k_gun,
        "bas_index": k_start, "son_index": k_end,
        "et_mm": win["et"], "net_mm": win["net"], "pe_mm": win["pe"],
        "pe_cover": k_pe_cover,
        "tepe_gunluk_net": win["tepe_net"],
        "sulama_sayisi": k_irr,
        "seviye": seviye,
        "nedenler": nedenler,
        "mesaj": mesaj,
    }

    # -------- otomatik sulama planı önerisi --------
    debi = max(0.1, float(opts.get("debi", 15.0)))  # sistem debisi (m³/sa)
    normal_aralik = max(1, interval)
    kritik_aralik = normal_aralik
    if kritik["seviye"] in ("yuksek", "orta") and k_gun > 1:
        sik = max(1, int(math.floor(k_gun / 2)))  # kritik dönemde en az 2 sulama
        if kritik["seviye"] == "yuksek":
            kritik_aralik = min(normal_aralik, sik)
        else:
            kritik_aralik = min(normal_aralik, max(1, sik))
    if tot_gross <= 0:
        # kova modeli yağışlı bir sezonda sıfır net ihtiyaç döndürebilir
        n_sulama = 0
        irr_mm = irr_m3 = sure_sa = 0.0
    else:
        n_sulama = max(1, irrigation_count) if irrigation_count else max(1, int(round(total / max(1, normal_aralik))))
        irr_mm = tot_gross / n_sulama
        irr_m3 = irr_mm * alan_da
        sure_sa = irr_m3 / debi if debi > 0 else 0.0
    plan_ay = []
    for m in range(12):
        g = month_acc[m]["gross"]
        if g <= 0:
            continue
        n_m = max(1, int(round(g / max(0.1, irr_mm))))
        aralik_m = max(1, int(round(AY_GUN[m] / n_m)))
        plan_ay.append({"ay": AY_AD[m], "sulama": n_m, "aralik": aralik_m,
                        "brut_mm": g, "hacim_m3": g * alan_da,
                        "sure_sa": (g * alan_da / debi) if debi > 0 else 0.0})
    kritik_sulama = max(1, int(round(k_gun / max(1, kritik_aralik))))
    tepe_haftalik = max((r["hacim_m3"] / 4.33) for r in plan_ay) if plan_ay else 0.0
    if kritik_aralik < normal_aralik:
        aralik_metin = (f"kritik dönemde ({kritik_ad}: {k_bas.strftime('%d.%m')}–{k_son.strftime('%d.%m')}) "
                        f"her {kritik_aralik} günde bir, normal dönemde her {normal_aralik} günde bir")
    else:
        aralik_metin = f"sezon boyunca her {normal_aralik} günde bir"
    agac_litre = None
    if per_tree:
        agac_litre = irr_mm * per_tree["alan_m2"]  # sulama başına litre/ağaç
    if tot_gross <= 0:
        tavsiye = ("Sezon boyunca etkili yağış ve kök bölgesi su bakiyesi ihtiyacı "
                   "karşılıyor; ilave sulama gerekmiyor.")
    else:
        tavsiye = (
            f"Önerilen sulama planı: {aralik_metin} sulama yapın. Sulama başına yaklaşık "
            f"{irr_mm:.0f} mm ({irr_m3:,.0f} m³) su verin; {debi:g} m³/sa sistem debisiyle "
            f"bu sulama ~{sure_sa:.1f} saat sürer. Sezonda toplam ~{n_sulama} sulama, "
            f"brüt {tot_gross:.0f} mm ({total_m3_gross:,.0f} m³)."
        )
    if agac_litre:
        tavsiye += f" Ağaç başına sulama: ~{agac_litre:,.0f} L."
    plan = {
        "normal_aralik": normal_aralik,
        "kritik_aralik": kritik_aralik,
        "kritik_sulama": kritik_sulama,
        "n_sulama": n_sulama,
        "irr_mm": irr_mm,
        "irr_m3": irr_m3,
        "sure_sa": sure_sa,
        "debi": debi,
        "haftalik_tepe_m3": tepe_haftalik,
        "ay": plan_ay,
        "tavsiye": tavsiye,
        "agac_basina_litre": agac_litre,
    }

    # --- yeni: stres skoru, kriter tabanlı sulama önerisi, kök stratejisi ---
    st = stress_score(kritik, root, mad, swc_end, k_pe_cover, total,
                      peak_day_meta[1] if peak_day_meta else 0.0)
    irr_sug = irrigation_suggestion(kritik, opts, plan)
    root_trt = root_zone_treatment(plant, opts)

    return {
        "plant": plant,
        "opts": opts,
        "tuzluluk": tuzluluk_uyarisi(
            plant, opts.get("toprak", "Tınlı"), opts.get("sistem", "Damla Sulama"),
            float(opts.get("ecw", 1.0))),
        "stage_breakdown": stage_breakdown,
        "kritik": kritik,
        "plan": plan,
        "monthly": [dict(v, ay=AY_AD[m]) for m, v in month_acc.items()],
        "eto_monthly": eto_monthly,
        "pe_monthly": pe_monthly,
        "pe_daily_monthly": pe_daily_monthly,
        "rh_min_list": rh_min_list,
        "season_days": total,
        "kc_avg": kc_season_avg,
        "kc_mid_adj": kc_mid_adj,
        "kc_end_adj": kc_end_adj,
        "u2_avg": u2_avg,
        "rh_avg": rh_avg,
        "peak_daily_net": peak_daily_net,
        "peak_day": peak_day_meta[0] if peak_day_meta else None,
        "peak_eto": peak_day_meta[1] if peak_day_meta else 0.0,
        "peak_kc": peak_day_meta[2] if peak_day_meta else 0.0,
        "peak_pe": peak_day_meta[3] if peak_day_meta else 0.0,
        "tot_et": tot_et, "tot_pe": tot_pe, "tot_net": tot_net, "tot_gross": tot_gross,
        "total_m3_net": total_m3_net, "total_m3_gross": total_m3_gross,
        "alan_da": alan_da,
        "sistem": opts.get("sistem", "Damla Sulama"),
        "sistem_eff": eff,
        "toprak": opts.get("toprak", "Tınlı"),
        "awc": awc,
        "mad": mad,
        "taw": taw,
        "raw": raw,
        "swc_end": swc_end,
        "pe_tasinan": pe_tasinan,
        "interval": interval,
        "irrigation_count": irrigation_count,
        "per_tree": per_tree,
        "et_fazla_yağmur": tot_pe,
        "stress_score": st,
        "irrigation_suggestion": irr_sug,
        "root_zone_treatment": root_trt,
    }

def stress_score(critik, root, mad, swc_end, pe_cover, total_days, eto_peak):
    """Kritik dönemsel su stresi skoru (0-100; yüksek = daha fazla stres).

    bileşenler: yağış karşılama yetersizliği, sezon sonu kök bölgesi bakiyesi,
    kritik dönemdeki tepe net ihtiyacın ETo tepe oranına göre yoğunluğu,
    kritik risk seviyesi ve uzun sezon birikimi.
    """
    p = 0.0
    # 1) yağış karşılama yetersizliği
    p += min(40.0, max(0.0, (40.0 - pe_cover) * 1.2))
    # 2) sezon sonu kök bölgesi bakiyesi (doluluk düşükse stres artar)
    cap = max(1.0, root * 150.0)
    p += min(25.0, max(0.0, (1.0 - swc_end / cap) * 25.0))
    # 3) kritik tepe net / sezon tepe ETo yoğunluğu
    peak_net = float((critik or {}).get("tepe_gunluk_net") or 0.0)
    if eto_peak > 0:
        oran = peak_net / eto_peak
        p += min(20.0, max(0.0, (oran - 0.4) * 30.0))
    # 4) kritik risk seviyesi
    sev = (critik or {}).get("seviye")
    if sev == "yuksek":
        p += 15.0
    elif sev == "orta":
        p += 8.0
    # 5) uzun sezon (stres birikimi)
    p += min(5.0, max(0.0, (total_days / 90.0 - 1.0) * 5.0))
    return round(min(100.0, max(0.0, p)), 1)


def irrigation_suggestion(critik, opts, plan):
    """Kriter tabanlı sulama önerisi üretir (sıklık, miktarı, süresi)."""
    cfg = {
        "basinc": critik.get("seviye", "dusuk"),
        "sulama_sayisi": plan.get("kritik_sulama", 0),
        "aralik": plan.get("kritik_aralik", 0),
        "toplam_gun": critik.get("gun", 0),
        "net": critik.get("net_mm", 0.0),
        "pe_cover": critik.get("pe_cover", 0.0),
    }
    kesin = []
    if cfg["basinc"] == "yuksek":
        kesin.append("Kritik döneme girişte 2 saat önce ve çıktığında sıcaklık <28°C ise sulama yapın.")
        kesin.append("Sulama sıklığını normalize edin; 3 günden fazla boşta bırakmayın.")
    elif cfg["basinc"] == "orta":
        kesin.append("Eksik su kurisını takip edin; toprağın yüzeyi 5 cm yakının kuru olursa sulayın.")
    else:
        kesin.append("Sezon boyunca saptırmadan uzak durun; planlı sulamayı koruyun.")
    if cfg["sulama_sayisi"] < 2:
        if cfg["basinc"] == "yuksek":
            kesin.append("Kritik dönemde en az 2 kez sulayın.")
        else:
            kesin.append("Sulama aralığını %30 azaltın.")
    if cfg["pe_cover"] < 20:
        kesin.append("Yağış, ihtiyacı yeterince karşılamıyor; damla/salma ile tamamlayın.")
    if plan.get("debi", 0) == 0:
        kesin.append("Sistem debisi belirsizse, suyu 2 aşamalı (drenaj + sulama) uygulayın.")
    return {"kesin": kesin, "risk": cfg["basinc"], "seviye": cfg["sulama_sayisi"]}


def root_zone_treatment(plant, opts):
    """Kök derinliğe göre toprak işleme / sulama stratejisi önerisi."""
    root = float(plant.get("kok", 0.7))
    toprak = opts.get("toprak", "Tınlı")
    sistem = opts.get("sistem", "Damla Sulama")
    if root < 0.5:
        durum = "Şerit sulama; küçük çap, yüksek sıklık"
    elif root < 1.0:
        durum = "Normal kök; standard drenaj + çoklu sulama"
    else:
        durum = "Derin kök; seyrek ancak yüksek debil eklemeli sulama"
    if toprak in ("Tınlı-Killi", "Killi"):
        durum += "; drenajı iyileştirin, sulama aralığını %20 azaltın"
    if sistem == "Salma (Yüzey)":
        durum += "; seyrek ve derin sulama yerine parça-parça uygulayın"
    return {"durum": durum, "kombinasyon": "sıra/tetik", "akis": "hafta içinde", "not": "Yüksek değerlerde toprak nemini 60-70% tutmak için sulama akışı azaltılmalıdır."}
