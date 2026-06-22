"""
Qt compatibility layer: PyQt5, PyQt6, PySide2, PySide6 – Python 3.9+.

pyqtgraph (already a dependency) handles backend detection.
This module re-exports the Qt classes used in the project and adds enum shims
so that the PyQt6-style nested enum syntax (Qt.CheckState.Checked, etc.)
works transparently even when PyQt5 (flat enums) is installed.

Priority order (set PYQTGRAPH_QT_LIB env var to force a specific binding):
  PyQt6 > PyQt5 > PySide6 > PySide2
"""
from __future__ import annotations

from pyqtgraph.Qt import QtCore, QtWidgets, QtGui

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
Qt = QtCore.Qt
QTimer = QtCore.QTimer
QObject = QtCore.QObject

# Signal: pyqtgraph normalises pyqtSignal / Signal across all backends
Signal = QtCore.Signal

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
QColor = QtGui.QColor
QBrush = QtGui.QBrush
QFontDatabase = QtGui.QFontDatabase

# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
QApplication = QtWidgets.QApplication
QCheckBox = QtWidgets.QCheckBox
QGridLayout = QtWidgets.QGridLayout
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QListWidget = QtWidgets.QListWidget
QMenu = QtWidgets.QMenu
QProgressBar = QtWidgets.QProgressBar
QPushButton = QtWidgets.QPushButton
QTabWidget = QtWidgets.QTabWidget
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QFrame = QtWidgets.QFrame
QSpinBox = QtWidgets.QSpinBox
QTextEdit = QtWidgets.QTextEdit
QLayout = QtWidgets.QLayout
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


def app_exec(app: QApplication) -> int:  # type: ignore[valid-type]
    """Cross-backend QApplication event-loop entry point.

    PyQt5 / PySide2 expose exec_(); PyQt6 / PySide6 expose exec().
    """
    fn = getattr(app, "exec", None) or getattr(app, "exec_")
    return fn()


# ---------------------------------------------------------------------------
# Enum shims
# ---------------------------------------------------------------------------
# PyQt5 / PySide2 use *flat* enums (Qt.Checked, Qt.DashLine, …).
# PyQt6 / PySide6 use *nested* enums (Qt.CheckState.Checked, …).
# When running under PyQt5/PySide2 the nested namespace is absent; we create
# lightweight proxy classes so that callers can always use the PyQt6 style.
# ---------------------------------------------------------------------------

def _patch_enums() -> None:  # noqa: C901
    # -- Qt.CheckState --
    if not hasattr(Qt, "CheckState"):
        class _CS:
            Checked = Qt.Checked    # type: ignore[attr-defined]
            Unchecked = Qt.Unchecked  # type: ignore[attr-defined]
        Qt.CheckState = _CS  # type: ignore[attr-defined]

    # -- Qt.ItemFlag --
    if not hasattr(Qt, "ItemFlag"):
        class _IF:
            ItemIsEditable = Qt.ItemIsEditable              # type: ignore[attr-defined]
            ItemIsEnabled = Qt.ItemIsEnabled                # type: ignore[attr-defined]
            ItemIsUserCheckable = Qt.ItemIsUserCheckable    # type: ignore[attr-defined]
        Qt.ItemFlag = _IF  # type: ignore[attr-defined]

    # -- Qt.ContextMenuPolicy --
    if not hasattr(Qt, "ContextMenuPolicy"):
        class _CMP:
            CustomContextMenu = Qt.CustomContextMenu  # type: ignore[attr-defined]
        Qt.ContextMenuPolicy = _CMP  # type: ignore[attr-defined]

    # -- Qt.PenStyle --
    if not hasattr(Qt, "PenStyle"):
        class _PS:
            DashLine = Qt.DashLine  # type: ignore[attr-defined]
        Qt.PenStyle = _PS  # type: ignore[attr-defined]

    # -- QTableWidget.SelectionBehavior --
    if not hasattr(QTableWidget, "SelectionBehavior"):
        class _SB:
            SelectRows = QTableWidget.SelectRows  # type: ignore[attr-defined]
        QTableWidget.SelectionBehavior = _SB  # type: ignore[attr-defined]

    # -- QTableWidget.SelectionMode --
    if not hasattr(QTableWidget, "SelectionMode"):
        class _SM:
            ExtendedSelection = QTableWidget.ExtendedSelection  # type: ignore[attr-defined]
        QTableWidget.SelectionMode = _SM  # type: ignore[attr-defined]

    # -- QTreeWidget.SelectionBehavior --
    if not hasattr(QTreeWidget, "SelectionBehavior"):
        class _SBT:
            SelectRows = QTreeWidget.SelectRows  # type: ignore[attr-defined]
        QTreeWidget.SelectionBehavior = _SBT  # type: ignore[attr-defined]

    # -- QTreeWidget.SelectionMode --
    if not hasattr(QTreeWidget, "SelectionMode"):
        class _SMT:
            ExtendedSelection = QTreeWidget.ExtendedSelection  # type: ignore[attr-defined]
        QTreeWidget.SelectionMode = _SMT  # type: ignore[attr-defined]

    # -- Qt.ItemDataRole --
    if not hasattr(Qt, "ItemDataRole"):
        class _IDR:
            UserRole = Qt.UserRole  # type: ignore[attr-defined]
        Qt.ItemDataRole = _IDR  # type: ignore[attr-defined]

    # -- QFontDatabase.SystemFont --
    if not hasattr(QFontDatabase, "SystemFont"):
        class _SF:
            FixedFont = QFontDatabase.FixedFont  # type: ignore[attr-defined]
        QFontDatabase.SystemFont = _SF  # type: ignore[attr-defined]


_patch_enums()
