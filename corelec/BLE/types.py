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
    ph: Optional[float]
    redox: Optional[int]
    temp: Optional[float]
    sel: Optional[float]
    alarme: int
    warning: int
    alarm_rdx: int
    # byte 12 relay/pump active states
    pompe_plus_active: bool
    pompe_moins_active: bool
    pompe_chl_elx_active: bool   # relais chlore/électrolyseur (= PompeChlElxActive officiel)
    regulation_active: bool      # alias de pompe_chl_elx_active, gardé pour rétrocompat
    relais_fil_actif: bool
    # byte 13 presence/config flags
    pompe_plus_presence: bool
    pompe_moins_presence: bool
    capteur_temp: bool
    config_capteur_sel_actif: bool
    flow_switch_m: bool
    pompe_chlore: bool
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
    redox_consigne: Optional[int]
    pin_code_soft: int = 0  # PinCodeSoft (bytes 12-13, source officielle akeron.js)


@dataclass
class Decoded65(DecodedBase):
    boost_active: bool
    boost_remaining_min: int
    current_electrolyse_percent: int
    inversion_period_min: int
    shutter_mode_electrolyse_percent: int
    flow_switch: bool       # bit2 io_flags : pressostat physique fermé
    flow_alarm: bool        # bit6 io_flags : alarme défaut d'écoulement
    volet_actif: bool
    volet_force: bool
    polarity_phase_a: bool
    inversion_timer_min: int
    elx_fault_code: int = 0   # byte 12 nibble bas : 0=OK, 7=E.07 défaut flux, 3=transitoire
    salinite: int = 0        # bits 0+1 io_flags : 0=faible, 1=moyen, 2=élevé (source officielle)
    sleep: bool = False      # byte13 bit6 && bit5 (source officielle akeron.js)
    timer_actif: bool = False  # byte13 bit7 && bit5 (source officielle akeron.js)
    duree_st: int = 0        # byte13 &0x1F : durée restante sleep/timer en minutes


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
