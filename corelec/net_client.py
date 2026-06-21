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
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

import zmq

from corelec.net_protocol import (
    Topic, ConnStatus, decode,
    DEFAULT_PUB_PORT, DEFAULT_CMD_PORT,
)
from corelec.BLE.types import (
    ConnectionInfo, ConnectionMetrics, DecodedBase,
)
from corelec.Analyse.model import RegulatorState
from corelec.Analyse.database import Database

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

        # ZMQ contexts (séparés pour SUB et PUSH)
        self._ctx_sub = zmq.Context()
        self._ctx_cmd = zmq.Context()
        self._sock_cmd: zmq.Socket | None = None

    # ------------------------------------------------------------------
    # Envoi de commandes
    # ------------------------------------------------------------------

    def send_cmd(self, topic: str, payload: dict | None = None) -> None:
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
        sock = self._ctx_sub.socket(zmq.SUB)
        sock.setsockopt(zmq.LINGER, 0)  # fermeture immédiate sans attente
        sock.connect(f"tcp://{self.host}:{self.pub_port}")
        # S'abonner à tous les topics corelec/*
        sock.setsockopt_string(zmq.SUBSCRIBE, "corelec/")
        sock.setsockopt(zmq.RCVTIMEO, 1000)  # 1 s timeout pour permettre l'arrêt
        logger.info("ZMQ SUB connected to tcp://%s:%s", self.host, self.pub_port)
        self._running = True

        # Import ici pour éviter la dépendance Qt dans le module
        from corelec.UI.signals import signals

        while self._running:
            try:
                parts = sock.recv_multipart()
                if len(parts) < 2:
                    continue
                topic, payload = decode(parts[0], parts[1])
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
        logger.info("NetworkClient stopped.")

    def stop(self) -> None:
        """Arrêt propre : signale le thread, ferme le socket CMD."""
        self._running = False
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

    # ------------------------------------------------------------------
    # Dispatch des messages reçus → signaux Qt
    # ------------------------------------------------------------------

    def _dispatch(self, topic: str, payload: dict, signals) -> None:
        try:
            if topic == Topic.CONNECTION:
                self._handle_connection(payload, signals)
            elif topic == Topic.STATE:
                self._handle_state(payload, signals)
            elif topic == Topic.VALUE:
                self._handle_value(payload)
            elif topic == Topic.FRAME_RAW:
                self._handle_frame_raw(payload, signals)
            elif topic == Topic.DB_SYNC:
                self._handle_db_sync(payload)
        except Exception as e:
            logger.warning("Dispatch error [%s]: %s", topic, e)

    def _handle_connection(self, p: dict, signals) -> None:
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

    def _handle_state(self, p: dict, signals) -> None:
        # Mettre à jour l'état courant directement
        for key, value in p.items():
            if hasattr(self.state, key):
                try:
                    setattr(self.state, key, value)
                except Exception:
                    pass
        signals.state_updated.emit()

    def _handle_value(self, p: dict) -> None:
        # Stocker dans la DB locale pour les graphiques
        name = p.get("name")
        value = p.get("value")
        ts = p.get("ts", datetime.now().isoformat())
        if name is None or value is None:
            return
        if not isinstance(value, (int, float, bool)):
            return
        try:
            with self.database.lock:
                self.database.conn.execute(
                    "INSERT INTO decoded_values(ts, name, value) VALUES(?,?,?)",
                    (ts, name, float(value)),
                )
                self.database.conn.commit()
        except Exception as e:
            logger.debug("DB insert error: %s", e)

    def _handle_frame_raw(self, p: dict, signals) -> None:
        # Reconstruire un DecodedBase minimal pour le panneau reverse
        frame_type = p.get("frame_type", 0)
        hex_str = p.get("hex", "")
        try:
            raw = bytearray.fromhex(hex_str)
        except Exception:
            return
        decoded = DecodedBase(type=frame_type, raw=raw)
        signals.reverse.emit(decoded)

    def _handle_db_sync(self, p: dict) -> None:
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
