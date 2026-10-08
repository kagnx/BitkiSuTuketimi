# -*- coding: utf-8 -*-
"""Uygulama ayarları (JSON tabanlı, data/config.json)."""
import json
import os

from .paths import CONFIG_PATH

DEFAULTS = {
    "rapor_kurumsal": False,   # raporlara kurumsal başlık/imza ekle
    "kurum_ad": "Mehmet YOLCU",
    "kurum_alt": "Şube Müdürü",
    "imza_ad": "Mehmet YOLCU",
    "imza_unvan": "Şube Müdürü",
    "logo_yolu": "",
    "imza_yolu": "",
}

TELIF = "Programlayan: Mehmet YOLCU - Şube Müdürü - Copyright © 2026 - Her Hakkı Saklıdır!"


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULTS:
                if k in data:
                    cfg[k] = data[k]
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    merged = dict(DEFAULTS)
    merged.update(cfg or {})
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged
