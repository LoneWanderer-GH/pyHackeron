#!/usr/bin/env python3
"""
ble_daemon.py — Démon headless Corelec BLE
===========================================
Rôle : passe-plat BLE → ZMQ.

Le daemon se limite à :
  - recevoir les trames BLE brutes
  - les stocker dans raw_frames (SQLite)
  - les republier telles quelles sur Topic.FRAME_RAW

Tout décodage (RegulatorState, graphiques…) est fait côté client (UI / net_client).
Cela permet de faire évoluer le décodage sans redémarrer le daemon.

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
from datetime import datetime
from pathlib import Path

import zmq
import zmq.asyncio

# ---------------------------------------------------------------------------
# Chemin racine pour les imports corelec.*
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent  # répertoire contenant ble_daemon.py
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.Acquisition import Acquisition
from corelec.BLE.types import ConnectionInfo, DecodedBase
from corelec.core.bus import bus
from corelec.net_protocol import (
    ConnStatus, Topic,
    encode, make_connection, make_frame_raw,
    make_db_sync_chunk,
    DEFAULT_PUB_PORT, DEFAULT_CMD_PORT, FRAME_LABELS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tableau de bord console — via rich (optionnel, pip install rich)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console as _Console
    from rich.live    import Live      as _Live
    from rich.logging import RichHandler as _RichHandler
    from rich.panel   import Panel     as _Panel
    from rich.table   import Table     as _Table
    from rich.text    import Text      as _Text
    from rich         import box       as _rich_box
    _RICH = True
except ImportError:
    _RICH = False


class StatusBoard:
    """Panneau de suivi persistant (rich.Live) — état BLE + compteurs de trames.

    Le panneau se rafraîchit toutes les 2 s dans un thread dédié.
    Les logs Python utilisent le même Console, donc ils s'affichent
    proprement au-dessus du panneau sans se télescoper.
    """

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._start = time.monotonic()
        # état connexion BLE
        self.conn_state:   str   = "attente"
        self.conn_message: str   = ""
        self.retry:        int   = 0
        self.rssi:         int   = 0
        self.ble_uptime:   float = 0.0
        self.conn_elapsed: int   = 0
        self.conn_timeout: int   = 120
        self.pkt_sent:     int   = 0
        self.pkt_recv:     int   = 0
        # compteurs de trames par type
        self.frames: dict[int, int] = {65: 0, 69: 0, 77: 0, 83: 0}
        # horodatages
        self.conn_established_at: datetime | None = None
        self.last_frame_ts: dict[int, datetime | None] = {65: None, 69: None, 77: None, 83: None}

    # ---------------------------------------------------------------- mise à jour

    def update_connection(self, info: ConnectionInfo) -> None:
        m = info.metrics
        with self._lock:
            prev_state = self.conn_state
            self.conn_state   = info.state
            self.conn_message = (info.message or "")[:55]
            self.retry        = info.retry_count
            self.rssi         = m.rssi
            self.ble_uptime   = m.connection_uptime_s
            self.pkt_sent     = m.packets_sent
            self.pkt_recv     = m.packets_received
            self.conn_elapsed = info.elapsed
            self.conn_timeout = info.timeout or 120
            if info.state == "connected" and prev_state != "connected":
                self.conn_established_at = datetime.now()

    def add_frame(self, frame_type: int) -> None:
        with self._lock:
            if frame_type in self.frames:
                self.frames[frame_type] += 1
                self.last_frame_ts[frame_type] = datetime.now()

    # ---------------------------------------------------------------- rendu rich

    def build(self):
        """Construit le Panel Rich à afficher."""
        with self._lock:
            up    = time.monotonic() - self._start
            total = sum(self.frames.values())
            fps   = total / max(up, 1)
            state_style = {
                "connected":    "bold green",
                "connecting":   "yellow",
                "error":        "bold red",
                "disconnected": "dim white",
            }.get(self.conn_state, "white")

            # Horodatage de connexion BLE
            est_str = self.conn_established_at.strftime("%Y-%m-%d %H:%M:%S") \
                if self.conn_established_at else "—"

            # Silence : âge du dernier paquet BLE reçu (tous types confondus)
            all_ts = [ts for ts in self.last_frame_ts.values() if ts is not None]
            if all_ts:
                last_any = max(all_ts)
                silence_s = (datetime.now() - last_any).total_seconds()
                if silence_s < 60:
                    silence_str = f"{silence_s:.0f}s"
                    silence_style = "bold green" if silence_s < 10 else "yellow"
                else:
                    silence_str = f"{silence_s/60:.1f}m"
                    silence_style = "bold red"
            else:
                silence_str, silence_style = "—", "dim"

            # Formatage count + âge pour un type de trame
            def _frame_cell(ftype: int) -> _Text:
                count = self.frames[ftype]
                ts = self.last_frame_ts.get(ftype)
                if ts:
                    age = (datetime.now() - ts).total_seconds()
                    suffix = f"  ({age:.0f}s)" if age < 120 else f"  ({age/60:.0f}m)"
                else:
                    suffix = ""
                return _Text(f"{count}{suffix}", style="bold cyan")

            tbl = _Table(box=_rich_box.SIMPLE, show_header=False, expand=True,
                         padding=(0, 2))
            tbl.add_column(style="dim cyan",  no_wrap=True, ratio=3)
            tbl.add_column(no_wrap=True, ratio=4)
            tbl.add_column(style="dim cyan",  no_wrap=True, ratio=3)
            tbl.add_column(no_wrap=True, ratio=3)

            tbl.add_row("BLE",
                        _Text(f"● {self.conn_state.upper()}", style=state_style),
                        "Daemon",     f"actif {up:.0f}s")
            # Ligne 2 : message + indicateur connecting/retry
            if self.conn_state == "connecting" and self.conn_timeout > 0:
                pct = min(1.0, self.conn_elapsed / self.conn_timeout)
                filled = int(pct * 16)
                bar_str = "\u2588" * filled + "\u2591" * (16 - filled)
                conn_detail = _Text(
                    f"[{bar_str}] {self.conn_elapsed}/{self.conn_timeout}s  essai {self.retry}",
                    style="yellow",
                )
            elif self.conn_state == "error":
                conn_detail = _Text(self.conn_message or "\u2014", style="bold red", overflow="ellipsis")
            else:
                conn_detail = _Text(self.conn_message or "\u2014", overflow="ellipsis")
            tbl.add_row("",
                        conn_detail,
                        "Retries",    _Text(str(self.retry), style="bold yellow" if self.retry > 5 else "white"))
            tbl.add_row("BLE établi",
                        _Text(est_str, style="dim white"),
                        "Silence",    _Text(silence_str, style=silence_style))
            tbl.add_row("RSSI",
                        f"{self.rssi} dBm" if self.rssi else "—",
                        "Uptime BLE", f"{self.ble_uptime:.0f}s")
            tbl.add_row("Pkt BLE",
                        f"↑{self.pkt_sent}  ↓{self.pkt_recv}",
                        "Trames/s",   f"{fps:.2f}")
            tbl.add_section()
            tbl.add_row("Total trames",
                        _Text(str(total), style="bold white"),
                        FRAME_LABELS[77],
                        _frame_cell(77))
            tbl.add_row(FRAME_LABELS[65],
                        _frame_cell(65),
                        FRAME_LABELS[83],
                        _frame_cell(83))
            tbl.add_row(FRAME_LABELS[69],
                        _frame_cell(69),
                        "", "")

        return _Panel(tbl,
                      title="[bold cyan]  Corelec BLE Daemon  [/bold cyan]",
                      border_style="cyan", expand=True)

    # ---------------------------------------------------------------- thread rafraîchissement

    def start_refresh(self, live, interval: float = 2.0) -> threading.Thread:
        """Démarre un thread qui rafraîchit le panneau toutes les `interval` secondes."""
        self._stop_evt: threading.Event = threading.Event()

        def _loop() -> None:
            while not self._stop_evt.is_set():
                try:
                    live.update(self.build(), refresh=True)
                except Exception:
                    pass
                self._stop_evt.wait(interval)

        t = threading.Thread(target=_loop, daemon=True, name="board-refresh")
        t.start()
        return t

    def stop_refresh(self) -> None:
        if hasattr(self, "_stop_evt"):
            self._stop_evt.set()


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

    def __init__(self, port: int, on_retry, on_cancel, on_db_sync, on_ble_command=None):
        self._port = port
        self._on_retry = on_retry
        self._on_cancel = on_cancel
        self._on_db_sync = on_db_sync
        self._on_ble_command = on_ble_command
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
                        elif topic == Topic.CMD_BLE_COMMAND:
                            if self._on_ble_command is not None:
                                payload = json.loads(parts[1]) if len(parts) > 1 else {}
                                self._on_ble_command(payload)
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
# Daemon principal
# ---------------------------------------------------------------------------

class BLEDaemon:

    def __init__(self, address: str, pub_port: int, cmd_port: int, db_path: str,
                 board: StatusBoard | None = None,
                 poll_interval_s: float = 5.0):
        self.address = address
        self.db = Database(db_path)
        self.state = RegulatorState()
        self.pub = ZmqPublisher(pub_port)

        # Connecter le bus d'événements aux callbacks ZMQ
        bus.connection.connect(self._on_connection)
        # bus.state_updated.connect(self._on_state_updated)
        bus.reverse.connect(self._on_reverse)
        bus.log.connect(self._on_log)

        self.acq = Acquisition(
            address=address,
            state=self.state,
            database=self.db,
            retry_count=0,
            poll_interval_s=poll_interval_s,
        )

        self.cmd_listener = ZmqCommandListener(
            port=cmd_port,
            on_retry=lambda: bus.retry_requested.emit(),
            on_cancel=lambda: bus.cancel_requested.emit(),
            on_db_sync=lambda p: self._handle_db_sync(p),
            on_ble_command=lambda p: self.acq._on_ble_command(p),
        )

        self._stop = False
        self.board = board
        self._last_conn_payload: dict | None = None
        self._last_conn_state:   str         = ""

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
        self._last_conn_payload = payload
        if self.board:
            self.board.update_connection(info)
        # Ne loguer qu'au changement d'état pour éviter le spam pendant les retries.
        # "connecting" : DEBUG (très fréquent pendant le timeout).
        # "error"      : WARNING (indique un échec à retenir).
        if info.state != self._last_conn_state:
            if info.state in ('connected', 'disconnected'):
                logger.info("[BLE] %s \u2014 %s", info.state, info.message)
            elif info.state == 'error':
                logger.warning("[BLE] erreur \u2014 %s", info.message)
            else:  # 'connecting'
                logger.debug("[BLE] %s \u2014 %s", info.state, info.message)
            self._last_conn_state = info.state
        else:
            logger.debug("[BLE] %s \u2014 %s", info.state, info.message)

    def _on_state_updated(self) -> None:
        try:
            d = asdict(self.state)
            self.pub.publish(Topic.STATE, make_state(d))
            # Re-publier l’état de connexion courant pour les clients qui viennent
            # de se connecter (ils ont manqué l’événement initial).
            if self._last_conn_payload is not None:
                self.pub.publish(Topic.CONNECTION, self._last_conn_payload)
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
        if self.board:
            self.board.add_frame(decoded.type)

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

    async def _heartbeat_loop(self) -> None:
        """Republish connection state every 5 s so late-joining UIs get BLE status."""
        while not self._stop:
            await asyncio.sleep(5)
            if self._last_conn_payload is not None:
                try:
                    self.pub.publish(Topic.CONNECTION, self._last_conn_payload)
                except Exception:
                    pass

    async def _run_acquisition_loop(self) -> None:
        """Boucle de reconnexion avec backoff progressif (3 s → 30 s max)."""
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
            # Backoff : de 3 s à 30 s. Permet au régulateur de démarrer
            # sans inonder le stack BLE de tentatives de connexion.
            delay = min(3.0 + retry * 1.0, 30.0)
            if retry <= 3 or retry % 20 == 0:
                logger.info("Reconnexion dans %.0fs (essai %d)…", delay, retry)
            else:
                logger.debug("Reconnexion dans %.0fs (essai %d)…", delay, retry)
            await asyncio.sleep(delay)

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._run_acquisition_loop()),
            asyncio.create_task(self.cmd_listener.run()),
            asyncio.create_task(self._heartbeat_loop()),
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
        bus.cancel_requested.emit()


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
    p.add_argument("--poll-interval", type=float,
                   default=float(os.environ.get("CORELEC_POLL_INTERVAL", "5.0")),
                   help="Intervalle de polling BLE en secondes (défaut 5.0)")
    p.add_argument("--log-level", default=os.environ.get("CORELEC_LOG_LEVEL", "INFO"),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # --- Logging : RichHandler si rich est disponible, sinon basicConfig standard ---
    _console = None
    if _RICH:
        _console = _Console()
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[_RichHandler(
                console=_console,
                show_path=False,
                log_time_format="[%H:%M:%S]",
                markup=False,
            )],
        )
    else:
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

    board = StatusBoard() if _RICH else None

    daemon = BLEDaemon(
        address=args.address,
        pub_port=args.pub_port,
        cmd_port=args.cmd_port,
        db_path=args.db_path,
        board=board,
        poll_interval_s=args.poll_interval,
    )

    loop = asyncio.get_event_loop()

    def _sig_handler(sig, frame):
        logger.info("Signal %s reçu, arrêt…", sig)
        daemon.stop()
        loop.stop()

    signal.signal(signal.SIGINT,  _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    def _run() -> None:
        try:
            loop.run_until_complete(daemon.run())
        except RuntimeError:
            pass  # loop stopped via loop.stop() dans le signal handler
        finally:
            loop.close()

    if _RICH and board and _console:
        with _Live(board.build(), console=_console, auto_refresh=False) as live:
            board.start_refresh(live, interval=2.0)
            try:
                _run()
            finally:
                board.stop_refresh()
    else:
        _run()


if __name__ == "__main__":
    main()
