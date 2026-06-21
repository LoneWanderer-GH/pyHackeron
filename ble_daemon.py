#!/usr/bin/env python3
"""
ble_daemon.py — Démon headless Corelec BLE
===========================================
Connexion BLE → décodage → SQLite + publication ZeroMQ PUB.

Usage :
    python ble_daemon.py [--address B4:E3:F9:5A:0A:13] [--pub-port 5555] [--cmd-port 5556]

Variables d'environnement :
    CORELEC_ADDRESS     Adresse BLE du régulateur
    CORELEC_PUB_PORT    Port ZMQ PUB  (défaut 5555)
    CORELEC_CMD_PORT    Port ZMQ PULL pour commandes (défaut 5556)
    CORELEC_DB_PATH     Chemin vers pool.db (défaut ./pool.db)
    CORELEC_LOG_LEVEL   DEBUG / INFO / WARNING (défaut INFO)

Compatible Python 3.9+, sans Qt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import zmq
import zmq.asyncio

# ---------------------------------------------------------------------------
# Chemin racine pour les imports corelec.*
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.Acquisition import Acquisition
from corelec.BLE.types import ConnectionInfo, DecodedBase
from corelec.net_protocol import (
    ConnStatus, Topic,
    encode, make_connection, make_value, make_state, make_frame_raw,
    make_db_sync_chunk,
    DEFAULT_PUB_PORT, DEFAULT_CMD_PORT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Publisher ZMQ thread-safe
# ---------------------------------------------------------------------------

class ZmqPublisher:
    """Publie des messages ZMQ depuis n'importe quel thread/coroutine."""

    def __init__(self, port: int):
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.bind(f"tcp://*:{port}")
        self._lock = threading.Lock()
        logger.info("ZMQ PUB bound on tcp://*:%s", port)

    def publish(self, topic: str, payload: dict) -> None:
        t, p = encode(topic, payload)
        with self._lock:
            self._sock.send_multipart([t, p])

    def close(self) -> None:
        self._sock.close()
        self._ctx.term()


# ---------------------------------------------------------------------------
# Listener ZMQ pour commandes (PULL)
# ---------------------------------------------------------------------------

class ZmqCommandListener:
    """Écoute les commandes PUSH envoyées par l'UI sur un port dédié."""

    def __init__(self, port: int, on_retry, on_cancel, on_db_sync):
        self._port = port
        self._on_retry = on_retry
        self._on_cancel = on_cancel
        self._on_db_sync = on_db_sync
        self._running = False

    async def run(self) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PULL)
        sock.bind(f"tcp://*:{self._port}")
        logger.info("ZMQ CMD PULL bound on tcp://*:%s", self._port)
        self._running = True
        try:
            while self._running:
                try:
                    parts = await asyncio.wait_for(sock.recv_multipart(), timeout=1.0)
                    if len(parts) >= 1:
                        topic = parts[0].decode()
                        logger.debug("CMD received: %s", topic)
                        if topic == Topic.CMD_RETRY:
                            self._on_retry()
                        elif topic == Topic.CMD_CANCEL:
                            self._on_cancel()
                        elif topic == Topic.CMD_DB_SYNC:
                            payload = json.loads(parts[1]) if len(parts) > 1 else {}
                            self._on_db_sync(payload)
                except asyncio.TimeoutError:
                    pass
        finally:
            sock.close()
            ctx.term()

    def stop(self) -> None:
        self._running = False


# ---------------------------------------------------------------------------
# DB Sync — exporte decoded_values en chunks
# ---------------------------------------------------------------------------

