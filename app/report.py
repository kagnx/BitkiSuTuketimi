# -*- coding: utf-8 -*-
"""HTML ve CSV rapor üretimi."""
import base64
import csv
import html
import os
from datetime import datetime


def _img_base64(path):
    """Görsel dosyayı base64 veri URI'sine çevirir (HTML'e gömme için)."""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "bmp": "image/bmp", "svg": "image/svg+xml"}.get(ext, "image/png")
    try:
        with open(path, "rb") as f:
            return f"data:{mime};base64,{base64.b64encode(f.read()).decode('ascii')}"
    except OSError:
        return None


def _kurumsal_html(config):
    """Kurumsal başlık (logo + kurum + tarih) ve imza bloğu HTML'i."""
    cfg = config or {}
    if not cfg.get("rapor_kurumsal"):
        return "", ""
    kurum = html.escape(cfg.get("kurum_ad") or "")
    alt = html.escape(cfg.get("kurum_alt") or "")
    logo = _img_base64(cfg.get("logo_yolu"))
    logo_html = f'<img src="{logo}" style="height:64px; border-radius:6px;"/>' if logo else ""
    baslik = f"""
    <div style="display:flex; align-items:center; gap:16px; border-bottom:3px solid #AED581;
                padding-bottom:10px; margin-bottom:18px;">
      {logo_html}
      <div>
        <h1 style="margin:0; font-size:24px; color:#33691E;">{kurum}</h1>
        <p style="margin:2px 0 0 0; color:#6B7A5E;">{alt}</p>
      </div>
      <div style="margin-left:auto; text-align:right; color:#6B7A5E; font-size:12px;">
        Rapor Tarihi ve Saati: {datetime.now().strftime('%d.%m.%Y %H:%M')}
      </div>
    </div>"""
    imza_ad = html.escape(cfg.get("imza_ad") or "")
    imza_unvan = html.escape(cfg.get("imza_unvan") or "")
    imza_img = _img_base64(cfg.get("imza_yolu"))
    imza_img_html = (f'<img src="{imza_img}" style="height:64px; margin-bottom:4px;"/>'
                     if imza_img else "")
    if not (imza_ad or imza_unvan):
        return baslik, ""
    imza = f"""
    <div style="margin-top:48px; text-align:right;">
      {imza_img_html}
      <p style="margin:2px 0; font-weight:700;">{imza_ad or '&nbsp;'}</p>
      <p style="margin:2px 0; color:#6B7A5E;">{imza_unvan or '&nbsp;'}</p>
      <p style="margin:2px 0; color:#6B7A5E;">İmza</p>
    </div>"""
    return baslik, imza

from .calculations import AY_AD
from .paths import REPORT_DIR
from .config import TELIF


def _f(v, nd=1):
    try:
        return f"{v:,.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _konum_html(ko):
    """Kullanılan konum bilgisini HTML tablosuna çevirir."""
    if not ko:
        return ""
    krows = []
    if ko.get("sehir"):
        krows.append(("Şehir", html.escape(ko["sehir"])))
    if ko.get("en_yakin"):
        d = ko.get("mesafe_km")
        if ko.get("sehir") and ko["en_yakin"] == ko["sehir"]:
            krows.append(("Şehir merkezine uzaklık", f"~{_f(d, 1)} km"))
        else:
            krows.append(("En yakın il merkezi", f"{html.escape(ko['en_yakin'])} (~{_f(d, 1)} km)"))
    krows.append(("Enlem / Boylam", f"{ko['lat']:.5f}°K, {ko['lon']:.5f}°D"))
    krows.append(("Yükseklik", f"{ko['alt']:,.0f} m"))
    if ko.get("iklim"):
        krows.append(("İklim verisi", html.escape(ko["iklim"])))
    psel = ko.get("parsel")
    if psel and psel.get("ada"):
        parsel_txt = f"Ada {html.escape(str(psel['ada']))} / Parsel {html.escape(str(psel['no']))}"
        yer = "/".join(html.escape(str(psel[k])) for k in ("il", "ilce", "mahalle") if psel.get(k))
        if yer:
            parsel_txt += f" ({yer})"
        krows.insert(0, ("Ada / Parsel", parsel_txt))
    return "<h3>📍 Kullanılan Konum</h3><table>" + "".join(
        f"<tr><th>{h}</th><td>{v}</td></tr>" for h, v in krows) + "</table>"


