#!/usr/bin/env python3
"""
monitor.py — Interface graphique Corelec Monitor
=================================================
Peut fonctionner en deux modes :

Mode BLE direct (défaut, connexion locale) :
    python monitor.py --address B4:E3:F9:5A:0A:13

Mode réseau (connecté à un ble_daemon distant, ex : Raspberry Pi) :
    python monitor.py --network 192.168.1.10

    Options optionnelles :
        --pub-port   port ZMQ PUB du daemon (défaut 5555)
        --cmd-port   port ZMQ CMD du daemon (défaut 5556)
        --sync-db    télécharger la DB distante au démarrage

Variables d'environnement :
    CORELEC_ADDRESS     Adresse BLE (mode direct)
    CORELEC_NETWORK     IP / hostname du daemon (mode réseau)
    CORELEC_PUB_PORT    (défaut 5555)
    CORELEC_CMD_PORT    (défaut 5556)
    CORELEC_DB_PATH     Chemin DB locale (défaut ./pool.db)
    CORELEC_LOG_LEVEL   DEBUG / INFO / WARNING / ERROR
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Chemin racine
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from corelec.UI.qt_compat import QApplication, app_exec
from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.Acquisition import Acquisition
from corelec.UI.dashboard import Dashboard
from corelec.UI.signals import signals
from corelec.core_logging import setup_logging
from corelec.net_protocol import DEFAULT_PUB_PORT, DEFAULT_CMD_PORT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mode BLE direct — boucle de reconnexion dans un thread
# ---------------------------------------------------------------------------

def _run_ble(stop_event: threading.Event, address: str,
             state: RegulatorState, db: Database,
             initial_retry: int = 0) -> None:
    retry_count = initial_retry
    while not stop_event.is_set():
        acq = Acquisition(address=address, state=state, database=db,
                          retry_count=retry_count)
        try:
            asyncio.run(acq.run())
        except Exception as e:
            logger.exception("BLE loop error: %s", e)
        retry_count += 1
        if not stop_event.is_set():
            import time; time.sleep(1)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Corelec Monitor — UI graphique (BLE direct ou réseau)"
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--address",
        default=os.environ.get("CORELEC_ADDRESS", ""),
        help="Mode BLE direct : adresse BLE du régulateur (ex: B4:E3:F9:5A:0A:13)",
    )
    mode.add_argument(
        "--network",
        default=os.environ.get("CORELEC_NETWORK", ""),
        metavar="HOST",
        help="Mode réseau : IP / hostname du ble_daemon",
    )
    p.add_argument("--pub-port", type=int,
                   default=int(os.environ.get("CORELEC_PUB_PORT", DEFAULT_PUB_PORT)))
    p.add_argument("--cmd-port", type=int,
                   default=int(os.environ.get("CORELEC_CMD_PORT", DEFAULT_CMD_PORT)))
    p.add_argument("--db-path",
                   default=os.environ.get("CORELEC_DB_PATH", "pool.db"))
    p.add_argument("--sync-db", action="store_true",
                   help="Mode réseau : demander un dump de la DB distante au démarrage")
    p.add_argument("--redecode", action="store_true",
                   help="Re-décode tous les raw_frames dans decoded_frames au démarrage (utile après mise à jour du décodeur)")
    p.add_argument("--log-level",
                   default=os.environ.get("CORELEC_LOG_LEVEL", "INFO"),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging(args.log_level)

    if not args.address and not args.network:
        logger.error(
            "Spécifier --address (mode BLE direct) ou --network (mode réseau daemon)."
        )
        sys.exit(1)

    app = QApplication(sys.argv)

    state = RegulatorState()
    db = Database(args.db_path)

    if args.redecode:
        logger.info("--redecode : re-décodage de decoded_frames en cours…")
        n = db.force_redecode()
        logger.info("--redecode terminé : %d trames décodées", n)

    # Titre différent selon le mode
    if args.network:
        title = f"Corelec Monitor — réseau {args.network}"
    else:
        title = f"Corelec Monitor — BLE {args.address}"

    dashboard = Dashboard(state, db)
    dashboard.resize(1200, 900)
    dashboard.setWindowTitle(title)
    dashboard.show()

    # ------------------------------------------------------------------
    # Mode réseau
    # ------------------------------------------------------------------
    if args.network:
        from corelec.net_client import NetworkClient

        client = NetworkClient(
            host=args.network,
            state=state,
            database=db,
            pub_port=args.pub_port,
            cmd_port=args.cmd_port,
        )
        client.start()
        dashboard.set_network_client(client)
        app.aboutToQuit.connect(client.stop)  # fermeture propre des sockets ZMQ

        # Relier les boutons Retry / Cancel du dashboard aux commandes réseau
        signals.retry_requested.connect(client.reconnect)
        signals.cancel_requested.connect(client.request_cancel)
        # Commandes GATT : le signal Qt ble_command est relayé vers le dæmon via ZMQ
        signals.ble_command.connect(client.send_ble_command)

        if args.sync_db:
            logger.info("Demande de sync DB distante…")
            client.request_db_sync("decoded_values")

    # ------------------------------------------------------------------
    # Mode BLE direct
    # ------------------------------------------------------------------
    else:
        stop_event = threading.Event()

        def _cancel() -> None:
            stop_event.set()

        def _restart() -> None:
            stop_event.set()
            new_stop = threading.Event()
            threading.Thread(
                target=_run_ble,
                args=(new_stop, args.address, state, db),
                daemon=True,
            ).start()

        signals.cancel_requested.connect(_cancel)
        signals.retry_requested.connect(_restart)

        threading.Thread(
            target=_run_ble,
            args=(stop_event, args.address, state, db),
            daemon=True,
        ).start()

    sys.exit(app_exec(app))


if __name__ == "__main__":
    main()
