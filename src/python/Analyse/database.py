from datetime import datetime
from pathlib import Path
import sqlite3
import threading
import logging

from src.python.BLE.frame import Frame
from src.python.ReverseEngineering.decoder import DecodedBase

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
                (
                    ts,
                    frame.type,
                    frame.raw.hex()
                )
            )

            for idx, value in enumerate(frame.raw):

                self.conn.execute(
                    """
                    INSERT INTO frame_bytes(
                        ts,
                        frame_type,
                        byte_index,
                        value
                    )
                    VALUES(?,?,?,?)
                    """,
                    (
                        ts,
                        frame.type,
                        idx,
                        value
                    )
                )

            self.conn.commit()

    def store_decoded(self, decoded:DecodedBase):

        ts = datetime.now().isoformat()

        with self.lock:

            for k, v in decoded.__dict__.items():

                if isinstance(v, bool):
                    v = int(v)

                if not isinstance(v, (int, float)):
                    continue

                self.conn.execute(
                    """
                    INSERT INTO decoded_values(
                        ts,
                        name,
                        value
                    )
                    VALUES(?,?,?)
                    """,
                    (
                        ts,
                        k,
                        float(v)
                    )
                )

            self.conn.commit()

    def load_history(self, name:str, limit:int=1000):

        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT ts,value
            FROM decoded_values
            WHERE name=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (name, limit)
        )

        return list(reversed(cur.fetchall()))