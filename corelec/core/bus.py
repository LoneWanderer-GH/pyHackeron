"""
corelec/core/bus.py — Bus d'événements applicatif.

Pur Python, sans dépendance Qt ni BLE.
Peut être utilisé en mode UI (via QtBridge dans UI/signals.py)
et en mode daemon headless (connexion directe de callbacks).

Directions :
    BLE/Acquisition → connection, state_updated, reverse, log, error
    UI / boutons    → retry_requested, cancel_requested
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List

logger = logging.getLogger(__name__)


class _Channel:
    """Canal d'événements synchrone — pub/sub pur Python."""

    __slots__ = ('_name', '_callbacks', '__weakref__')

    def __init__(self, name: str = '') -> None:
        self._name = name
        self._callbacks: List[Callable] = []

    def connect(self, cb: Callable) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def disconnect(self, cb: Callable) -> None:
        try:
            self._callbacks.remove(cb)
        except ValueError:
            pass

    def emit(self, *args: Any) -> None:
        for cb in list(self._callbacks):
            try:
                cb(*args)
            except Exception:
                logger.exception("bus[%s] callback error", self._name)


class AppBus:
    """Bus d'événements de l'application — instancié une seule fois (singleton `bus`)."""

    def __init__(self) -> None:
        # BLE → UI / daemon
        self.connection       = _Channel('connection')
        self.state_updated    = _Channel('state_updated')
        self.reverse          = _Channel('reverse')
        self.log              = _Channel('log')
        self.error            = _Channel('error')
        # UI / daemon → BLE
        self.retry_requested  = _Channel('retry_requested')
        self.cancel_requested = _Channel('cancel_requested')
        self.ble_command      = _Channel('ble_command')  # payload dict → Acquisition
        # daemon → UI : fin d'un sync DB
        self.db_sync_complete = _Channel('db_sync_complete')


# Singleton global — importé par tous les modules consommateurs
bus: AppBus = AppBus()
