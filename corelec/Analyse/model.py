from __future__ import annotations
# model.py
"""
model.py — État courant du régulateur Corelec.

RegulatorState est mis à jour en temps réel par Acquisition (mode BLE direct)
ou par NetworkClient._handle_state (mode réseau via le topic corelec/state).
Il est lu par le Dashboard pour afficher les valeurs instantanées.
L’historique des graphiques est dérivé de raw_frames et non de cet objet.
"""
from dataclasses import dataclass, asdict
from datetime import datetime

from corelec.ReverseEngineering.decoder import Decoded65, Decoded69, Decoded77, Decoded83, DecodedBase


@dataclass
class RegulatorState:
    """Snapshot complet de l’état du régulateur, mis à jour à chaque trame reçue."""
    timestamp : str = datetime.now().isoformat()
    ph: float | None = None
    redox: float | None = None
    temp: float | None = None
    sel: float | None = None

    ph_consigne: float | None = None
    redox_consigne: int | None = None

    alarme: int = 0
    warning: int = 0

    pompe_moins_active: bool = False
    pompe_chl_elx: bool = False
    pompes_forcees: bool = False

    boost_remaining_time_min: int = 0
    boost_active: bool = False
    
    configured_cycle_period_min : int = 0
    # chlorinator_power_percent : float = 0
    current_electrolyse_percent: float = 0
    shutter_mode_electrolyse_percent: float = 0
    
    cycle_a_min : int = 0
    cycle_b_min : int = 0

    volet_actif: bool = False
    volet_force: bool = False
    
    flow_switch : bool = False
    # elx_fault_code : code d’arrêt de l’électrolyseur (trame 65 byte 12)
    # 0=normal, 7=arrêt défaut flux, 3=transitoire
    elx_fault_code: int = 0

    # raw_a10: int = 0

    def update(self, decoded: DecodedBase):
        self.timestamp = datetime.now().isoformat()
        t = decoded.type

        if t == 77 and isinstance(decoded, Decoded77):
            self.ph = decoded.ph if decoded.ph is not None else self.ph
            self.redox = decoded.redox if decoded.redox is not None else self.redox
            self.temp = decoded.temp if decoded.temp is not None else self.temp
            self.sel = decoded.sel if decoded.sel is not None else self.sel

            self.alarme = decoded.alarme
            self.warning = decoded.warning
            self.pompe_moins_active = decoded.pompe_moins_active
            self.pompe_chl_elx = decoded.regulation_active
            self.pompes_forcees = decoded.pompes_forcees

        elif t == 83 and isinstance(decoded, Decoded83):
            self.ph_consigne = decoded.ph_consigne

        elif t == 69 and isinstance(decoded, Decoded69):
            self.redox_consigne = decoded.redox_consigne

        elif t == 65 and isinstance(decoded, Decoded65):
            self.boost_remaining_time_min = decoded.boost_remaining_min
            self.boost_active = decoded.boost_active
            self.configured_cycle_period_min = decoded.cycle_period_min
            self.current_electrolyse_percent = decoded.current_electrolyse_percent
            self.shutter_mode_electrolyse_percent = decoded.shutter_mode_electrolyse_percent
            self.flow_switch = decoded.flow_switch
            self.volet_actif = decoded.volet_actif
            self.volet_force = decoded.volet_force
            self.cycle_a_min = decoded.cycle_a_min
            self.cycle_b_min = decoded.cycle_b_min
            self.elx_fault_code = decoded.elx_fault_code
            # self.raw_a10 = decoded.raw_field_a10

    def json(self):
        return asdict(self)