# signals.py — Qt bridge pour corelec.core.bus
"""
Relaie les événements du AppBus (pur Python) vers des Qt signals thread-safe.

Dans le mode UI, l'acquisition BLE tourne dans un thread asyncio séparé.
Les Qt signals garantissent le marshalling automatique vers le thread Qt
(QueuedConnection implicite pour les connexions cross-thread).

Usage :
    from corelec.UI.signals import signals
    signals.connection.connect(my_slot)   # ← Qt signal, thread-safe
    signals.retry_requested.emit()         # ← _Channel Python → Acquisition
"""
from __future__ import annotations

from corelec.core.bus import bus, _Channel, AppBus
from corelec.UI.qt_compat import QObject, Signal


class QtBridge(QObject):
    """Passerelle thread-safe entre AppBus et l'UI Qt.

    Sens BLE → UI : bus._Channel → Qt signal (thread-safe cross-thread).
    Sens UI → BLE : proxy direct vers bus._Channel (même thread).
    """

    # Signaux Qt reçus par l'UI (thread-safe)
    connection    = Signal(object)   # ConnectionInfo
    state_updated = Signal()
    reverse       = Signal(object)   # DecodedBase
    log           = Signal(str)
    error         = Signal(str)
    db_sync_complete = Signal(str)   # table synchronisée
    # UI → BLE : commande d'écriture GATT
    # Émis par les panneaux de commande ; relayé vers bus.ble_command
    ble_command   = Signal(dict)

    def __init__(self, app_bus: AppBus = bus, parent:QObject|None=None) -> None:
        super().__init__(parent)
        self._bus = app_bus
        # bus pur-Python → Qt signal
        app_bus.connection.connect(self.connection.emit)
        app_bus.state_updated.connect(self.state_updated.emit)
        app_bus.reverse.connect(self.reverse.emit)
        app_bus.log.connect(self.log.emit)
        app_bus.error.connect(self.error.emit)
        app_bus.db_sync_complete.connect(self.db_sync_complete.emit)
        # Qt signal → bus Python : widgets UI → Acquisition (local) ou ZMQ (réseau)
        self.ble_command.connect(self._bus.ble_command.emit)

    # Sens UI → BLE : proxy transparent vers les canaux du bus
    @property
    def retry_requested(self) -> _Channel:
        return self._bus.retry_requested

    @property
    def cancel_requested(self) -> _Channel:
        return self._bus.cancel_requested


# Singleton global — créé à l'import de ce module (mode UI uniquement).
# Le daemon n'importe jamais ce module (Acquisition dépend de core.bus).
signals: QtBridge = QtBridge()

