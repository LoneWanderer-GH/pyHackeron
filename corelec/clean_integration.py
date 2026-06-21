import asyncio
import sys
import threading
import logging

from corelec.UI.qt_compat import QApplication

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.Acquisition import Acquisition
from corelec.UI.dashboard import Dashboard
from corelec.UI.signals import signals
from corelec.core_logging import setup_logging

ADDRESS = "B4:E3:F9:5A:0A:13"

logger = logging.getLogger(__name__)


# -----------------------------
# boucle BLE (auto restart)
# -----------------------------
def run_ble(stop_event: threading.Event, state: RegulatorState, db: Database, initial_retry: int = 0):
    
    retry_count = initial_retry
    
    while not stop_event.is_set():
        
        acq = Acquisition(
                ADDRESS,
                state,
                db,
                retry_count=retry_count
        )
        
        try:
            asyncio.run(acq.run())
        except Exception as e:
            logger.exception("BLE loop error: %s", e)
        
        retry_count += 1
        
        # petit délai pour éviter spam reconnect
        if not stop_event.is_set():
            asyncio.run(asyncio.sleep(1))


# -----------------------------
# main UI
# -----------------------------
def main():
    setup_logging("INFO")
    
    app = QApplication(sys.argv)
    
    state = RegulatorState()
    db = Database()
    
    dashboard = Dashboard(state, db)
    dashboard.resize(1200, 900)
    dashboard.setWindowTitle(f"Corelec Monitor - {ADDRESS}")
    dashboard.show()
    
    stop_event = threading.Event()
    
    # -----------------------------
    # callbacks UI
    # -----------------------------
    def cancel():
        stop_event.set()
    
    def restart():
        # Stop the current BLE loop and start a fresh one.
        stop_event.set()
        
        new_stop = threading.Event()
        
        t = threading.Thread(
                target=run_ble,
                args=(new_stop, state, db),
                daemon=True
        )
        t.start()
    
    signals.cancel_requested.connect(cancel)
    signals.retry_requested.connect(restart)
    
    # -----------------------------
    # start initial BLE
    # -----------------------------
    t = threading.Thread(
            target=run_ble,
            args=(stop_event, state, db),
            daemon=True
    )
    t.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
