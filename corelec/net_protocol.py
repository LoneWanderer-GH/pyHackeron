"""
net_protocol.py — Protocole réseau Corelec Monitor
====================================================
Sérialisation JSON sur ZeroMQ PUB/SUB.

Format d'un message sur le bus :
    topic|{json}

Topics définis dans Topic.*  — chaînes ASCII stables, compatibles MQTT / HA / Jeedom.

Codes de statut (champ "status" dans CONNECTION):
    0   disconnected
    1   connecting
    2   connected
    3   error

Compatibilité : Python 3.9+, pas de dépendances Qt.
"""
from __future__ import annotations

import json
from enum import IntEnum
from typing import Any


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

class Topic:
    """Topics ZMQ/MQTT stables — ne pas renommer pour la compatibilité HA/Jeedom."""

    # Statut de connexion BLE
    CONNECTION = "corelec/connection"

    # Valeur décodée : un paquet par champ
    # payload: {"name": "ph", "value": 7.12, "ts": "..."}
    VALUE = "corelec/value"

    # Trame brute (reverse engineering)
    # payload: {"frame_type": 77, "hex": "2a4d...2a", "ts": "..."}
    FRAME_RAW = "corelec/frame/raw"

    # Snapshot complet de l'état du régulateur (toutes les 2 s)
    STATE = "corelec/state"

    # Réponse à une requête de sync DB (tableaux de rows raw_frames)
    # payload: {"table": "raw_frames", "rows": [...], "chunk_index": 0, "total_chunks": 1}
    DB_SYNC = "corelec/db/sync"

    # Commandes UI → daemon
    CMD_RETRY   = "corelec/cmd/retry"
    CMD_CANCEL  = "corelec/cmd/cancel"
    CMD_DB_SYNC = "corelec/cmd/db_sync"     # demande un dump raw_frames depuis le daemon
    CMD_BLE_COMMAND = "corelec/cmd/ble_command"  # commande d'écriture GATT
    CMD_COMPACT_DB  = "corelec/cmd/compact_db"   # nettoyage / compression de la base de données


# ---------------------------------------------------------------------------
# Codes de statut connexion
# ---------------------------------------------------------------------------

class ConnStatus(IntEnum):
    DISCONNECTED = 0
    CONNECTING   = 1
    CONNECTED    = 2
    ERROR        = 3


# ---------------------------------------------------------------------------
# Construction des payloads
# ---------------------------------------------------------------------------

def encode(topic: str, payload: dict[str, Any]) -> tuple[bytes, bytes]:
    """Retourne (topic_bytes, json_bytes) prêt pour zmq.Socket.send_multipart."""
    return topic.encode(), json.dumps(payload, default=str).encode()


def decode(topic_bytes: bytes, json_bytes: bytes) -> tuple[str, dict[str, Any]]:
    """Décode un message reçu depuis ZMQ send_multipart."""
    return topic_bytes.decode(), json.loads(json_bytes)


# ---------------------------------------------------------------------------
# Helpers de construction des payloads par topic
# ---------------------------------------------------------------------------

def make_connection(
    status: ConnStatus,
    message: str,
    elapsed: int = 0,
    remaining: int = 0,
    timeout: int = 0,
    retry_count: int = 0,
    rssi: int = 0,
    packets_sent: int = 0,
    packets_received: int = 0,
    frames_parsed: int = 0,
    uptime_s: float = 0.0,
) -> dict[str, Any]:
    return {
        "status": int(status),
        "status_name": status.name.lower(),
        "message": message,
        "elapsed": elapsed,
        "remaining": remaining,
        "timeout": timeout,
        "retry_count": retry_count,
        "metrics": {
            "rssi": rssi,
            "packets_sent": packets_sent,
            "packets_received": packets_received,
            "frames_parsed": frames_parsed,
            "uptime_s": uptime_s,
        },
    }


def make_value(name: str, value: Any, ts: str) -> dict[str, Any]:
    return {"name": name, "value": value, "ts": ts}


def make_state(state_dict: dict[str, Any]) -> dict[str, Any]:
    """state_dict = RegulatorState.__dict__ ou asdict(state)."""
    return state_dict


def make_frame_raw(frame_type: int, hex_str: str, ts: str) -> dict[str, Any]:
    return {"frame_type": frame_type, "hex": hex_str, "ts": ts}


def make_db_sync_chunk(
    rows: list[dict[str, Any]],
    table: str,
    chunk_index: int,
    total_chunks: int,
) -> dict[str, Any]:
    return {
        "table": table,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Ports par défaut
# ---------------------------------------------------------------------------

DEFAULT_PUB_PORT = 5555   # daemon publie ici
DEFAULT_SUB_PORT = 5555   # UI s'abonne ici
DEFAULT_CMD_PORT = 5556   # UI envoie des commandes ici (PUSH/PULL)


# ---------------------------------------------------------------------------
# Labels human-friendly des types de trames
# Partagés entre le StatusBoard (ble_daemon.py) et l'UI RE (dashboard.py).
# ---------------------------------------------------------------------------

FRAME_LABELS: dict[int, str] = {
    77: "Frame 77  pH/Rdx/T",
    65: "Frame 65  Elec/Cyc",
    83: "Frame 83  cons.pH",
    69: "Frame 69  cons.Rdx",
}