def _svg_chart(res):
    """Aylık ETc / Net / Brüt değerlerini gösteren inline SVG çubuk grafik üretir."""
    months = [m["ay"] for m in res["monthly"]]
    series = [
        ("ETc", "#7CB342", [m["et"] for m in res["monthly"]]),
        ("Net İhtiyaç", "#33691E", [m["net"] for m in res["monthly"]]),
        ("Brüt İhtiyaç", "#AED581", [m["gross"] for m in res["monthly"]]),
    ]
    W, H = 780, 300
    ml, mr, mt, mb = 48, 12, 28, 38
    pw, ph = W - ml - mr, H - mt - mb
    maxv = max(max(s[2]) for s in series) * 1.15 or 1.0
    n = len(months)
    gw = pw / n
    nser = len(series)
    bw = min(30.0, gw / (nser + 0.5))
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         'style="width:100%;height:auto;background:#FFFFFF;border:1px solid #D8E3CC;border-radius:8px;">']
    # yatay ızgara + eksen etiketleri
    for i in range(5):
        y = mt + ph - ph * i / 4
        v = maxv * i / 4
        p.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" stroke="#EAF1E2" stroke-width="1"/>')
        p.append(f'<text x="{ml - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#6B7A5E">{v:.0f}</text>')
    p.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#9AAE88" stroke-width="1.5"/>')
    p.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#9AAE88" stroke-width="1.5"/>')
    # çubuklar
    for i, mname in enumerate(months):
        cx = ml + gw * i + gw / 2
        for s, (name, color, vals) in enumerate(series):
            v = vals[i]
            bh = ph * v / maxv
            x = cx - (nser * bw) / 2 + s * bw
            p.append(f'<rect x="{x:.1f}" y="{mt + ph - bh:.1f}" width="{bw - 1:.1f}" '
                     f'height="{bh:.1f}" fill="{color}" rx="2"/>')
        p.append(f'<text x="{cx:.1f}" y="{H - 14}" text-anchor="middle" font-size="10" '
                 f'fill="#33452B">{html.escape(mname[:3])}</text>')
    # lejant
    lx = ml
    for name, color, vals in series:
        p.append(f'<rect x="{lx}" y="6" width="12" height="12" fill="{color}" rx="2"/>')
        p.append(f'<text x="{lx + 16}" y="16" font-size="11" fill="#26311F">{html.escape(name)}</text>')
        lx += 16 + 12 + len(name) * 7 + 12
    p.append("</svg>")
    return "\n".join(p)