def dump_db_to_zmq(db: Database, pub: ZmqPublisher, table: str = "decoded_values",
                   chunk_size: int = 500) -> None:
    """Exporte une table SQLite complète en chunks ZMQ."""
    try:
        cur = db.conn.cursor()
        if table == "decoded_values":
            cur.execute("SELECT ts, name, value FROM decoded_values ORDER BY id")
            all_rows = [{"ts": r[0], "name": r[1], "value": r[2]} for r in cur.fetchall()]
        elif table == "raw_frames":
            cur.execute("SELECT ts, frame_type, frame_hex FROM raw_frames ORDER BY id")
            all_rows = [{"ts": r[0], "frame_type": r[1], "hex": r[2]} for r in cur.fetchall()]
        else:
            logger.warning("DB sync: table inconnue %s", table)
            return

        total = len(all_rows)
        n_chunks = max(1, (total + chunk_size - 1) // chunk_size)
        logger.info("DB sync: %d rows en %d chunks (table=%s)", total, n_chunks, table)

        for i in range(n_chunks):
            chunk = all_rows[i * chunk_size:(i + 1) * chunk_size]
            pub.publish(Topic.DB_SYNC, make_db_sync_chunk(chunk, table, i, n_chunks))

    except Exception as e:
        logger.error("DB sync error: %s", e)


# ---------------------------------------------------------------------------
# Pont entre signaux Qt (Acquisition utilise signals.*) et ZMQ
# ---------------------------------------------------------------------------
# Acquisition.py émet des signaux Qt — pour le mode headless on les remplace
# par des callbacks directs en monkey-patchant l'objet signals.

class _HeadlessSignals:
    """Remplace l'objet signals Qt par des callbacks purs."""

    def __init__(self):
        self._on_connection = []
        self._on_state_updated = []
        self._on_reverse = []
        self._on_log = []

    # API compatible avec les appels .emit() et .connect() du code existant
    class _Signal:
        def __init__(self):
            self._cbs = []
        def connect(self, cb):
            self._cbs.append(cb)
        def emit(self, *args):
            for cb in self._cbs:
                try:
                    cb(*args)
                except Exception as e:
                    logging.getLogger(__name__).warning("Signal callback error: %s", e)

    def __init__(self):
        self.connection      = self._Signal()
        self.state_updated   = self._Signal()
        self.reverse         = self._Signal()
        self.log             = self._Signal()
        self.error           = self._Signal()
        self.retry_requested = self._Signal()
        self.cancel_requested= self._Signal()


# ---------------------------------------------------------------------------
# Daemon principal
# ---------------------------------------------------------------------------

class BLEDaemon:

    def __init__(self, address: str, pub_port: int, cmd_port: int, db_path: str):
        self.address = address
        self.db = Database(db_path)
        self.state = RegulatorState()
        self.pub = ZmqPublisher(pub_port)

        # Remplacer signals Qt par notre shim headless
        import corelec.UI.signals as _signals_mod
        self._signals = _HeadlessSignals()
        _signals_mod.signals = self._signals

        # Connecter les callbacks
        self._signals.connection.connect(self._on_connection)
        self._signals.state_updated.connect(self._on_state_updated)
        self._signals.reverse.connect(self._on_reverse)
        self._signals.log.connect(self._on_log)

        self.acq = Acquisition(
            address=address,
            state=self.state,
            database=self.db,
            retry_count=0,
        )

        self.cmd_listener = ZmqCommandListener(
            port=cmd_port,
            on_retry=lambda: self._signals.retry_requested.emit(),
            on_cancel=lambda: self._signals.cancel_requested.emit(),
            on_db_sync=lambda p: self._handle_db_sync(p),
        )

        self._stop = False

    # ------------------------------------------------------------------
    # Callbacks signaux → ZMQ
    # ------------------------------------------------------------------

    def _on_connection(self, info: ConnectionInfo) -> None:
        status_map = {
            "connected": ConnStatus.CONNECTED,
            "connecting": ConnStatus.CONNECTING,
            "error": ConnStatus.ERROR,
            "disconnected": ConnStatus.DISCONNECTED,
        }
        status = status_map.get(info.state, ConnStatus.DISCONNECTED)
        m = info.metrics
        payload = make_connection(
            status=status,
            message=info.message,
            elapsed=info.elapsed,
            remaining=info.remaining,
            timeout=info.timeout,
            retry_count=info.retry_count,
            rssi=m.rssi,
            packets_sent=m.packets_sent,
            packets_received=m.packets_received,
            frames_parsed=m.frames_parsed,
            uptime_s=m.connection_uptime_s,
        )
        self.pub.publish(Topic.CONNECTION, payload)
        logger.info("[BLE] %s — %s", info.state, info.message)

    def _on_state_updated(self) -> None:
        try:
            d = asdict(self.state)
            self.pub.publish(Topic.STATE, make_state(d))
            # Publier aussi chaque valeur individuellement
            ts = d.get("timestamp", datetime.now().isoformat())
            for name, value in d.items():
                if name == "timestamp":
                    continue
                if isinstance(value, (int, float, bool)) or value is None:
                    self.pub.publish(Topic.VALUE, make_value(name, value, ts))
        except Exception as e:
            logger.warning("_on_state_updated error: %s", e)

    def _on_reverse(self, decoded: DecodedBase) -> None:
        try:
            ts = datetime.now().isoformat()
            self.pub.publish(
                Topic.FRAME_RAW,
                make_frame_raw(decoded.type, bytes(decoded.raw).hex(), ts),
            )
        except Exception as e:
            logger.warning("_on_reverse error: %s", e)

    def _on_log(self, msg: str) -> None:
        logger.debug("[UI-log] %s", msg)

    def _handle_db_sync(self, payload: dict) -> None:
        table = payload.get("table", "decoded_values")
        logger.info("DB sync requested for table=%s", table)
        threading.Thread(
            target=dump_db_to_zmq,
            args=(self.db, self.pub, table),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    async def _run_acquisition_loop(self) -> None:
        """Boucle de reconnexion — relance Acquisition.run() indéfiniment."""
        retry = 0
        while not self._stop:
            self.acq.retry_count = retry
            try:
                await self.acq.run()
            except Exception as e:
                logger.error("Acquisition error: %s", e)
            if self._stop:
                break
            retry += 1
            logger.info("Reconnexion dans 3 s (essai %d)…", retry)
            await asyncio.sleep(3)

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._run_acquisition_loop()),
            asyncio.create_task(self.cmd_listener.run()),
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for t in tasks:
                t.cancel()
            self.pub.close()
            logger.info("Daemon arrêté.")

    def stop(self) -> None:
        self._stop = True
        self.cmd_listener.stop()
        self._signals.cancel_requested.emit()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Corelec BLE daemon (headless)")
    p.add_argument("--address",  default=os.environ.get("CORELEC_ADDRESS", ""),
                   help="Adresse BLE du régulateur (ex: B4:E3:F9:5A:0A:13)")
    p.add_argument("--pub-port", type=int,
                   default=int(os.environ.get("CORELEC_PUB_PORT", DEFAULT_PUB_PORT)),
                   help=f"Port ZMQ PUB (défaut {DEFAULT_PUB_PORT})")
    p.add_argument("--cmd-port", type=int,
                   default=int(os.environ.get("CORELEC_CMD_PORT", DEFAULT_CMD_PORT)),
                   help=f"Port ZMQ CMD PULL (défaut {DEFAULT_CMD_PORT})")
    p.add_argument("--db-path",  default=os.environ.get("CORELEC_DB_PATH", "pool.db"),
                   help="Chemin vers la base SQLite")
    p.add_argument("--log-level", default=os.environ.get("CORELEC_LOG_LEVEL", "INFO"),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not args.address:
        logger.error(
            "Adresse BLE requise. Utiliser --address ou CORELEC_ADDRESS."
        )
        sys.exit(1)

    daemon = BLEDaemon(
        address=args.address,
        pub_port=args.pub_port,
        cmd_port=args.cmd_port,
        db_path=args.db_path,
    )

    loop = asyncio.get_event_loop()

    def _sig_handler(sig, frame):
        logger.info("Signal %s reçu, arrêt…", sig)
        daemon.stop()
        loop.stop()

    signal.signal(signal.SIGINT,  _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
