import logging
from html import escape
from typing import Callable

import coloredlogs


_LOGGING_CONFIGURED = False
_QT_HANDLER: logging.Handler | None = None


class QtHtmlLogHandler(logging.Handler):
    def __init__(self, emitter: Callable[[str], None]):
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            color_map = {
                logging.DEBUG: "#8a8f98",
                logging.INFO: "#d7e3f4",
                logging.WARNING: "#f2c97d",
                logging.ERROR: "#ff8f8f",
                logging.CRITICAL: "#ff4d4d",
            }
            color = color_map.get(record.levelno, "#d7e3f4")
            html = (
                f"<span style='font-family:Consolas,\"Courier New\",monospace;"
                f"color:{color};white-space:pre;'>{escape(msg)}</span>"
            )
            self._emitter(html)
        except Exception:
            self.handleError(record)


def setup_logging(level: str = "INFO") -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    coloredlogs.install(
        level=level,
        logger=logging.getLogger(),
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    _LOGGING_CONFIGURED = True


def attach_qt_log_emitter(emitter: Callable[[str], None], level: str = "DEBUG") -> None:
    global _QT_HANDLER
    root = logging.getLogger()

    if _QT_HANDLER is not None:
        root.removeHandler(_QT_HANDLER)

    handler = QtHtmlLogHandler(emitter)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(handler)
    _QT_HANDLER = handler
