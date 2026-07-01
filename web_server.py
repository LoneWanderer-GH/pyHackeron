"""
web_server.py — Serveur web Corelec Pool Monitor
=================================================
Pont ZMQ → HTTP + Server-Sent Events (SSE).

Usage:
    python web_server.py --daemon-host 192.168.0.16
    python web_server.py --daemon-host 192.168.0.16 --http-port 8080

Routes:
    GET  /              → dashboard HTML
    GET  /api/state     → snapshot JSON de l'état courant
    GET  /api/stream    → SSE (text/event-stream) — mises à jour live
    GET  /api/history/ph→ historique pH 48 h [{"ts": epoch, "ph": value}, ...]
    POST /api/cmd       → commande → daemon ZMQ  ({"type": "boost_start", "minutes": 120})
    POST /api/retry     → demande retry connexion BLE au daemon
    POST /api/compact_db→ nettoyage / compression de la base de données du daemon

Compatible Python 3.9+, sans Qt. Dépendances: flask, pyzmq.
Testé sur Synology DSM 7.x / Python 3.9 et Raspberry Pi 3.
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import zmq
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from corelec.net_protocol import (
    DEFAULT_CMD_PORT,
    DEFAULT_PUB_PORT,
    Topic,
    decode,
)
from corelec.BLE.frame import Frame
from corelec.BLE.types import Decoded65, Decoded69, Decoded77, Decoded83
from corelec.ReverseEngineering.decoder import Decoder

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Code PIN optionnel pour protéger les endpoints d'écriture.
# Configuré via --pin-code ou $CORELEC_PIN_CODE.
# Chaîne vide = pas de protection.
# ---------------------------------------------------------------------------
_pin_code: str = ""


def _check_pin(data: dict) -> bool:
    """Retourne True si le PIN est correct ou si aucun PIN n'est configuré."""
    if not _pin_code:
        return True
    return str(data.get("pin", "")) == _pin_code

# ---------------------------------------------------------------------------
# État partagé (mis à jour par le thread ZMQ, lu par Flask)
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()

# Historique pH en mémoire : 48 h, un point par trame (max ~5760 à 1 trame/30 s).
_PH_HISTORY_MAX_SEC = 48 * 3600
_ph_history: collections.deque = collections.deque()  # (epoch_float, ph_float)
_ph_history_lock = threading.Lock()


def _ph_history_push(ts_iso: str, ph: float) -> None:
    """Ajoute un point pH et élague les entrées plus anciennes que 48 h."""
    try:
        epoch = datetime.fromisoformat(ts_iso).timestamp()
    except Exception:
        epoch = time.time()
    cutoff = epoch - _PH_HISTORY_MAX_SEC
    with _ph_history_lock:
        _ph_history.append((epoch, ph))
        while _ph_history and _ph_history[0][0] < cutoff:
            _ph_history.popleft()


_state: Dict[str, Any] = {
    "connection": {
        "status": 0,
        "status_name": "disconnected",
        "message": "En attente de données…",
        "retry_count": 0,
        "metrics": {
            "rssi": 0,
            "packets_received": 0,
            "frames_parsed": 0,
            "uptime_s": 0.0,
        },
    },
    "pool": {
        "ph": None,
        "ph_consigne": None,
        "err_max": None,
        "err_min": None,
        "redox": None,
        "redox_consigne": None,
        "temp": None,
        "sel": None,
        "electrolyse_pct": 0,
        "boost_active": False,
        "boost_remaining_min": 0,
        # Frame77 byte12 relay states
        "pompe_plus_active": False,
        "pompe_moins_active": False,
        "pompe_chl_elx_active": False,
        "regulation_active": False,
        "relais_fil_actif": False,
        # Frame77 byte13 presence/config
        "pompe_plus_presence": False,
        "pompe_moins_presence": False,
        "capteur_temp": False,
        "config_capteur_sel_actif": False,
        "flow_switch_m": False,
        "pompe_chlore": False,
        "pompes_forcees": False,
        # Frame65
        "flow_switch": False,
        "flow_alarm": False,
        "salinite": 0,
        "sleep": False,
        "timer_actif": False,
        "duree_st": 0,
        "alarme": 0,
        "warning": 0,
        "alarm_rdx": 0,
        "elx_fault_code": 0,
    },
    # Capacités du régulateur détectées depuis les trames BLE.
    # have_data=False tant qu'aucune trame Frame77 n'a été reçue.
    # Les cartes/champs sont cachés dans l'UI tant que have_data=False.
    "capabilities": {
        "have_data": False,      # True dès la première trame Frame77
        "has_temp":  True,       # capteur température (byte13 bit2)
        "has_sel":   False,      # capteur sel/salinité (byte13 bit3)
        "has_redox": False,      # électrode Redox (déduit de redox_consigne != None)
        "has_pompe_plus":  False, # pompe pH+ (byte13 bit1)
        "has_pompe_moins": False, # pompe pH- (byte13 bit0)
        "has_pompe_chlore": False, # pompe chlore (byte13 bit5)
    },
    "ts": datetime.now().isoformat(),
    "web_server_uptime_s": 0,
}

