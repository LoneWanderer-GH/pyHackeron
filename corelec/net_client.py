"""
net_client.py — Client réseau Corelec Monitor (côté UI)
========================================================
Abonnement ZMQ SUB au daemon BLE.
Traduit les messages réseau en signaux Qt pour que le Dashboard
fonctionne sans modification, en mode réseau comme en mode BLE direct.

Peut aussi :
  - envoyer des commandes au daemon (retry, cancel, db_sync)
  - reconstruire une DB locale depuis un dump réseau

Compatible Python 3.9+.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any

import zmq

from corelec.UI.signals import QtBridge
from corelec.net_protocol import (
    Topic, decode,
    DEFAULT_PUB_PORT, DEFAULT_CMD_PORT,
)
from corelec.BLE.types import (
    ConnectionInfo, ConnectionMetrics, DecodedBase,
)
from corelec.Analyse.model import RegulatorState
from corelec.Analyse.database import Database
from corelec.ReverseEngineering.decoder import Decoder

logger = logging.getLogger(__name__)


class NetworkClient(threading.Thread):
    """
    Thread ZMQ SUB qui écoute le daemon et émet des signaux Qt.

    Usage :
        client = NetworkClient(host="192.168.1.10", state=state, database=db)
        client.start()
        # Pour envoyer une commande :
        client.send_cmd(Topic.CMD_RETRY)
        client.send_cmd(Topic.CMD_DB_SYNC, {"table": "decoded_values"})
    """

    def __init__(
        self,
        host: str,
        state: RegulatorState,
        database: Database,
        pub_port: int = DEFAULT_PUB_PORT,
        cmd_port: int = DEFAULT_CMD_PORT,
    ):
        super().__init__(daemon=True, name="zmq-sub")
        self.host = host
        self.state = state
        self.database = database
        self.pub_port = pub_port
        self.cmd_port = cmd_port
        self._running = False
        self._gen = 0  # numéro de génération pour invalider les anciens threads
        self._decoder = Decoder()
        # Compteurs pour l’indicateur ZMQ
        self.frames_received: int = 0
        self.last_msg_time: float = 0.0

        # ZMQ contexts (séparés pour SUB et PUSH)
        self._ctx_sub = zmq.Context()
        self._ctx_cmd = zmq.Context()
        self._sock_cmd: zmq.SyncSocket | None = None

    # ------------------------------------------------------------------
    # Envoi de commandes
    # ------------------------------------------------------------------

    def send_cmd(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        """Envoie une commande au daemon (fire-and-forget)."""
        if self._sock_cmd is None:
            self._sock_cmd = self._ctx_cmd.socket(zmq.PUSH)
            self._sock_cmd.connect(f"tcp://{self.host}:{self.cmd_port}")
        parts = [topic.encode()]
        if payload:
            parts.append(json.dumps(payload).encode())
        self._sock_cmd.send_multipart(parts)
        logger.debug("CMD sent: %s %s", topic, payload)

    def request_retry(self) -> None:
        self.send_cmd(Topic.CMD_RETRY)

    def request_cancel(self) -> None:
        self.send_cmd(Topic.CMD_CANCEL)

    def request_db_sync(self, table: str = "decoded_values") -> None:
        self.send_cmd(Topic.CMD_DB_SYNC, {"table": table})

    # ------------------------------------------------------------------
    # Thread SUB
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._running = True
        self._zmq_loop(self._gen)

    def _zmq_loop(self, gen: int) -> None:
        """Boucle ZMQ SUB. S'arrête si _running devient False ou si la génération change."""
        sock = self._ctx_sub.socket(zmq.SUB)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(f"tcp://{self.host}:{self.pub_port}")
        sock.setsockopt_string(zmq.SUBSCRIBE, "corelec/")
        sock.setsockopt(zmq.RCVTIMEO, 1000)  # 1 s timeout pour permettre l'arrêt
        logger.info("ZMQ SUB connected to tcp://%s:%s", self.host, self.pub_port)

        # Import ici pour éviter la dépendance Qt dans le module
        from corelec.UI.signals import signals

        while self._running and self._gen == gen:
            try:
                parts = sock.recv_multipart()
                if len(parts) < 2:
                    continue
                topic, payload = decode(parts[0], parts[1])
                self.frames_received += 1
                self.last_msg_time = time.monotonic()
                self._dispatch(topic, payload, signals)
            except zmq.Again:
                pass  # timeout — boucle normale
            except Exception as e:
                logger.warning("ZMQ recv error: %s", e)

        sock.close()
        try:
            self._ctx_sub.term()
        except Exception:
            pass
        logger.info("NetworkClient ZMQ loop stopped (gen=%d).", gen)

    def stop(self) -> None:
        """Arrêt propre : signale le thread, ferme le socket CMD."""
        self._running = False
        self._gen += 1
        # Fermer le socket de commande (créé côté thread principal)
        if self._sock_cmd is not None:
            try:
                self._sock_cmd.setsockopt(zmq.LINGER, 0)
                self._sock_cmd.close()
            except Exception:
                pass
            self._sock_cmd = None
        try:
            self._ctx_cmd.term()
        except Exception:
            pass

    def reconnect(self) -> None:
        """Re-établit la connexion ZMQ et demande au daemon de retenter BLE."""
        # Arrêter le thread courant en incrémentant la génération
        self._running = False
        self._gen += 1
        # Fermer l’ancien socket CMD
        if self._sock_cmd is not None:
            try:
                self._sock_cmd.setsockopt(zmq.LINGER, 0)
                self._sock_cmd.close()
            except Exception:
                pass
            self._sock_cmd = None
        try:
            self._ctx_cmd.term()
        except Exception:
            pass
        # Recréer les contextes ZMQ
        self._ctx_sub = zmq.Context()
        self._ctx_cmd = zmq.Context()
        # Envoyer CMD_RETRY au daemon (best-effort)
        try:
            self.send_cmd(Topic.CMD_RETRY)
            logger.info("CMD_RETRY envoyé au daemon %s.", self.host)
        except Exception as e:
            logger.debug("CMD_RETRY échoué (daemon inaccessible?) : %s", e)
        # Relancer la boucle ZMQ dans un nouveau thread
        self._running = True
        t = threading.Thread(
            target=self._zmq_loop, args=(self._gen,),
            daemon=True, name="zmq-sub",
        )
        t.start()
        logger.info("ZMQ SUB reconnecté (gen=%d).", self._gen)

    # ------------------------------------------------------------------
    # Dispatch des messages reçus → signaux Qt
    # ------------------------------------------------------------------

    def _dispatch(self, topic: str, payload: dict[str, Any], signals : QtBridge) -> None:
        try:
            if topic == Topic.CONNECTION:
                self._handle_connection(payload, signals)
            elif topic == Topic.STATE:
                self._handle_state(payload, signals)
            elif topic == Topic.VALUE:
                self._handle_value(payload, signals)
            elif topic == Topic.FRAME_RAW:
                self._handle_frame_raw(payload, signals)
            elif topic == Topic.DB_SYNC:
                self._handle_db_sync(payload, signals)
        except Exception as e:
            logger.warning("Dispatch error [%s]: %s", topic, e)

    def _handle_connection(self, p: dict[str, Any], signals : QtBridge) -> None:
        status_name = p.get("status_name", "disconnected")
        m = p.get("metrics", {})
        metrics = ConnectionMetrics(
            packets_sent=m.get("packets_sent", 0),
            packets_received=m.get("packets_received", 0),
            frames_parsed=m.get("frames_parsed", 0),
            rssi=m.get("rssi", 0),
            connection_uptime_s=m.get("uptime_s", 0.0),
        )
        info = ConnectionInfo(
            state=status_name,
            message=p.get("message", ""),
            elapsed=p.get("elapsed", 0),
            remaining=p.get("remaining", 0),
            timeout=p.get("timeout", 0),
            retry_count=p.get("retry_count", 0),
            metrics=metrics,
        )
        signals.connection.emit(info)

    def _handle_state(self, p: dict[str, Any], signals : QtBridge) -> None:
        """Compat ascendante : anciens daemons qui publiaient encore Topic.STATE."""
        for key, value in p.items():
            if hasattr(self.state, key):
                try:
                    setattr(self.state, key, value)
                except Exception:
                    pass
        signals.state_updated.emit()

    def _handle_value(self, p: dict[str, Any], signals : QtBridge) -> None:
        """No-op : les graphiques utilisent désormais raw_frames pour l’historique."""

    def _handle_frame_raw(self, p: dict[str, Any], signals : QtBridge) -> None:
        frame_type = p.get("frame_type", 0)
        hex_str = p.get("hex", "")
        ts = p.get("ts", datetime.now().isoformat())
        try:
            raw = bytearray.fromhex(hex_str)
        except Exception:
            return
        # Stocker la trame brute en DB locale (source unique pour les graphiques)
        try:
            with self.database.lock:
                self.database.conn.execute(
                    "INSERT INTO raw_frames(ts, frame_type, frame_hex) VALUES(?,?,?)",
                    (ts, frame_type, hex_str),
                )
                self.database.conn.commit()
        except Exception as e:
            logger.debug("DB insert raw_frame: %s", e)
        # Décoder côté client — le daemon est un simple passe-plat
        from corelec.BLE.frame import Frame
        frame = Frame.parse(raw)
        if frame:
            try:
                decoded_full = self._decoder.decode(frame)
                self.state.update(decoded_full)
                signals.state_updated.emit()
            except Exception as e:
                logger.debug("Décodage frame_raw: %s", e)
        # Émettre le DecodedBase pour la fenêtre RE (type + raw suffisent)
        signals.reverse.emit(DecodedBase(type=frame_type, raw=raw))

    def _handle_db_sync(self, p: dict[str, Any], signals : QtBridge) -> None:
        """Insère les rows reçues dans la DB locale (reconstruction pour dev)."""
        table = p.get("table", "decoded_values")
        rows = p.get("rows", [])
        chunk_index = p.get("chunk_index", 0)
        total_chunks = p.get("total_chunks", 1)
        logger.debug("DB sync chunk %d/%d table=%s (%d rows)",
                     chunk_index + 1, total_chunks, table, len(rows))
        try:
            with self.database.lock:
                if table == "decoded_values":
                    self.database.conn.executemany(
                        "INSERT OR IGNORE INTO decoded_values(ts, name, value) VALUES(?,?,?)",
                        [(r["ts"], r["name"], r["value"]) for r in rows],
                    )
                elif table == "raw_frames":
                    self.database.conn.executemany(
                        "INSERT OR IGNORE INTO raw_frames(ts, frame_type, frame_hex) VALUES(?,?,?)",
                        [(r["ts"], r["frame_type"], r["hex"]) for r in rows],
                    )
                self.database.conn.commit()
        except Exception as e:
            logger.warning("DB sync insert error: %s", e)
        if chunk_index + 1 == total_chunks:
            logger.info("DB sync complet pour table=%s", table)
            from corelec.core.bus import bus
            bus.db_sync_complete.emit(table)
