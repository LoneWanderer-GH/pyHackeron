from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import sqlite3
import threading
import logging

from corelec.BLE.frame import Frame
from corelec.ReverseEngineering.decoder import DecodedBase

logger = logging.getLogger(__name__)


class Database:
    """
    Couche de persistance SQLite pour Corelec Monitor.

    Source unique de vérité :
        - ``raw_frames``     : trames BLE brutes (hex).
        - ``decoded_frames`` : valeurs numériques décodées (JSON) — alimentée
          automatiquement à chaque ``store_frame()``, utilisée par les graphiques
          pour éviter le re-décodage ctypes à chaque rafraîchissement.

    Tables :
        raw_frames      (id, ts ISO-8601, frame_type int, frame_hex str)
        decoded_frames  (id, ts ISO-8601, frame_type int, data json)
        decoded_values  conservée pour compatibilité, n’est plus écrite
        frame_bytes     conservée pour compatibilité, n’est plus écrite

    Thread-safe : toutes les écritures utilisent ``self.lock``.
    """

    def __init__(self, path:str | Path="pool.db"):
        _path  : Path = Path(path)
        if not _path.is_absolute():
            _path = Path(__file__).resolve().parent.parent / _path

        _path.parent.mkdir(parents=True, exist_ok=True)
        if _path.exists():
            logger.info("DB Path %s exists", _path.as_posix())
        else:
            logger.info("DB Path %s does not exist, will create new DB", _path.as_posix())
        self.path = _path
        self.conn = sqlite3.connect(_path, check_same_thread=False)
        self.lock = threading.Lock()

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_frames(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            frame_type INTEGER,
            frame_hex TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS frame_bytes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            frame_type INTEGER,
            byte_index INTEGER,
            value INTEGER
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS decoded_values(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT,
            value REAL
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS decoded_frames(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            frame_type INTEGER NOT NULL,
            data       TEXT    NOT NULL
        )
        """)
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_decoded_frames_tp
        ON decoded_frames(frame_type, ts)
        """)

        self.conn.commit()

        # Backfill one-shot : si decoded_frames est vide mais raw_frames ne l'est pas
        # (migration depuis une base existante sans decoded_frames).
        _empty = self.conn.execute("SELECT COUNT(*) FROM decoded_frames").fetchone()[0] == 0
        _has_raw = self.conn.execute("SELECT COUNT(*) FROM raw_frames").fetchone()[0] > 0
        if _empty and _has_raw:
            self._backfill_decoded_frames()

    def store_frame(self, frame: Frame, ts: str | None = None) -> None:
        """Stocke la trame brute ET les valeurs décodées dans une seule transaction.

        ``ts`` permet de conserver l'horodatage d'origine (ex. daemon ZMQ).
        Si None, utilise l'heure locale.
        """
        # Import local pour éviter tout problème de dépendance circulaire au niveau module.
        from corelec.ReverseEngineering.ctypes_frames import FrameBase as CFrameBase
        from corelec.ReverseEngineering.ctypes_frames import Frame77 as CFrame77
        from corelec.ReverseEngineering.ctypes_frames import Frame65 as CFrame65
        from corelec.ReverseEngineering.ctypes_frames import Frame69 as CFrame69
        from corelec.ReverseEngineering.ctypes_frames import Frame83 as CFrame83
        # CFrame77|CFrame65|CFrame69|CFrame83
        _parsers : dict[int, CFrameBase.__class__] = {77: CFrame77, 65: CFrame65, 83: CFrame83, 69: CFrame69}

        if ts is None:
            ts = datetime.now().isoformat()
        decoded_json: str | None = None
        parser = _parsers.get(frame.type)
        if parser is not None:
            try:
                d = parser.from_bytes(frame.raw).as_dict()
                clean = {
                    k: (int(v) if isinstance(v, bool) else v)
                    for k, v in d.items()
                    if not k.startswith('_')
                    and not k.startswith('raw_')
                    and k not in ('type',)
                    and v is not None
                    and isinstance(v, (int, float, bool))
                }
                decoded_json = json.dumps(clean)
            except Exception:
                pass

        with self.lock:
            self.conn.execute(
                "INSERT INTO raw_frames(ts,frame_type,frame_hex) VALUES(?,?,?)",
                (ts, frame.type, frame.raw.hex()),
            )
            if decoded_json is not None:
                self.conn.execute(
                    "INSERT INTO decoded_frames(ts,frame_type,data) VALUES(?,?,?)",
                    (ts, frame.type, decoded_json),
                )
            self.conn.commit()

    def store_decoded(self, decoded: DecodedBase) -> None:
        """No-op : les valeurs décodées sont dérivées des trames brutes par l’UI à l’affichage."""

    def load_decoded_frames_by_type(
        self, frame_type: int, fields: list[str], limit: int = 10000
    ) -> dict[str, list[tuple[str, float]]]:
        """Lit les valeurs décodées directement depuis decoded_frames via json_extract.

        Retourne {field_name: [(ts_iso, float_value), ...]} en ordre chronologique.
        Aucun décodage Python : le parsing JSON est fait côté SQLite.
        """
        sel = ", ".join(f"json_extract(data,'$.{f}')" for f in fields)
        sql = (
            f"SELECT ts, {sel} FROM decoded_frames "
            "WHERE frame_type=? ORDER BY ts DESC LIMIT ?"
        )
        cur = self.conn.cursor()
        cur.execute(sql, (frame_type, limit))
        rows = list(reversed(cur.fetchall()))

        result: dict[str, list[tuple[str, float]]] = {f: [] for f in fields}
        for row in rows:
            ts = row[0]
            for i, f in enumerate(fields):
                v = row[i + 1]
                if v is not None:
                    result[f].append((ts, float(v)))
        return result

    def _backfill_decoded_frames(self) -> None:
        """Migration one-shot : décode toutes les raw_frames existantes dans decoded_frames.
        Appelé automatiquement au démarrage si decoded_frames est vide.
        """
        from corelec.ReverseEngineering.ctypes_frames import FrameBase as CFrameBase
        from corelec.ReverseEngineering.ctypes_frames import Frame77 as CFrame77
        from corelec.ReverseEngineering.ctypes_frames import Frame65 as CFrame65
        from corelec.ReverseEngineering.ctypes_frames import Frame69 as CFrame69
        from corelec.ReverseEngineering.ctypes_frames import Frame83 as CFrame83
        # CFrame77|CFrame65|CFrame69|CFrame83
        _parsers : dict[int, CFrameBase.__class__] = {77: CFrame77, 65: CFrame65, 83: CFrame83, 69: CFrame69}

        logger.info("decoded_frames vide — backfill depuis raw_frames en cours…")
        cur = self.conn.cursor()
        cur.execute("SELECT ts, frame_type, frame_hex FROM raw_frames ORDER BY id")
        rows : list[tuple[str, int, str]] = cur.fetchall()

        batch: list[tuple[str, int, str]] = []
        for ts, frame_type, frame_hex in rows:
            parser = _parsers.get(frame_type)
            if parser is None:
                continue
            try:
                raw = bytearray.fromhex(frame_hex)
                d = parser.from_bytes(raw).as_dict()
                clean = {
                    k: (int(v) if isinstance(v, bool) else v)
                    for k, v in d.items()
                    if not k.startswith('_')
                    and not k.startswith('raw_')
                    and k not in ('type',)
                    and v is not None
                    and isinstance(v, (int, float, bool))
                }
                batch.append((ts, frame_type, json.dumps(clean)))
            except Exception:
                continue

        with self.lock:
            self.conn.executemany(
                "INSERT OR IGNORE INTO decoded_frames(ts,frame_type,data) VALUES(?,?,?)",
                batch,
            )
            self.conn.commit()
        logger.info("Backfill terminé : %d lignes décodées", len(batch))

    def load_history(self, name: str, limit: int = 1000):
        """Retourne les `limit` entrées les plus récentes pour `name`, dédupliquées par timestamp.

        Utilise ORDER BY ts DESC pour rester cohérent après un DB sync (INSERT en vrac),
        et GROUP BY ts pour éviter les doublons si les mêmes données sont insérées plusieurs fois.
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ts, AVG(value) AS value
            FROM decoded_values
            WHERE name=?
            GROUP BY ts
            ORDER BY ts DESC
            LIMIT ?
            """,
            (name, limit),
        )
        return list(reversed(cur.fetchall()))

    def load_raw_frames_history(self, limit: int = 2000) -> list[tuple[str, int, str]]:
        """Return (ts, frame_type, frame_hex) rows sorted by time ASC, last `limit` rows."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT ts, frame_type, frame_hex FROM raw_frames ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(cur.fetchall()))