def build_report_html(res, ekstra=None, config=None):
    """Hesap sonucundan biçimlendirilmiş HTML raporu üretir."""
    plant = res["plant"]
    opts = res["opts"]
    ekstra = ekstra or {}
    kurumsal_html, imza_html = _kurumsal_html(config)
    rows = "".join(
        f"<tr><td>{html.escape(m['ay'])}</td>"
        f"<td>{_f(m['et'])}</td>"
        f"<td>{_f(m['pe'])}</td>"
        f"<td>{_f(m['net'])}</td>"
        f"<td>{_f(m['gross'])}</td></tr>"
        for m in res["monthly"] if m["et"] > 0 or m["gross"] > 0)

    stage_rows = "".join(
        f"<tr><td>{html.escape(s['ad'])}</td><td>{s['gun']}</td>"
        f"<td>{s['kc_bas']:.2f} → {s['kc_son']:.2f}</td>"
        f"<td>{_f(s['et_mm'])}</td><td>{_f(s['net_mm'])}</td>"
        f"<td>%{_f(s['oran'], 0)}</td></tr>"
        for s in res.get("stage_breakdown", []))

    kritik_html = ""
    kr = res.get("kritik")
    if kr:
        if kr["seviye"] == "yuksek":
            kb_col, kb_bg, sev = "#C62828", "#FDE7E7", "YÜKSEK"
        elif kr["seviye"] == "orta":
            kb_col, kb_bg, sev = "#B26A00", "#FFF3CD", "ORTA"
        else:
            kb_col, kb_bg, sev = "#2E7D32", "#E7F4E7", "DÜŞÜK"
        neden_list = "".join(f"<li>{html.escape(n)}</li>" for n in kr["nedenler"]) \
            if kr["nedenler"] else "<li>Risk faktörü tespit edilmedi.</li>"
        kritik_html = f"""
        <h3>⚠️ Kritik Dönem ve Su Stresi Riski</h3>
        <div class="box" style="border-left:5px solid {kb_col}; background:{kb_bg};">
          <p style="color:{kb_col}; font-weight:700; margin:0 0 6px 0;">
            Risk seviyesi: {sev} — {html.escape(kr['mesaj'])}</p>
          <p style="margin:4px 0;">🗓️ {html.escape(kr['ad'])} dönemi: {kr['bas_tarih'].strftime('%d.%m.%Y')} – {kr['son_tarih'].strftime('%d.%m.%Y')} ({kr['gun']} gün)</p>
          <p style="margin:4px 0;">Dönem ETc: {_f(kr['et_mm'])} mm • Net ihtiyaç: {_f(kr['net_mm'])} mm • Yağış karşılama: %{_f(kr['pe_cover'], 0)} • Tepe günlük ihtiyaç: {_f(kr['tepe_gunluk_net'])} mm</p>
          <ul style="margin:4px 0 0 18px;">{neden_list}</ul>
        </div>"""

    tuz_html = ""
    tuz = res.get("tuzluluk")
    if tuz:
        sev_map = {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}
        tz_sev = sev_map.get(tuz["seviye"], tuz["seviye"])
        if tuz["seviye"] == "yuksek":
            tz_col, tz_bg = "#C62828", "#FDE7E7"
        elif tuz["seviye"] == "orta":
            tz_col, tz_bg = "#B26A00", "#FFF3CD"
        else:
            tz_col, tz_bg = "#2E7D32", "#E7F4E7"
        neden_list = "".join(f"<li>{html.escape(n)}</li>" for n in tuz["nedenler"])
        oneri_list = "".join(f"<li>{html.escape(o)}</li>" for o in tuz["oneriler"])
        lr_txt = tuz.get("lr_acik") or (f"%{tuz['lr']:.0f}" if tuz.get("lr") is not None else "-")
        tuz_html = f"""
        <h3>🧂 Su Kalitesi ve Tuzluluk Uyarısı</h3>
        <div class="box" style="border-left:5px solid {tz_col}; background:{tz_bg};">
          <p style="color:{tz_col}; font-weight:700; margin:0 0 6px 0;">
            Tuzluluk riski: {tz_sev} — {html.escape(tuz['mesaj'])}</p>
          <p style="margin:4px 0;">Bitkinin tuz toleransı: {html.escape(tuz['sinif'])} (ECe eşiği {tuz['ece']:.1f} dS/m) • Sulama suyu EC: {tuz['ecw']:.1f} dS/m • Yıkama gereksinimi (FAO): {lr_txt}</p>
          <p style="margin:6px 0 2px 0;"><b>Değerlendirme:</b></p>
          <ul style="margin:2px 0 0 18px;">{neden_list}</ul>
          <p style="margin:6px 0 2px 0;"><b>Öneriler:</b></p>
          <ul style="margin:2px 0 0 18px;">{oneri_list}</ul>
        </div>"""

    tuz_param_row = ""
    if tuz:
        tz_sev2 = {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}.get(tuz["seviye"], tuz["seviye"])
        tuz_param_row = (f"<tr><th>Sulama Suyu EC (ECw)</th><td>{tuz['ecw']:.2f} dS/m</td>"
                         f"<th>Tuzluluk Riski</th><td>{html.escape(tz_sev2)}</td></tr>")

    plan_html = ""
    pl = res.get("plan")
    if pl:
        plan_rows = "".join(
            f"<tr><td>{html.escape(m['ay'])}</td><td>{m['sulama']}</td><td>{m['aralik']} gün</td>"
            f"<td>{_f(m['brut_mm'])}</td><td>{_f(m['hacim_m3'])}</td><td>{_f(m['sure_sa'])} sa</td></tr>"
            for m in pl.get("ay", []))
        plan_html = f"""
        <h3>💧 Otomatik Sulama Planı Önerisi (risk seviyesine göre)</h3>
        <div class="box" style="border-left:5px solid #7CB342; background:#E8F5E9;">
          <p style="margin:0 0 6px 0; color:#1B5E20; font-weight:700;">{html.escape(pl['tavsiye'])}</p>
          <p style="margin:4px 0; font-size:12px; color:#33691E;">Sulama başına {_f(pl['irr_mm'], 0)} mm ({_f(pl['irr_m3'], 0)} m³) • Sistem debisi {pl['debi']:g} m³/sa • Sulama süresi ~{_f(pl['sure_sa'], 1)} sa • Tepe haftalık ihtiyaç {_f(pl['haftalik_tepe_m3'], 0)} m³/hafta</p>
        </div>
        <table>
        <tr><th>Ay</th><th>Sulama (adet)</th><th>Aralık</th><th>Brüt (mm)</th><th>Hacim (m³)</th><th>Süre</th></tr>
        {plan_rows}
        </table>"""

    tree_html = ""
    if res.get("per_tree"):
        pt = res["per_tree"]
        tree_html = f"""
        <h3>🌳 Ağaç Başına Su İhtiyacı</h3>
        <table><tr><th>Dikim alanı (ağaç başına)</th><th>Sezon net</th><th>Sezon brüt</th><th>Sulama başına brüt</th></tr>
        <tr><td>{_f(pt['alan_m2'], 2)} m²</td><td>{_f(pt['sezon_net_litre'])} L</td>
        <td>{_f(pt['sezon_brut_litre'])} L</td><td>{_f(pt['sulama_brut_litre'])} L</td></tr></table>"""

    ekstra_html = ""
    if ekstra.get("ada_parsel") or ekstra.get("koordinat"):
        ekstra_html = "<h3>🗺️ Konum Bilgisi</h3><table>"
        if ekstra.get("ada_parsel"):
            ekstra_html += f"<tr><th>Ada / Parsel</th><td>{html.escape(ekstra['ada_parsel'])}</td></tr>"
        if ekstra.get("koordinat"):
            ekstra_html += f"<tr><th>Koordinat</th><td>{html.escape(ekstra['koordinat'])}</td></tr>"
        ekstra_html += "</table>"

    konum_html = _konum_html(res.get("konum"))

    peak = res.get("peak_day")
    peak_str = peak.strftime("%d.%m.%Y") if peak else "-"

    html_doc = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>ProSU — Su İhtiyacı Raporu</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; color: #26311F; background: #F4F7F1; }}
  h1 {{ color: #558B2F; border-bottom: 3px solid #AED581; padding-bottom: 8px; }}
  h2, h3 {{ color: #33691E; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0 20px 0; background: white; }}
  th {{ background: #E8F1DC; color: #33691E; padding: 8px; text-align: left; border: 1px solid #D8E3CC; }}
  td {{ padding: 7px; border: 1px solid #D8E3CC; }}
  tr:nth-child(even) td {{ background: #F6FAF1; }}
  .sum {{ font-weight: 700; background: #E8F1DC !important; }}
  .box {{ background: white; border: 1px solid #D8E3CC; border-radius: 8px; padding: 14px; margin: 10px 0; }}
  .kpi {{ display: inline-block; background: #7CB342; color: white; border-radius: 8px; padding: 12px 20px; margin: 6px; }}
  .kpi span {{ display: block; font-size: 11px; opacity: .9; }}
  .kpi b {{ font-size: 20px; }}
  footer {{ margin-top: 30px; color: #6B7A5E; font-size: 11px; }}
</style></head><body>
{kurumsal_html}
<h1>🌱 ProSU — Bitki Su İhtiyacı Raporu</h1>
<p>Üretim tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
<div class="box">
<h2>{html.escape(plant['ad'])} <span style="font-weight:400;color:#6B7A5E">({html.escape(plant.get('latin',''))})</span></h2>
<p>Kategori: {html.escape(plant.get('kategori',''))} &nbsp;|&nbsp; Kc kaynağı: {html.escape(plant.get('kaynak',''))} &nbsp;|&nbsp; Sezon uzunluğu: {res['season_days']} gün</p>
</div>
{ekstra_html}
{konum_html}
<div>
  <div class="kpi"><span>Sezonluk ETc</span><b>{_f(res['tot_et'])} mm</b></div>
  <div class="kpi"><span>Etkili Yağış</span><b>{_f(res['tot_pe'])} mm</b></div>
  <div class="kpi"><span>Net İhtiyaç</span><b>{_f(res['tot_net'])} mm</b></div>
  <div class="kpi"><span>Brüt İhtiyaç</span><b>{_f(res['tot_gross'])} mm</b></div>
  <div class="kpi"><span>Net ({_f(res['alan_da'])} da)</span><b>{_f(res['total_m3_net'])} m³</b></div>
  <div class="kpi"><span>Brüt ({_f(res['alan_da'])} da)</span><b>{_f(res['total_m3_gross'])} m³</b></div>
</div>
<div class="box">
<h3>Hesap Parametreleri</h3>
<table>
<tr><th>ETo Yöntemi</th><td>{html.escape(res['opts'].get('eto_method',''))}</td>
    <th>Etkili Yağış</th><td>{html.escape(res['opts'].get('rain_method',''))}</td></tr>
<tr><th>Sulama Sistemi</th><td>{html.escape(res['sistem'])} (%{_f(res['sistem_eff']*100,0)} verim)</td>
    <th>Toprak</th><td>{html.escape(res['toprak'])}</td></tr>
<tr><th>Dikim Tarihi</th><td>{res['opts'].get('ekim_tarihi','').strftime('%d.%m.%Y') if res['opts'].get('ekim_tarihi') else '-'}</td>
    <th>MAD (izin verilen su tüketimi)</th><td>%{_f(res['mad']*100,0)}</td></tr>
<tr><th>En yoğun gün (net ihtiyaç)</th><td>{peak_str} — {_f(res['peak_daily_net'])} mm/gün</td>
    <th>Önerilen sulama aralığı</th><td>{res['interval']} gün ({res['irrigation_count']} sulama)</td></tr>
{tuz_param_row}
</table>
</div>
<h3>📅 Aylık Döküm (mm)</h3>
<table>
<tr><th>Ay</th><th>ETc</th><th>Etkili Yağış</th><th>Net İhtiyaç</th><th>Brüt İhtiyaç</th></tr>
{rows}
<tr class="sum"><td>TOPLAM</td><td>{_f(res['tot_et'])}</td><td>{_f(res['tot_pe'])}</td>
<td>{_f(res['tot_net'])}</td><td>{_f(res['tot_gross'])}</td></tr>
</table>

<h3>📊 Aylık Su Dengesi Grafiği (mm)</h3>
{_svg_chart(res)}

<h3>📈 Gelişim Evresi Dökümü — ETc (gerçek bitki su tüketimi)</h3>
<p style="color:#6B7A5E;font-size:12px;">ETo (referans bitki su tüketimi) genel atmosferik kaybı ifade eder; ETc, bitki katsayısı (Kc) ve gelişim evresine göre hedeflenen mahsulün gerçek ihtiyacıdır. Sulama planı evre bazlı bu ETc değerine göre yapılmalıdır.</p>
<table>
<tr><th>Gelişim Evresi</th><th>Süre (gün)</th><th>Kc (baş → son)</th><th>ETc (mm)</th><th>Net İhtiyaç (mm)</th><th>Sezon Payı</th></tr>
{stage_rows}
</table>
{kritik_html}
{tuz_html}
{plan_html}
{tree_html}
{imza_html}
<footer>Rapor ProSU Tarımsal Su Yönetim Sistemi tarafından üretilmiştir. Kc değerleri FAO-56
esas alınarak belirlenmiştir; yerel koşullar için ziraat mühendisliği onayı önerilir.<br/>
{html.escape(TELIF)}</footer>
</body></html>"""
    return html_doc


def save_report_html(res, ekstra=None, config=None):
    os.makedirs(REPORT_DIR, exist_ok=True)
    name = f"su_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    path = os.path.join(REPORT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_report_html(res, ekstra, config))
    return path


def save_report_csv(res, path=None, config=None):
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = path or os.path.join(REPORT_DIR, f"su_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        cfg = config or {}
        if cfg.get("rapor_kurumsal") and (cfg.get("kurum_ad") or cfg.get("imza_ad")):
            if cfg.get("kurum_ad"):
                w.writerow(["Kurum", cfg.get("kurum_ad")])
            if cfg.get("kurum_alt"):
                w.writerow(["Birim", cfg.get("kurum_alt")])
            w.writerow(["Rapor Tarihi ve Saati", datetime.now().strftime("%d.%m.%Y %H:%M")])
            if cfg.get("imza_ad"):
                w.writerow(["İmza", cfg.get("imza_ad")])
            if cfg.get("imza_unvan"):
                w.writerow(["Unvan", cfg.get("imza_unvan")])
            w.writerow([])
        w.writerow(["ProSU Bitki Su İhtiyacı Raporu"])
        w.writerow(["Bitki", res["plant"]["ad"]])
        w.writerow(["Kategori", res["plant"].get("kategori", "")])
        w.writerow(["ETo Yöntemi", res["opts"].get("eto_method", "")])
        w.writerow(["Sulama Sistemi", res["sistem"]])
        w.writerow(["Toprak", res["toprak"]])
        w.writerow(["Alan (da)", res["alan_da"]])
        w.writerow([])
        w.writerow(["Ay", "ETc (mm)", "Etkili Yağış (mm)", "Net (mm)", "Brüt (mm)"])
        for m in res["monthly"]:
            w.writerow([m["ay"], round(m["et"], 1), round(m["pe"], 1),
                        round(m["net"], 1), round(m["gross"], 1)])
        w.writerow(["TOPLAM", round(res["tot_et"], 1), round(res["tot_pe"], 1),
                    round(res["tot_net"], 1), round(res["tot_gross"], 1)])
        w.writerow([])
        w.writerow(["Net İhtiyaç (m³)", round(res["total_m3_net"], 1)])
        w.writerow(["Brüt İhtiyaç (m³)", round(res["total_m3_gross"], 1)])
        ko = res.get("konum")
        if ko:
            w.writerow([])
            w.writerow(["KULLANILAN KONUM / ŞEHİR"])
            if ko.get("sehir"):
                w.writerow(["Şehir", ko["sehir"]])
            if ko.get("en_yakin"):
                d = ko.get("mesafe_km")
                if ko.get("sehir") and ko["en_yakin"] == ko["sehir"]:
                    w.writerow(["Şehir merkezine uzaklık (km)", d])
                else:
                    w.writerow(["En yakın il merkezi", ko["en_yakin"]])
                    w.writerow(["Mesafe (km)", d])
            w.writerow(["Enlem", ko["lat"]])
            w.writerow(["Boylam", ko["lon"]])
            w.writerow(["Yükseklik (m)", ko["alt"]])
            if ko.get("iklim"):
                w.writerow(["İklim verisi", ko["iklim"]])
            psel = ko.get("parsel")
            if psel and psel.get("ada"):
                w.writerow(["Ada / Parsel", f"Ada {psel['ada']} / Parsel {psel['no']}"])
                for k in ("il", "ilce", "mahalle"):
                    if psel.get(k):
                        w.writerow([k.capitalize(), psel[k]])
        if res.get("per_tree"):
            w.writerow(["Ağaç başına sezon brüt (L)", round(res["per_tree"]["sezon_brut_litre"], 1)])
        # gelişim evresi dökümü
        w.writerow([])
        w.writerow(["GELİŞİM EVRESİ DÖKÜMÜ (ETc — gerçek bitki su tüketimi)"])
        w.writerow(["Evre", "Süre (gün)", "Kc (baş)", "Kc (son)", "ETc (mm)", "Net (mm)", "Sezon Payı (%)"])
        for s in res.get("stage_breakdown", []):
            w.writerow([s["ad"], s["gun"], round(s["kc_bas"], 2), round(s["kc_son"], 2),
                        round(s["et_mm"], 1), round(s["net_mm"], 1), round(s["oran"], 1)])
        # kritik dönem / su stresi riski
        kr = res.get("kritik")
        if kr:
            w.writerow([])
            w.writerow(["KRİTİK DÖNEM / SU STRESİ RİSKİ"])
            w.writerow(["Kritik dönem", kr["ad"]])
            w.writerow(["Dönem aralığı",
                        f"{kr['bas_tarih'].strftime('%d.%m.%Y')} - {kr['son_tarih'].strftime('%d.%m.%Y')}"])
            w.writerow(["Süre (gün)", kr["gun"]])
            w.writerow(["Dönem ETc (mm)", round(kr["et_mm"], 1)])
            w.writerow(["Dönem net ihtiyaç (mm)", round(kr["net_mm"], 1)])
            w.writerow(["Yağış karşılama (%)", round(kr["pe_cover"], 1)])
            w.writerow(["Tepe günlük ihtiyaç (mm)", round(kr["tepe_gunluk_net"], 1)])
            w.writerow(["Risk seviyesi",
                        {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}.get(kr["seviye"], kr["seviye"])])
            for n in kr["nedenler"]:
                w.writerow(["Risk nedeni", n])
            w.writerow(["Değerlendirme", kr["mesaj"]])
        # su kalitesi / tuzluluk uyarısı
        tuz = res.get("tuzluluk")
        if tuz:
            w.writerow([])
            w.writerow(["SU KALİTESİ / TUZLULUK UYARISI"])
            w.writerow(["Bitkinin tuz toleransı",
                        f"{tuz['sinif']} (ECe eşiği {tuz['ece']:.1f} dS/m)"])
            w.writerow(["Sulama suyu EC (ECw, dS/m)", round(tuz["ecw"], 2)])
            w.writerow(["Yıkama gereksinimi (FAO)", tuz["lr_acik"]])
            w.writerow(["Risk seviyesi",
                        {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}.get(tuz["seviye"], tuz["seviye"])])
            w.writerow(["Değerlendirme", tuz["mesaj"]])
            for n in tuz["nedenler"]:
                w.writerow(["Değerlendirme", n])
            for o in tuz["oneriler"]:
                w.writerow(["Öneri", o])
        # otomatik sulama planı önerisi
        pl = res.get("plan")
        if pl:
            w.writerow([])
            w.writerow(["OTOMATİK SULAMA PLANI ÖNERİSİ (risk seviyesine göre)"])
            w.writerow(["Öneri", pl["tavsiye"]])
            w.writerow(["Normal dönem aralığı (gün)", pl["normal_aralik"]])
            w.writerow(["Kritik dönem aralığı (gün)", pl["kritik_aralik"]])
            w.writerow(["Sulama başına miktar (mm)", round(pl["irr_mm"], 1)])
            w.writerow(["Sulama başına miktar (m³)", round(pl["irr_m3"], 1)])
            w.writerow(["Sistem debisi (m³/sa)", pl["debi"]])
            w.writerow(["Sulama süresi (sa)", round(pl["sure_sa"], 1)])
            w.writerow(["Tepe haftalık ihtiyaç (m³)", round(pl["haftalik_tepe_m3"], 1)])
            if pl.get("agac_basina_litre"):
                w.writerow(["Ağaç başına sulama (L)", round(pl["agac_basina_litre"], 1)])
            w.writerow([])
            w.writerow(["Ay", "Sulama (adet)", "Aralık (gün)", "Brüt (mm)", "Hacim (m³)", "Süre (sa)"])
            for m in pl.get("ay", []):
                w.writerow([m["ay"], m["sulama"], m["aralik"], round(m["brut_mm"], 1),
                            round(m["hacim_m3"], 1), round(m["sure_sa"], 1)])
        w.writerow([])
        w.writerow([TELIF])
    return path


def _svg_compare_chart(results):
    """Bitkiler arası brüt ihtiyaç (m³) karşılaştırma çubuk grafiği."""
    if not results:
        return ""
    W, ml = 780, 210
    row_h, bar_h, gap = 34, 18, 10
    H = 40 + len(results) * row_h
    maxv = max((r.get("m3_gross") or 0) for r in results) * 1.12 or 1.0
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         'style="width:100%;height:auto;background:#FFFFFF;border:1px solid #D8E3CC;border-radius:8px;">']
    for i, r in enumerate(results):
        y = 40 + i * row_h
        name = html.escape(str(r["plant"]["ad"]))[:26]
        v = r.get("m3_gross") or 0
        bw = (W - ml - 60) * v / maxv
        p.append(f'<text x="{ml - 8}" y="{y + bar_h - 4}" text-anchor="end" font-size="12" fill="#33452B">{name}</text>')
        p.append(f'<rect x="{ml}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="#7CB342" rx="4"/>')
        p.append(f'<text x="{ml + bw + 6}" y="{y + bar_h - 4}" font-size="12" fill="#33691E">{_f(v, 0)} m³</text>')
    p.append("</svg>")
    return "\n".join(p)


SEVIYE_AD = {"yuksek": "YÜKSEK", "orta": "ORTA", "dusuk": "DÜŞÜK"}


def build_compare_html(results, konum=None, config=None):
    """Aynı konum için bitki karşılaştırma raporu (HTML)."""
    kurumsal_html, imza_html = _kurumsal_html(config)
    rows = "".join(
        f"<tr><td>{html.escape(r['plant']['ad'])}</td>"
        f"<td>{html.escape(r['plant'].get('kategori',''))}</td>"
        f"<td>{r['sezon']}</td>"
        f"<td>{_f(r['et'])}</td><td>{_f(r['pe'])}</td>"
        f"<td>{_f(r['net'])}</td><td>{_f(r['gross'])}</td>"
        f"<td>{_f(r['m3_net'])}</td><td>{_f(r['m3_gross'])}</td>"
        f"<td>{r['aralik']}</td><td>{r['sulama']}</td>"
        f"<td>{SEVIYE_AD.get(r['risk'], '-') if r['risk'] else '-'}</td>"
        f"<td>{SEVIYE_AD.get(r['tuzluluk'], '-') if r.get('tuzluluk') else '-'}</td>"
        f"<td>{_f(r['agac_l']) if r.get('agac_l') else '-'}</td></tr>"
        for r in results)
    doc = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>ProSU — Bitki Karşılaştırma Raporu</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; color: #26311F; background: #F4F7F1; }}
  h1 {{ color: #558B2F; border-bottom: 3px solid #AED581; padding-bottom: 8px; }}
  h2, h3 {{ color: #33691E; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0 20px 0; background: white; }}
  th {{ background: #E8F1DC; color: #33691E; padding: 8px; text-align: left; border: 1px solid #D8E3CC; }}
  td {{ padding: 7px; border: 1px solid #D8E3CC; }}
  tr:nth-child(even) td {{ background: #F6FAF1; }}
  footer {{ margin-top: 30px; color: #6B7A5E; font-size: 11px; }}
</style></head><body>
{kurumsal_html}
<h1>⚖️ ProSU — Bitki Su İhtiyacı Karşılaştırma Raporu</h1>
<p>Üretim tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
<p style="color:#6B7A5E;font-size:12px;">Tüm bitkiler aynı konum/iklim ve aynı hesap parametreleriyle hesaplandı; dikim tarihi her bitkinin kendi önerilen ekim ayına göre alındı.</p>
{_konum_html(konum)}
<h3>📊 Brüt Su İhtiyacı Karşılaştırması ({_f(results[0]['alan_da']) if results else 0} da)</h3>
{_svg_compare_chart(results)}
<h3>📋 Karşılaştırma Tablosu</h3>
<table>
<tr><th>Bitki</th><th>Kategori</th><th>Sezon (gün)</th><th>ETc (mm)</th><th>Etkili Yağış (mm)</th><th>Net (mm)</th><th>Brüt (mm)</th><th>Net (m³)</th><th>Brüt (m³)</th><th>Aralık (gün)</th><th>Sulama (adet)</th><th>Su Stresi Riski</th><th>Tuzluluk Riski</th><th>Ağaç başına (L/sulama)</th></tr>
{rows}
</table>
<p style="color:#6B7A5E;font-size:12px;">Alan: {_f(results[0]['alan_da']) if results else 0} da • Toprak: {html.escape(results[0]['toprak']) if results else '-'} • Sistem: {html.escape(results[0]['sistem']) if results else '-'} • MAD: %{_f(results[0]['mad']*100,0) if results else 0} • ETo yöntemi: {html.escape(results[0]['eto_method']) if results else '-'}</p>
{imza_html}
<footer>Rapor ProSU Tarımsal Su Yönetim Sistemi tarafından üretilmiştir. Kc değerleri FAO-56
esas alınarak belirlenmiştir; yerel koşullar için ziraat mühendisliği onayı önerilir.<br/>
{html.escape(TELIF)}</footer>
</body></html>"""
    return doc


def save_compare_csv(results, konum=None, config=None, path=None):
    """Aynı konum için bitki karşılaştırma raporu (CSV)."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = path or os.path.join(REPORT_DIR, f"karsilastirma_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        cfg = config or {}
        if cfg.get("rapor_kurumsal") and (cfg.get("kurum_ad") or cfg.get("imza_ad")):
            if cfg.get("kurum_ad"):
                w.writerow(["Kurum", cfg.get("kurum_ad")])
            if cfg.get("kurum_alt"):
                w.writerow(["Birim", cfg.get("kurum_alt")])
            w.writerow(["Rapor Tarihi ve Saati", datetime.now().strftime("%d.%m.%Y %H:%M")])
            if cfg.get("imza_ad"):
                w.writerow(["İmza", cfg.get("imza_ad")])
            if cfg.get("imza_unvan"):
                w.writerow(["Unvan", cfg.get("imza_unvan")])
            w.writerow([])
        w.writerow(["ProSU Bitki Karşılaştırma Raporu"])
        ko = konum or {}
        if ko:
            w.writerow([])
            w.writerow(["KULLANILAN KONUM / ŞEHİR"])
            if ko.get("sehir"):
                w.writerow(["Şehir", ko["sehir"]])
            if ko.get("en_yakin"):
                d = ko.get("mesafe_km")
                if ko.get("sehir") and ko["en_yakin"] == ko["sehir"]:
                    w.writerow(["Şehir merkezine uzaklık (km)", d])
                else:
                    w.writerow(["En yakın il merkezi", ko["en_yakin"]])
                    w.writerow(["Mesafe (km)", d])
            w.writerow(["Enlem", ko["lat"]])
            w.writerow(["Boylam", ko["lon"]])
            w.writerow(["Yükseklik (m)", ko["alt"]])
            if ko.get("iklim"):
                w.writerow(["İklim verisi", ko["iklim"]])
            psel = ko.get("parsel")
            if psel and psel.get("ada"):
                w.writerow(["Ada / Parsel", f"Ada {psel['ada']} / Parsel {psel['no']}"])
                for k in ("il", "ilce", "mahalle"):
                    if psel.get(k):
                        w.writerow([k.capitalize(), psel[k]])
        if results:
            r0 = results[0]
            w.writerow([])
            w.writerow(["Alan (da)", r0["alan_da"]])
            w.writerow(["Toprak", r0["toprak"]])
            w.writerow(["Sulama sistemi", r0["sistem"]])
            w.writerow(["ETo yöntemi", r0["eto_method"]])
        w.writerow([])
        w.writerow(["Bitki", "Kategori", "Sezon (gün)", "ETc (mm)", "Etkili Yağış (mm)",
                    "Net (mm)", "Brüt (mm)", "Net (m³)", "Brüt (m³)", "Sulama aralığı (gün)",
                    "Sulama (adet)", "Su stresi riski", "Tuzluluk riski", "Ağaç başına (L/sulama)"])
        for r in results:
            w.writerow([r["plant"]["ad"], r["plant"].get("kategori", ""), r["sezon"],
                        round(r["et"], 1), round(r["pe"], 1), round(r["net"], 1), round(r["gross"], 1),
                        round(r["m3_net"], 1), round(r["m3_gross"], 1), r["aralik"], r["sulama"],
                        SEVIYE_AD.get(r["risk"], "") if r["risk"] else "",
                        SEVIYE_AD.get(r.get("tuzluluk"), "") if r.get("tuzluluk") else "",
                        round(r["agac_l"], 1) if r.get("agac_l") else ""])
        w.writerow([])
        w.writerow([TELIF])
    return path
