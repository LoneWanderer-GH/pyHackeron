"""
widgets.py — Widgets réutilisables pour l'interface Corelec Monitor.

StatusBadge     Pastille colorée read-only pour états booléens.
PolarityWidget  Phase A/B + barre de progression du cycle d'inversion (texte intégré).
BoostWidget     Barre de progression du boost avec texte intégré.
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

    Le texte (phase, minuterie, pourcentage) est affiché directement sur la
    barre de progression — un seul widget au lieu de label + barre séparés.

    Visual ::
        [A]  Phase A — 180 / 240 min (75 %)
             ████████████████░░░░░░
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

    _BAR_BASE = (
        "QProgressBar {{ border:1px solid #555; border-radius:5px; background:#2a2a2a; "
        "color:{fg}; font-size:12px; }}"
        "QProgressBar::chunk {{ background:{chunk}; border-radius:4px; }}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        self._badge = QLabel("—")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(self._STYLE_UNKNOWN)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bar.setFormat("Inversion de polarité")
        self._bar.setFixedHeight(24)
        self._bar.setStyleSheet(self._BAR_BASE.format(fg="white", chunk="#555"))

        layout.addWidget(self._badge)
        layout.addWidget(self._bar)

    def update_state(self, phase_a: bool, timer_min: int, period_min: int) -> None:
        self._badge.setText("A" if phase_a else "B")
        self._badge.setStyleSheet(self._STYLE_A if phase_a else self._STYLE_B)
        if period_min > 0:
            pct = min(100, int(timer_min * 100 / period_min))
            self._bar.setValue(pct)
            chunk = "#27ae60" if phase_a else "#2980b9"
            self._bar.setStyleSheet(self._BAR_BASE.format(fg="white", chunk=chunk))
            self._bar.setFormat(
                f"Phase {'A' if phase_a else 'B'}"
                f" \u2014 {timer_min} / {period_min} min ({pct} %%)"
            )
        else:
            self._bar.setValue(0)
            self._bar.setStyleSheet(self._BAR_BASE.format(fg="#888", chunk="#555"))
            self._bar.setFormat("—")


class BoostWidget(QProgressBar):
    """Barre de progression du boost électrolyse avec texte intégré.

    Quand le boost est inactif la barre est vide et affiche « — ».
    Quand le boost est actif, la barre décroît depuis la durée initiale
    jusqu'à 0 et affiche « Boost actif — X min restantes ».
    """

    _BAR_ACTIVE = (
        "QProgressBar { border:1px solid #555; border-radius:5px; background:#2a2a2a; "
        "color:white; font-size:12px; }"
        "QProgressBar::chunk { background:#e67e22; border-radius:4px; }"
    )
    _BAR_INACTIVE = (
        "QProgressBar { border:1px solid #555; border-radius:5px; background:#2a2a2a; "
        "color:#888; font-size:12px; }"
        "QProgressBar::chunk { background:#444; border-radius:4px; }"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFormat("—")
        self.setFixedHeight(22)
        self.setStyleSheet(self._BAR_INACTIVE)

    def update_boost(self, active: bool, remaining_min: int, total_min: int = 0) -> None:
        """Met à jour la barre de boost.

        Args:
            active:        True si le boost est en cours.
            remaining_min: minutes restantes.
            total_min:     durée initiale (0 = inconnue → barre pleine).
        """
        if not active or remaining_min <= 0:
            self.setValue(0)
            self.setFormat("—")
            self.setStyleSheet(self._BAR_INACTIVE)
        else:
            if total_min > 0:
                pct = max(1, min(100, int(remaining_min * 100 / total_min)))
            else:
                pct = 100
            self.setValue(pct)
            self.setFormat(f"Boost actif \u2014 {remaining_min} min restantes")
            self.setStyleSheet(self._BAR_ACTIVE)
