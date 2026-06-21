# signals.py
from __future__ import annotations

from corelec.UI.qt_compat import QObject, Signal

from corelec.BLE.types import ConnectionInfo, DecodedBase


class Signals(QObject):

    connection = Signal(ConnectionInfo)
    log = Signal(str)
    state_updated = Signal()
    error = Signal(str)
    reverse = Signal(DecodedBase)
    retry_requested = Signal()
    cancel_requested = Signal()


signals = Signals()
