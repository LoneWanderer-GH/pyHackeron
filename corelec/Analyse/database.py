from __future__ import annotations
from datetime import datetime
from pathlib import Path
import sqlite3
import threading
import logging

from corelec.BLE.frame import Frame
from corelec.ReverseEngineering.decoder import DecodedBase

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, path:str | Path="pool.db"):
        path  : Path = Path(path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            logger.info("DB Path %s exists", path.as_posix())
        else:
            logger.info("DB Path %s does not exist, will create new DB", path.as_posix())
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
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

        self.conn.commit()

    def store_frame(self, frame: Frame):
        ts = datetime.now().isoformat()
        with self.lock:
            self.conn.execute(
                "INSERT INTO raw_frames(ts,frame_type,frame_hex) VALUES(?,?,?)",
                (ts, frame.type, frame.raw.hex()),
            )
            self.conn.commit()

    def store_decoded(self, decoded: DecodedBase) -> None:
        """No-op : les valeurs décodées sont dérivées des trames brutes par l’UI à l’affichage."""

    def load_raw_frames_by_type(self, frame_type: int, limit: int = 2000) -> list:
        """Retourne (ts, frame_hex) pour le type de trame donné, ordre chronologique."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT ts, frame_hex FROM raw_frames WHERE frame_type=? ORDER BY ts DESC LIMIT ?",
            (frame_type, limit),
        )
        return list(reversed(cur.fetchall()))

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

    def load_raw_frames_history(self, limit: int = 2000) -> list:
        """Return (ts, frame_type, frame_hex) rows sorted by time ASC, last `limit` rows."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT ts, frame_type, frame_hex FROM raw_frames ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(cur.fetchall()))