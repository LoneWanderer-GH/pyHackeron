from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json
import sqlite3
import threading
import time as _time
import logging

from corelec.BLE.frame import Frame
from corelec.ReverseEngineering.decoder import DecodedBase

logger = logging.getLogger(__name__)


def _shift_ts(ts_iso: str, delta_s: int) -> str:
    """Retourne ts_iso + delta_s secondes (format ISO 'YYYY-MM-DD HH:MM:SS').

    ts_iso provient de SQLite datetime(...,'unixepoch') : 'YYYY-MM-DD HH:MM:SS'.
    Utilisé par load_decoded_frames_tiered pour placer le point MAX au milieu
    du bucket des champs en échelon.
    """
    dt = datetime.fromisoformat(ts_iso.replace(' ', 'T'))
    return (dt + timedelta(seconds=delta_s)).strftime('%Y-%m-%d %H:%M:%S')


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
        decoded_values  conservée pour compatibilité, n'est plus écrite
        frame_bytes     conservée pour compatibilité, n'est plus écrite

    Agrégation tiered (load_decoded_frames_tiered) :
        - Champs continus (pH, temp…)      → AVG() par bucket
        - Champs d'alarme                  → MAX() par bucket
        - Champs en échelon/compteur       → MIN()+MAX() par bucket
          (transitions et remises à zéro préservées)

    Thread-safe : toutes les écritures utilisent ``self.lock``.
    """
    _HIST_TIERS: list[tuple[float, int]] = [
        (    24 * 3600,     60),   # < 24 h         → 1 pt / 60 s  (≈ 1 440 pts/j)
        ( 7 * 24 * 3600,   300),   # 24 h – 7 j     → 1 pt / 5 min (≈ 2 016 pts)
        (30 * 24 * 3600, 1_800),   # 7 j – 30 j     → 1 pt / 30 min (≈ 1 104 pts)
        (float('inf'),   7_200),   # > 30 j          → 1 pt / 2 h
    ]

    # Champs dont le signal est continu et lentement variable :
    # avg() par bucket conserve bien la valeur.
    _SMOOTH_FIELDS: frozenset = frozenset({
        'ph', 'redox', 'temp', 'sel',
        'ph_consigne', 'err_max', 'err_min', 'redox_consigne',
    })

    # Champs d'alarme / code d'état : MAX() pour ne jamais perdre une alarme.
    _ALARM_FIELDS: frozenset = frozenset({
        'alarme', 'warning', 'alarm_rdx', 'elx_fault_code',
    })

    # Tous les autres champs sont traités comme des échelons / compteurs
    # (MIN + MAX par bucket) pour préserver les transitions et remises à zéro.
    # Ex : inversion_timer_min (dent de scie), boost_remaining_min,
    #      current_electrolyse_percent, polarity_phase_a, etc.



    def __init__(self, path:str | Path="pool.db", sparse_heartbeat_s: float = 60.0):
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

        # Mode WAL : lectures non bloquantes pendant les écritures, meilleure
        # robustesse pour un fonctionnement prolongé (jours / semaines).
        # synchronous=NORMAL : sécurité suffisante avec WAL (pas de fsync à chaque commit).
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA wal_autocheckpoint=1000")  # checkpoint auto toutes les 1000 pages

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

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS connection_events(
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      TEXT    NOT NULL,
            event   TEXT    NOT NULL,
            message TEXT    DEFAULT ''
        )
        """)
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_conn_events_ts
        ON connection_events(ts)
        """)

        self.conn.commit()

        # Cache pour stockage éparse : seulement stocker si les données changent
        # ou si sparse_heartbeat_s secondes se sont écoulées depuis le dernier stockage.
        self.sparse_heartbeat_s = sparse_heartbeat_s
        self._sparse_json: dict[int, str]   = {}   # dernière JSON stockée par frame_type
        self._sparse_ts:   dict[int, float] = {}   # monotonic du dernier stockage

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
                decoded_json = json.dumps(clean, sort_keys=True)
            except Exception:
                pass

        # Stockage éparse : seulement stocker si les données ont changé ou si le
        # heartbeat est échu, pour réduire le volume en BD lors de valeurs stables.
        now_mono = _time.monotonic()
        last_json = self._sparse_json.get(frame.type)
        last_ts   = self._sparse_ts.get(frame.type, 0.0)
        should_store = (
            decoded_json is None                              # type inconnu
            or last_json is None                              # premier échantillon
            or (now_mono - last_ts) >= self.sparse_heartbeat_s  # heartbeat échu
            or last_json != decoded_json                      # valeur changée
        )
        if not should_store:
            return
        if decoded_json is not None:
            self._sparse_json[frame.type] = decoded_json
            self._sparse_ts[frame.type]   = now_mono

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
        self, frame_type: int, fields: list[str], limit: int = 10000,
        display_step_s: float = 0.0,
    ) -> dict[str, list[tuple[str, float]]]:
        """Lit les valeurs décodées depuis decoded_frames.

        ``display_step_s > 0`` active un élagage côté Python : on ne garde qu'un
        point par fenêtre de ``display_step_s`` secondes, ce qui réduit
        considérablement le nombre de points tracés.
        """
        sel = ", ".join(f"json_extract(data,'$.{f}')" for f in fields)
        sql = (
            f"SELECT ts, {sel} FROM decoded_frames "
            "WHERE frame_type=? ORDER BY ts DESC LIMIT ?"
        )
        cur = self.conn.cursor()
        cur.execute(sql, (frame_type, limit))
        rows = list(reversed(cur.fetchall()))

        # Élagage par pas de temps (stride Python) pour réduire les points affichés
        if display_step_s > 0 and rows:
            strided: list = []
            last_epoch: float | None = None
            for row in rows:
                try:
                    epoch = datetime.fromisoformat(row[0]).timestamp()
                except Exception:
                    continue
                if last_epoch is None or epoch - last_epoch >= display_step_s:
                    strided.append(row)
                    last_epoch = epoch
            rows = strided

        result: dict[str, list[tuple[str, float]]] = {f: [] for f in fields}
        for row in rows:
            ts = row[0]
            for i, f in enumerate(fields):
                v = row[i + 1]
                if v is not None:
                    result[f].append((ts, float(v)))
        return result

    def load_decoded_frames_tiered(
        self,
        frame_type: int,
        fields: list[str],
        tiers: list[tuple[float, int]] | None = None,
    ) -> dict[str, list[tuple[str, float]]]:
        """Chargement multi-paliers avec agrégation adaptée au type de champ.

        Trois stratégies SQL selon la nature du champ :

        · **smooth** (_SMOOTH_FIELDS)  : AVG() — signal continu, le lissage
          est souhaitable (pH, redox, température...).

        · **alarm**  (_ALARM_FIELDS)   : MAX() — on ne perd jamais un code
          d'alarme actif.

        · **step**   (tous les autres) : MIN() + MAX() par bucket.
          Si min ≈ max (Δ < 0.5) → valeur stable, on n'émet qu'un seul point.
          Sinon → deux points : (ts_bucket, min) et (ts_bucket + bucket//2, max).
          Cela préserve les transitions d'échelons, les remises à zéro des
          compteurs (dent de scie de polarité) et les activations boost.

        Paramètres
        ----------
        tiers : [(age_max_s, bucket_s), ...].  None → _HIST_TIERS.
        """
        if tiers is None:
            tiers = self._HIST_TIERS

        result: dict[str, list[tuple[str, float]]] = {f: [] for f in fields}
        now_s = _time.time()

        # —— Classement des champs et construction du SELECT dynamique ———————
        # col_info : [(field_name, 'avg' | 'single' | 'min' | 'max'), ...]
        # Un champ STEP génère DEUX entrées consécutives ('min' puis 'max').
        sel_parts: list[str] = []
        col_info:  list[tuple[str, str]] = []
        for f in fields:
            if f in self._SMOOTH_FIELDS:
                sel_parts.append(f"AVG(json_extract(data,'$.{f}'))")
                col_info.append((f, 'avg'))
            elif f in self._ALARM_FIELDS:
                sel_parts.append(f"MAX(json_extract(data,'$.{f}'))")
                col_info.append((f, 'single'))
            else:  # step / counter / binary
                sel_parts.append(f"MIN(json_extract(data,'$.{f}'))")
                sel_parts.append(f"MAX(json_extract(data,'$.{f}'))")
                col_info.append((f, 'min'))
                col_info.append((f, 'max'))
        sel = ", ".join(sel_parts)

        upper_s: float | None = None

        for age_max_s, bucket_s in tiers:
            lower_s: float | None = (
                now_s - age_max_s if age_max_s != float('inf') else None
            )

            where_parts = ["frame_type=?"]
            params: list = [bucket_s, bucket_s, frame_type]
            if upper_s is not None:
                where_parts.append("ts < ?")
                params.append(datetime.utcfromtimestamp(upper_s).isoformat())
            if lower_s is not None:
                where_parts.append("ts >= ?")
                params.append(datetime.utcfromtimestamp(lower_s).isoformat())

            where = " AND ".join(where_parts)
            sql = (
                f"SELECT datetime(CAST(strftime('%s',ts)/?  AS INTEGER)*?,'unixepoch') AS ts_b,"
                f" {sel}"
                f" FROM decoded_frames WHERE {where}"
                f" GROUP BY ts_b ORDER BY ts_b"
            )
            cur = self.conn.cursor()
            cur.execute(sql, params)

            for row in cur.fetchall():
                ts_b = row[0]
                if ts_b is None:
                    continue

                # Accumule les min/max des champs STEP pour émission en fin de ligne
                pending: dict[str, dict[str, float]] = {}  # field → {'min': v, 'max': v}

                for col_i, (f, agg) in enumerate(col_info):
                    v = row[col_i + 1]
                    if v is None:
                        continue
                    v = float(v)
                    if agg in ('avg', 'single'):
                        result[f].append((ts_b, v))
                    elif agg == 'min':
                        pending.setdefault(f, {})['min'] = v
                    elif agg == 'max':
                        pending.setdefault(f, {})['max'] = v

                # Émission des points pour les champs STEP
                for f, mm in pending.items():
                    mn = mm.get('min')
                    mx = mm.get('max')
                    if mn is None and mx is None:
                        continue
                    if mn is None:
                        result[f].append((ts_b, mx))  # type: ignore[arg-type]
                    elif mx is None:
                        result[f].append((ts_b, mn))
                    elif mx - mn < 0.5:
                        # Valeur stable dans ce bucket → un seul point
                        result[f].append((ts_b, (mn + mx) / 2.0))
                    else:
                        # Transition détectée : émettre min en début de bucket
                        # et max au milieu pour préserver la plage.
                        ts_mid = _shift_ts(ts_b, bucket_s // 2)
                        result[f].append((ts_b,  mn))
                        result[f].append((ts_mid, mx))

            upper_s = lower_s
            if lower_s is None:
                break

        # Re-tri ASC (paliers parcourus récent → ancien → points mélangés)
        for f in fields:
            result[f].sort(key=lambda t: t[0])

        return result

    def log_connection_event(self, event: str, message: str = '') -> None:
        """Enregistre un événement de connexion/déconnexion BLE."""
        ts = datetime.now().isoformat()
        try:
            with self.lock:
                self.conn.execute(
                    "INSERT INTO connection_events(ts, event, message) VALUES(?,?,?)",
                    (ts, event, message[:200]),
                )
                self.conn.commit()
        except Exception as exc:
            logger.debug("log_connection_event error: %s", exc)

    def load_connection_events(
        self, limit: int = 500
    ) -> list[tuple[str, str, str]]:
        """Retourne [(ts, event, message), ...] en ordre chronologique."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT ts, event, message FROM connection_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(cur.fetchall()))

    def load_decoded_frames_since(
        self, frame_type: int, fields: list[str], min_id: int
    ) -> list:   # list[tuple[int, str, ...]]
        """Requête incrémentale : lignes de decoded_frames avec id > min_id.

        Retourne des tuples ``(id, ts, val_f1, val_f2, …)`` en ordre ASC.
        Utilisé par le cache de l'historique du dashboard pour n'interroger
        que les nouvelles lignes entre deux rafraîchissements.
        """
        sel = ", ".join(f"json_extract(data,'$.{f}')" for f in fields)
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT id, ts, {sel} FROM decoded_frames "
            "WHERE frame_type=? AND id > ? ORDER BY id ASC",
            (frame_type, min_id),
        )
        return cur.fetchall()

    def get_max_decoded_frame_id(self, frame_type: int) -> int:
        """Retourne le plus grand id dans decoded_frames pour frame_type, ou 0."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT MAX(id) FROM decoded_frames WHERE frame_type=?", (frame_type,)
        )
        r = cur.fetchone()
        return (r[0] or 0) if r else 0

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
                batch.append((ts, frame_type, json.dumps(clean, sort_keys=True)))
            except Exception:
                continue

        with self.lock:
            self.conn.executemany(
                "INSERT OR IGNORE INTO decoded_frames(ts,frame_type,data) VALUES(?,?,?)",
                batch,
            )
            self.conn.commit()
        logger.info("Backfill terminé : %d lignes décodées", len(batch))

    def force_redecode(self) -> int:
        """Efface decoded_frames et re-décode tous les raw_frames depuis zéro."""
        logger.info("force_redecode : suppression de decoded_frames…")
        # Vider le cache éparse pour forcer un re-stockage après redecode
        self._sparse_json.clear()
        self._sparse_ts.clear()
        with self.lock:
            self.conn.execute("DELETE FROM decoded_frames")
            self.conn.commit()
        self._backfill_decoded_frames()
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM decoded_frames")
        return cur.fetchone()[0]

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