_start_time = time.monotonic()
_decoder = Decoder()


def _update_state(section: str, updates: Dict[str, Any]) -> None:
    with _state_lock:
        _state[section].update(updates)
        _state["ts"] = datetime.now().isoformat()
        _state["web_server_uptime_s"] = round(time.monotonic() - _start_time)
    _broadcast_state()


def get_state_snapshot() -> Dict[str, Any]:
    with _state_lock:
        # Copie profonde simple (state contient seulement des types primitifs)
        return json.loads(json.dumps(_state))


# ---------------------------------------------------------------------------
# SSE — broadcast vers tous les clients connectés
# ---------------------------------------------------------------------------

_sse_clients: List[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast_state() -> None:
    snap = get_state_snapshot()
    msg = "event: state\ndata: " + json.dumps(snap) + "\n\n"
    with _sse_lock:
        dead: List[queue.Queue] = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                _sse_clients.remove(q)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Thread ZMQ SUB — écoute le daemon BLE
# ---------------------------------------------------------------------------

class ZmqListener(threading.Thread):
    """Thread unique qui s'abonne au daemon ZMQ PUB et met à jour l'état."""

    def __init__(self, host: str, pub_port: int) -> None:
        super().__init__(daemon=True, name="zmq-sub-web")
        self.host = host
        self.pub_port = pub_port
        self._running = False

    def run(self) -> None:
        self._running = True
        ctx = zmq.Context()
        sock = ctx.socket(zmq.SUB)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(f"tcp://{self.host}:{self.pub_port}")
        sock.setsockopt_string(zmq.SUBSCRIBE, "corelec/")
        sock.setsockopt(zmq.RCVTIMEO, 1000)
        logger.info("ZMQ SUB connecté → tcp://%s:%d", self.host, self.pub_port)

        while self._running:
            try:
                parts = sock.recv_multipart()
                if len(parts) >= 2:
                    topic, payload = decode(parts[0], parts[1])
                    self._dispatch(topic, payload)
            except zmq.Again:
                pass  # timeout 1 s — boucle normale
            except Exception as exc:
                logger.warning("ZMQ recv: %s", exc)

        sock.close()
        ctx.term()
        logger.info("ZmqListener arrêté.")

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------

    def _dispatch(self, topic: str, payload: Dict[str, Any]) -> None:
        try:
            if topic == Topic.CONNECTION:
                _update_state("connection", {
                    "status": payload.get("status", 0),
                    "status_name": payload.get("status_name", "disconnected"),
                    "message": payload.get("message", ""),
                    "retry_count": payload.get("retry_count", 0),
                    "metrics": payload.get("metrics", {}),
                })
            elif topic == Topic.FRAME_RAW:
                self._handle_frame(payload)
        except Exception as exc:
            logger.warning("Dispatch [%s]: %s", topic, exc)

    def _handle_frame(self, payload: Dict[str, Any]) -> None:
        hex_str = payload.get("hex", "")
        try:
            raw = bytearray.fromhex(hex_str)
        except ValueError:
            return

        frame = Frame.parse(raw)
        if frame is None:
            return

        decoded = _decoder.decode(frame)
        if decoded is None:
            return

        updates: Dict[str, Any] = {}

        if isinstance(decoded, Decoded77):
            if decoded.ph is not None:
                updates["ph"] = round(decoded.ph, 2)
                # Historique pH pour /api/history/ph
                _ph_history_push(_state["ts"], round(decoded.ph, 2))
            if decoded.redox is not None:
                updates["redox"] = decoded.redox
            if decoded.temp is not None:
                updates["temp"] = round(decoded.temp, 1)
            if decoded.sel is not None:
                updates["sel"] = round(decoded.sel, 1)
            updates.update({
                "alarme": decoded.alarme,
                "warning": decoded.warning,
                "alarm_rdx": decoded.alarm_rdx,
                "pompe_plus_active": decoded.pompe_plus_active,
                "pompe_moins_active": decoded.pompe_moins_active,
                "pompe_chl_elx_active": decoded.pompe_chl_elx_active,
                "regulation_active": decoded.regulation_active,
                "relais_fil_actif": decoded.relais_fil_actif,
                "pompe_plus_presence": decoded.pompe_plus_presence,
                "pompe_moins_presence": decoded.pompe_moins_presence,
                "capteur_temp": decoded.capteur_temp,
                "config_capteur_sel_actif": decoded.config_capteur_sel_actif,
                "flow_switch_m": decoded.flow_switch_m,
                "pompe_chlore": decoded.pompe_chlore,
                "pompes_forcees": decoded.pompes_forcees,
            })
            # Mise à jour des capacités détectées
            with _state_lock:
                caps = _state["capabilities"]
                caps["have_data"]       = True
                caps["has_temp"]        = decoded.capteur_temp
                caps["has_sel"]         = decoded.config_capteur_sel_actif
                caps["has_redox"]       = decoded.capteur_redox   # bit 6 byte13 : électrode Redox présente
                caps["has_pompe_plus"]  = decoded.pompe_plus_presence
                caps["has_pompe_moins"] = decoded.pompe_moins_presence
                caps["has_pompe_chlore"] = decoded.pompe_chlore

            if decoded.ph_consigne is not None:
                updates["ph_consigne"] = round(decoded.ph_consigne, 2)
            if decoded.err_max is not None:
                updates["err_max"] = round(decoded.err_max, 2)
            if decoded.err_min is not None:
                updates["err_min"] = round(decoded.err_min, 2)

        elif isinstance(decoded, Decoded69):
            if decoded.redox_consigne is not None:
                updates["redox_consigne"] = decoded.redox_consigne
                # has_redox est désormais piloté par decoded.capteur_redox (Frame77 byte13 bit6).
                # Le bloc Decoded69 ne touche plus aux capabilities.

        elif isinstance(decoded, Decoded65):
            updates.update({
                "electrolyse_pct": decoded.current_electrolyse_percent,
                "boost_active": decoded.boost_active,
                "boost_remaining_min": decoded.boost_remaining_min,
                "flow_switch": decoded.flow_switch,
                "flow_alarm": decoded.flow_alarm,
                "elx_fault_code": decoded.elx_fault_code,
                "salinite": decoded.salinite,
                "sleep": decoded.sleep,
                "timer_actif": decoded.timer_actif,
                "duree_st": decoded.duree_st,
            })

        if updates:
            _update_state("pool", updates)


# ---------------------------------------------------------------------------
# Émetteur de commandes ZMQ PUSH → daemon
# ---------------------------------------------------------------------------

_cmd_lock = threading.Lock()
_cmd_ctx: Optional[zmq.Context] = None
_cmd_sock: Optional[Any] = None  # zmq.SyncSocket n'est pas dispo sur Python 3.9 zmq
_cmd_host: str = "127.0.0.1"
_cmd_port: int = DEFAULT_CMD_PORT


def init_cmd(host: str, port: int) -> None:
    global _cmd_host, _cmd_port
    _cmd_host = host
    _cmd_port = port


def send_cmd(topic: str, payload: Optional[Dict[str, Any]] = None) -> None:
    global _cmd_ctx, _cmd_sock
    with _cmd_lock:
        if _cmd_ctx is None:
            _cmd_ctx = zmq.Context()
            _cmd_sock = _cmd_ctx.socket(zmq.PUSH)
            _cmd_sock.setsockopt(zmq.LINGER, 0)
            _cmd_sock.connect(f"tcp://{_cmd_host}:{_cmd_port}")
        parts = [topic.encode()]
        if payload:
            parts.append(json.dumps(payload).encode())
        _cmd_sock.send_multipart(parts)
    logger.info("CMD → daemon: %s %s", topic, payload)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(
    __name__,
    template_folder=str(_HERE / "corelec" / "web" / "templates"),
    static_folder=str(_HERE / "corelec" / "web" / "static"),
)


def _cors_headers(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/state")
def api_state() -> Response:
    resp = jsonify(get_state_snapshot())
    return _cors_headers(resp)


@app.route("/api/stream")
def api_stream() -> Response:
    """SSE : chaque client reçoit une queue dédiée. Keepalive toutes les 25 s."""
    client_q: queue.Queue = queue.Queue(maxsize=100)
    with _sse_lock:
        _sse_clients.append(client_q)

    # Snapshot initial immédiat
    snap = get_state_snapshot()
    initial = "event: state\ndata: " + json.dumps(snap) + "\n\n"

    def event_gen() -> Iterator[str]:
        try:
            yield initial
            while True:
                try:
                    msg = client_q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(client_q)
                except ValueError:
                    pass

    return Response(
        stream_with_context(event_gen()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: désactive le buffering SSE
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.route("/api/cmd", methods=["POST", "OPTIONS"])
def api_cmd() -> Response:
    if request.method == "OPTIONS":
        return _cors_headers(Response("", 204))
    data = request.get_json(silent=True) or {}
    if not _check_pin(data):
        return _cors_headers(jsonify({"error": "Code PIN incorrect"})), 403
    cmd_type = data.get("type")
    if not cmd_type:
        return _cors_headers(jsonify({"error": "champ 'type' manquant"})), 400
    try:
        send_cmd(Topic.CMD_BLE_COMMAND, data)
        return _cors_headers(jsonify({"ok": True}))
    except Exception as exc:
        logger.error("api_cmd: %s", exc)
        return _cors_headers(jsonify({"error": str(exc)})), 500


@app.route("/api/retry", methods=["POST", "OPTIONS"])
def api_retry() -> Response:
    if request.method == "OPTIONS":
        return _cors_headers(Response("", 204))
    data = request.get_json(silent=True) or {}
    if not _check_pin(data):
        return _cors_headers(jsonify({"error": "Code PIN incorrect"})), 403
    try:
        send_cmd(Topic.CMD_RETRY)
        return _cors_headers(jsonify({"ok": True}))
    except Exception as exc:
        return _cors_headers(jsonify({"error": str(exc)})), 500


@app.route("/api/history/ph")
def api_history_ph() -> Response:
    """Retourne l'historique pH des 48 derni\u00e8res heures.

    R\u00e9ponse : {"points": [[epoch_float, ph_float], ...]}
    """
    with _ph_history_lock:
        points = list(_ph_history)
    resp = jsonify({"points": points})
    return _cors_headers(resp)


@app.route("/api/compact_db", methods=["POST", "OPTIONS"])
def api_compact_db() -> Response:
    if request.method == "OPTIONS":
        return _cors_headers(Response("", 204))
    data = request.get_json(silent=True) or {}
    if not _check_pin(data):
        return _cors_headers(jsonify({"error": "Code PIN incorrect"})), 403
    max_age_days = int(data.get("max_age_days", 30))
    if not (1 <= max_age_days <= 3650):
        return _cors_headers(jsonify({"error": "max_age_days doit \u00eatre entre 1 et 3650"})), 400
    try:
        send_cmd(Topic.CMD_COMPACT_DB, {"max_age_days": max_age_days})
        return _cors_headers(jsonify({"ok": True, "max_age_days": max_age_days}))
    except Exception as exc:
        logger.error("api_compact_db: %s", exc)
        return _cors_headers(jsonify({"error": str(exc)})), 500


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Corelec Web Server")
    parser.add_argument(
        "--daemon-host", default=os.environ.get("CORELEC_HOST", "127.0.0.1"),
        help="IP du daemon BLE (défaut: 127.0.0.1 ou $CORELEC_HOST)",
    )
    parser.add_argument(
        "--daemon-pub-port", type=int,
        default=int(os.environ.get("CORELEC_PUB_PORT", DEFAULT_PUB_PORT)),
        help=f"Port ZMQ PUB du daemon (défaut: {DEFAULT_PUB_PORT})",
    )
    parser.add_argument(
        "--daemon-cmd-port", type=int,
        default=int(os.environ.get("CORELEC_CMD_PORT", DEFAULT_CMD_PORT)),
        help=f"Port ZMQ CMD du daemon (défaut: {DEFAULT_CMD_PORT})",
    )
    parser.add_argument(
        "--http-host", default="0.0.0.0",
        help="Interface d'écoute HTTP (défaut: 0.0.0.0)",
    )
    parser.add_argument(
        "--http-port", type=int,
        default=int(os.environ.get("CORELEC_WEB_PORT", 8080)),
        help="Port HTTP (défaut: 8080 ou $CORELEC_WEB_PORT)",
    )
    parser.add_argument(
        "--pin-code", default=os.environ.get("CORELEC_PIN_CODE", ""),
        help="Code PIN requis pour les commandes (écriture). Vide = sans protection.",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    global _pin_code
    _pin_code = args.pin_code.strip()

    env_level_name = os.environ.get("CORELEC_LOG_LEVEL", "INFO").upper()
    env_level = getattr(logging, env_level_name, logging.INFO)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else env_level,
        format="%(asctime)s %(name)-24s %(levelname)s %(message)s",
    )

    listener = ZmqListener(args.daemon_host, args.daemon_pub_port)
    listener.start()

    init_cmd(args.daemon_host, args.daemon_cmd_port)

    logger.info(
        "Web server → http://%s:%d | Daemon ZMQ PUB tcp://%s:%d CMD tcp://%s:%d",
        args.http_host, args.http_port,
        args.daemon_host, args.daemon_pub_port,
        args.daemon_host, args.daemon_cmd_port,
    )

    app.run(
        host=args.http_host,
        port=args.http_port,
        debug=args.debug,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
