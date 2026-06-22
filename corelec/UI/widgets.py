"""
widgets.py — Widgets réutilisables pour l'interface Corelec Monitor.

StatusBadge     Pastille colorée read-only pour états booléens.
PolarityWidget  Phase A/B + barre de progression du cycle d'inversion.
"""
from __future__ import annotations

from corelec.UI.qt_compat import (
    Qt, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)


class StatusBadge(QLabel):
    """Pastille pill-shaped colorée indiquant un état booléen (read-only).

    Usage ::
        badge = StatusBadge()
        badge.set_state(True,  label_on="Actif",  label_off="Inactif")
        badge.set_state(False, label_on="Présent", label_off="Absent", warn_when_off=True)
    """

    _STYLE_ON   = ("background:#27ae60; color:white; border-radius:10px; "
                   "padding:2px 14px; font-weight:600; font-size:13px;")
    _STYLE_OFF  = ("background:#444; color:#888; border-radius:10px; "
                   "padding:2px 14px; font-size:13px;")
    _STYLE_WARN = ("background:#e67e22; color:white; border-radius:10px; "
                   "padding:2px 14px; font-weight:600; font-size:13px;")
    _STYLE_ERR  = ("background:#e74c3c; color:white; border-radius:10px; "
                   "padding:2px 14px; font-weight:600; font-size:13px;")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(False)

    def set_state(
        self,
        active: bool,
        label_on:  str  = "OUI",
        label_off: str  = "NON",
        warn_when_off:  bool = False,
        error_when_on:  bool = False,
    ) -> None:
        self.setText(label_on if active else label_off)
        if active:
            self.setStyleSheet(self._STYLE_ERR if error_when_on else self._STYLE_ON)
        else:
            self.setStyleSheet(self._STYLE_WARN if warn_when_off else self._STYLE_OFF)


class PolarityWidget(QWidget):
    """Affiche la phase courante de polarité A/B + progression du timer d'inversion.

    Visual ::
        ┌────────────────────────────────────────────┐
        │  [A]  Phase A — 180 / 240 min (75%)        │
        │       ████████████████░░░░░░               │
        └────────────────────────────────────────────┘
    """

    _STYLE_A = (
        "background:#27ae60; color:white; border-radius:26px; "
        "font-size:26px; font-weight:bold; min-width:52px; min-height:52px; "
        "max-width:52px; max-height:52px;"
    )
    _STYLE_B = (
        "background:#2980b9; color:white; border-radius:26px; "
        "font-size:26px; font-weight:bold; min-width:52px; min-height:52px; "
        "max-width:52px; max-height:52px;"
    )
    _STYLE_UNKNOWN = (
        "background:#555; color:#999; border-radius:26px; "
        "font-size:26px; font-weight:bold; min-width:52px; min-height:52px; "
        "max-width:52px; max-height:52px;"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        self._badge = QLabel("—")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(self._STYLE_UNKNOWN)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)

        self._info_label = QLabel("Inversion de polarité")
        self._info_label.setStyleSheet("font-size:12px; color:#bbb;")

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(12)
        self._bar.setStyleSheet(
            "QProgressBar { border:1px solid #555; border-radius:5px; background:#2a2a2a; }"
            "QProgressBar::chunk { background:#27ae60; border-radius:4px; }"
        )

        right.addWidget(self._info_label)
        right.addWidget(self._bar)

        layout.addWidget(self._badge)
        layout.addLayout(right)

    def update_state(self, phase_a: bool, timer_min: int, period_min: int) -> None:
        self._badge.setText("A" if phase_a else "B")
        self._badge.setStyleSheet(self._STYLE_A if phase_a else self._STYLE_B)
        if period_min > 0:
            pct = min(100, int(timer_min * 100 / period_min))
            self._bar.setValue(pct)
            bar_style = self._bar.styleSheet()
            # Phase B → barre bleue
            color = "#27ae60" if phase_a else "#2980b9"
            self._bar.setStyleSheet(
                f"QProgressBar {{ border:1px solid #555; border-radius:5px; background:#2a2a2a; }}"
                f"QProgressBar::chunk {{ background:{color}; border-radius:4px; }}"
            )
            self._info_label.setText(
                f"Phase {'A' if phase_a else 'B'} — {timer_min} / {period_min} min ({pct} %)"
            )
        else:
            self._bar.setValue(0)
            self._info_label.setText("—")
