"""
types.py — Dataclasses de résultat BLE pour Corelec Monitor.

Hiérarchie :
    DecodedBase         Base commune : type + raw (17 octets)
    ├── Decoded77       pH, Redox, Temp, Sel, alarmes, pompes
    ├── Decoded83       Consigne pH, erreur max/min
    ├── Decoded65       Électrolyse, Boost, Cycles A/B, Volet
    └── Decoded69       Consigne Redox

ConnectionInfo      Statut BLE publié sur le bus interne / ZMQ
ConnectionMetrics   Compteurs de paquets / RSSI
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DecodedBase:
    type: int  # str
    raw: bytearray


@dataclass
class Decoded77(DecodedBase):
    # def __post_init__(self):
    #     self.type = 77
    # # type:int = 77
    ph: Optional[float]
    redox: Optional[int]
    temp: Optional[float]
    sel: Optional[float]
    alarme: int
    warning: int
    alarm_rdx: int
    pompe_moins_active: bool
    regulation_active: bool
    config_capteur_sel_actif: bool
    pompes_forcees: bool


@dataclass
class Decoded83(DecodedBase):
    # def __post_init__(self):
    #     self.type = 83
    # # type:int = 83
    ph_consigne: Optional[float]
    err_max: Optional[float]
    err_min: Optional[float]


@dataclass
class Decoded69(DecodedBase):
    # def __post_init__(self):
    #     self.type = 69
    # # type:int = 69
    redox_consigne: Optional[int]


@dataclass
class Decoded65(DecodedBase):
    boost_active: bool
    boost_remaining_min: int
    current_electrolyse_percent: int
    cycle_period_min: int
    shutter_mode_electrolyse_percent: int
    flow_switch: bool
    volet_actif: bool
    volet_force: bool
    cycle_a_min: int
    cycle_b_min: int
    elx_fault_code: int = 0   # byte 12 : 0=OK, 7=arrêt défaut flux, 3=transitoire


@dataclass
class ConnectionMetrics:
    """Tracks BLE connection statistics."""
    packets_sent: int = 0
    packets_received: int = 0
    frames_parsed: int = 0
    rssi: int = 0  # Signal strength in dBm
    mtu_size: int = 23  # Default BLE MTU
    connection_uptime_s: float = 0.0
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConnectionInfo:
    state: str
    message: str
    elapsed: int = 0
    remaining: int = 0
    timeout: int = 0
    retry_count: int = 0
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)


# class ReverseEngineeringData:
#     type: int
#     raw: list[bytes]
#     decoded: DecodedBase
