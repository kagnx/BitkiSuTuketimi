# -*- coding: utf-8 -*-
"""SQLite veritabanı yönetimi: bitki kütüphanesi + ada/parsel kayıtları."""
import json
import os
import sqlite3
import sys
import threading
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from .paths import DB_PATH, DATA_DIR
from .plants_data import BITKILER

PLANT_COLUMNS = [
    "ad", "latin", "kategori", "kc_ini", "kc_mid", "kc_end",
    "L_ini", "L_dev", "L_mid", "L_late",
    "boy", "kok", "ekim_ay", "sira", "sira_arasi", "kaynak", "aciklama",
    "kritik_ad", "kritik_merkez",
]

PARCEL_COLUMNS = ["ada", "parsel", "il", "ilce", "mahalle", "koordinatlar", "alan_m2", "kaynak"]


class Database(QObject):
    """Uygulama veritabanı. Tüm işlemler tek bir bağlantı üzerinden yapılır."""

    changed = pyqtSignal()

    def __init__(self, path=DB_PATH):
        super().__init__()
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self.seed_plants()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bitkiler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT NOT NULL, latin TEXT, kategori TEXT,
                kc_ini REAL, kc_mid REAL, kc_end REAL,
                L_ini INTEGER, L_dev INTEGER, L_mid INTEGER, L_late INTEGER,
                boy REAL, kok REAL, ekim_ay INTEGER,
                sira REAL, sira_arasi REAL,
                kaynak TEXT, aciklama TEXT,
                kritik_ad TEXT, kritik_merkez REAL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parseller (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ada TEXT, parsel TEXT, il TEXT, ilce TEXT, mahalle TEXT,
                koordinatlar TEXT, alan_m2 REAL, kaynak TEXT, tarih TEXT
            )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bitki_ad ON bitkiler(ad)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_parsel ON parseller(ada, parsel)")
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Eski veritabanlarına eksik kolonları ekler ve kritik dönemleri geri doldurur."""
        cur = self.conn.cursor()
        cols = {r["name"] for r in cur.execute("PRAGMA table_info(bitkiler)").fetchall()}
        migrated = False
        if "kritik_ad" not in cols:
            cur.execute("ALTER TABLE bitkiler ADD COLUMN kritik_ad TEXT")
            migrated = True
        if "kritik_merkez" not in cols:
            cur.execute("ALTER TABLE bitkiler ADD COLUMN kritik_merkez REAL")
            migrated = True
        if migrated:
            # ilk migrasyonda: önce bitki bazlı açık override'lar, sonra kategori varsayılanları
            from .plants_data import KRITIK_DEFAULT, OVERRIDE
            for ad, (kad, km) in OVERRIDE.items():
                cur.execute("UPDATE bitkiler SET kritik_ad=?, kritik_merkez=? WHERE ad=?",
                            (kad, km, ad))
            for kat, (kad, km) in KRITIK_DEFAULT.items():
                cur.execute("UPDATE bitkiler SET kritik_ad=?, kritik_merkez=? "
                            "WHERE kategori=? AND kritik_ad IS NULL",
                            (kad, km, kat))
            self.conn.commit()

    # ------------------------- Bitkiler -------------------------
    def seed_plants(self):
        """Veri setini yükler: boş tabloya tümünü, dolu tabloya yalnızca
        adı olmayan yeni bitkileri ekler (mevcut kayıtlar ve kullanıcı
        düzenlemeleri korunur)."""
        with self._lock:
            cur = self.conn.cursor()
            n = cur.execute("SELECT COUNT(*) FROM bitkiler").fetchone()[0]
            if n == 0:
                for b in BITKILER:
                    self._insert_plant(cur, b)
                self.conn.commit()
                return
            # senkron: adı veritabanında olmayan bitkileri ekle
            existing = {r[0] for r in cur.execute("SELECT ad FROM bitkiler")}
            added = 0
            for b in BITKILER:
                if b["ad"] not in existing:
                    self._insert_plant(cur, b)
                    added += 1
            if added:
                self.conn.commit()

    def _insert_plant(self, cur, b):
        cur.execute(
            """INSERT INTO bitkiler (ad, latin, kategori, kc_ini, kc_mid, kc_end,
               L_ini, L_dev, L_mid, L_late, boy, kok, ekim_ay, sira, sira_arasi,
               kaynak, aciklama, kritik_ad, kritik_merkez)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (b["ad"], b.get("latin", ""), b.get("kategori", ""),
             b["kc_ini"], b["kc_mid"], b["kc_end"],
             b["L_ini"], b["L_dev"], b["L_mid"], b["L_late"],
             b.get("boy", 1.0), b.get("kok", 0.7), b.get("ekim_ay", 4),
             b.get("sira"), b.get("sira_arasi"),
             b.get("kaynak", "FAO-56"), b.get("aciklama", ""),
             b.get("kritik_ad", "Çiçeklenme"), b.get("kritik_merkez", 0.5)))

    def list_plants(self, kategori=None, arama=""):
        with self._lock:
            sql = "SELECT * FROM bitkiler"
            where, args = [], []
            if kategori:
                where.append("kategori = ?")
                args.append(kategori)
            if arama:
                where.append("(ad LIKE ? OR latin LIKE ? OR aciklama LIKE ?)")
                like = f"%{arama}%"
                args += [like, like, like]
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY kategori, ad"
            return [dict(r) for r in self.conn.execute(sql, args)]

    def get_plant(self, pid):
        with self._lock:
            r = self.conn.execute("SELECT * FROM bitkiler WHERE id=?", (pid,)).fetchone()
            return dict(r) if r else None

    def add_plant(self, data):
        with self._lock:
            cur = self.conn.cursor()
            self._insert_plant(cur, data)
            self.conn.commit()
        self.changed.emit()

    def update_plant(self, pid, data):
        with self._lock:
            sets = ", ".join(f"{c}=?" for c in PLANT_COLUMNS)
            vals = [data[c] for c in PLANT_COLUMNS] + [pid]
            self.conn.execute(f"UPDATE bitkiler SET {sets} WHERE id=?", vals)
            self.conn.commit()
        self.changed.emit()

    def delete_plant(self, pid):
        with self._lock:
            self.conn.execute("DELETE FROM bitkiler WHERE id=?", (pid,))
            self.conn.commit()
        self.changed.emit()

    def plant_count_by_category(self):
        with self._lock:
            rows = self.conn.execute(
                "SELECT kategori, COUNT(*) n FROM bitkiler GROUP BY kategori").fetchall()
            return {r["kategori"]: r["n"] for r in rows}

    # ------------------------- Parseller -------------------------
    def add_parcel(self, ada, parsel, il="", ilce="", mahalle="", coords=None,
                   alan_m2=None, kaynak="manuel"):
        coords = coords or []
        if alan_m2 is None and coords:
            alan_m2 = 0.0
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO parseller (ada, parsel, il, ilce, mahalle, koordinatlar, alan_m2, kaynak, tarih)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (str(ada), str(parsel), il, ilce, mahalle,
                 json.dumps(coords), alan_m2, kaynak,
                 datetime.now().isoformat(timespec="seconds")))
            self.conn.commit()
            rid = cur.lastrowid
        self.changed.emit()
        return rid

    def update_parcel_fields(self, pid, **fields):
        """Parselin belirtilen alanlarını günceller (il, ilce, mahalle vb.)."""
        allowed = {"ada", "parsel", "il", "ilce", "mahalle", "alan_m2", "kaynak"}
        up = {k: v for k, v in fields.items() if k in allowed}
        if not up:
            return
        sets = ", ".join(f"{k}=?" for k in up)
        with self._lock:
            self.conn.execute(f"UPDATE parseller SET {sets} WHERE id=?",
                              (*up.values(), pid))
            self.conn.commit()
        self.changed.emit()

    def list_parcels(self, il=None, arama=""):
        with self._lock:
            sql = "SELECT * FROM parseller"
            where, args = [], []
            if il:
                where.append("il = ?")
                args.append(il)
            if arama:
                where.append("(ada LIKE ? OR parsel LIKE ? OR il LIKE ?"
                             " OR ilce LIKE ? OR mahalle LIKE ?)")
                like = f"%{arama}%"
                args += [like, like, like, like, like]
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY ada, parsel"
            rows = [dict(r) for r in self.conn.execute(sql, args)]
        for r in rows:
            try:
                r["koordinatlar"] = json.loads(r["koordinatlar"] or "[]")
            except Exception:
                r["koordinatlar"] = []
        return rows

    def find_parcel_by_id(self, pid):
        with self._lock:
            r = self.conn.execute("SELECT * FROM parseller WHERE id=?", (pid,)).fetchone()
            if r is None:
                return None
            d = dict(r)
            try:
                d["koordinatlar"] = json.loads(d["koordinatlar"] or "[]")
            except Exception:
                d["koordinatlar"] = []
            return d

    def find_parcel(self, ada, parsel):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM parseller WHERE ada=? AND parsel=?",
                (str(ada), str(parsel))).fetchone()
            if r is None:
                return None
            d = dict(r)
            try:
                d["koordinatlar"] = json.loads(d["koordinatlar"] or "[]")
            except Exception:
                d["koordinatlar"] = []
            return d

    def delete_parcel(self, pid):
        with self._lock:
            self.conn.execute("DELETE FROM parseller WHERE id=?", (pid,))
            self.conn.commit()
        self.changed.emit()

    def delete_all_parcels(self):
        with self._lock:
            self.conn.execute("DELETE FROM parseller")
            self.conn.commit()
        self.changed.emit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


_db = None


def get_db():
    global _db
    if _db is None:
        _db = Database()
    return _db


def db_path_str():
    return DB_PATH
