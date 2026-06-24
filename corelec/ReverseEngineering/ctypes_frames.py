from __future__ import annotations

import ctypes
import re
from ctypes import BigEndianStructure, Structure, c_uint8, c_uint16
from typing import Any, ByteString, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Layout utility — single source of truth for _known_offsets and _offset_names
# ---------------------------------------------------------------------------

_UNKNOWN_FIELD = re.compile(r'^b\d+$')
_layout_cache: Dict[type, Tuple[Dict[int, str], List[int]]] = {}


def _be_layout(be_cls: type) -> Tuple[Dict[int, str], List[int]]:
    """Introspect a BigEndianStructure subclass and return:
      - offset_names : {byte_offset: display_label}
      - known_offsets: sorted list of offsets whose field name is not 'bN'
    Result is cached per class.
    """
    assert(be_cls is not None and issubclass(be_cls, BigEndianStructure))
    if be_cls in _layout_cache:
        return _layout_cache[be_cls]

    offset_names: Dict[int, str] = {}
    known_offsets: List[int] = []
    pos = 0
    for entry in be_cls._fields_:
        name, ctype = entry[0], entry[1]
        size = ctypes.sizeof(ctype)
        is_known = not _UNKNOWN_FIELD.match(name)
        for i in range(size):
            off = pos + i
            if size == 1:
                label = name
            elif i == 0:
                label = f"{name}[hi]"
            elif i == size - 1:
                label = f"{name}[lo]"
            else:
                label = f"{name}[{i}]"
            offset_names[off] = label
            if is_known:
                known_offsets.append(off)
        pos += size

    result = (offset_names, sorted(known_offsets))
    _layout_cache[be_cls] = result
    return result



# ---------------------------------------------------------------------------
# Base frame — 17 bytes, provides raw byte access + as_dict skeleton
# ---------------------------------------------------------------------------

class FrameBase(Structure):
    _fields_ = [(f'b{i}', c_uint8) for i in range(17)]

    # Default _BE: only structural bytes known (sync/typ/crc/end)
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync', c_uint8), ('typ',  c_uint8),
            ('b2',  c_uint8),  ('b3',   c_uint8), ('b4',  c_uint8),
            ('b5',  c_uint8),  ('b6',   c_uint8), ('b7',  c_uint8),
            ('b8',  c_uint8),  ('b9',   c_uint8), ('b10', c_uint8),
            ('b11', c_uint8),  ('b12',  c_uint8), ('b13', c_uint8),
            ('b14', c_uint8),
            ('crc', c_uint8),  ('end',  c_uint8),
        ]

    @classmethod
    def from_bytes(cls, raw: ByteString) -> FrameBase:
        """Build from raw bytes using from_buffer_copy (zero-copy mapping)."""
        data = bytes(raw)
        if len(data) < 17:
            data = data + bytes(17 - len(data))
        return cls.from_buffer_copy(data[:17])

    def raw_list(self) -> List[int]:
        return [getattr(self, f'b{i}') for i in range(17)]

    def raw_bytes(self) -> bytes:
        return bytes(self.raw_list())

    def as_dict(self) -> Dict[str, Any]:
        """Base dict: raw_bN bytes + _known_offsets + _offset_names from _BE layout."""
        raw = self.raw_bytes()
        d: Dict[str, Any] = {f'raw_b{i}': raw[i] for i in range(17)}
        offset_names, known_offsets = _be_layout(type(self)._BE)
        d['_known_offsets'] = known_offsets
        d['_offset_names']  = offset_names
        return d


# ---------------------------------------------------------------------------
# Frame 77 — pH, Redox, Temp, Sel, Alarmes, Pompes
# ---------------------------------------------------------------------------

class Frame77(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync',      c_uint8),
            ('typ',       c_uint8),
            ('ph',        c_uint16),       # bytes 2-3  (÷100)
            ('redox',     c_uint16),       # bytes 4-5
            ('temp',      c_uint16),       # bytes 6-7  (÷10)
            ('sel',       c_uint16),       # bytes 8-9  (÷10)
            ('alarme',     c_uint8),  # byte 10 : code E affiché sur le contrôleur (ex. alarme=12 → « E12 »)
            ('warning',    c_uint8),  # byte 11  alarm_rdx[7:4] | warning[3:0]
            # byte 12  pump_flags :
            #   bits 0+1 (0x03) : toujours à 1 dans les données observées (usage inconnu)
            #   bit 5   (0x20)  : regulation_active — passe à 0 dans deux cas :
            #                       1) simultanément avec flow_switch (trame 65) quand l'arrivée d'eau
            #                          est coupée (électrolyseur arrêté / régulation inhibée)
            #                       2) quand pompes_forcees=True (mode forcé manuel, byte13 bit7)
            #                     Représente l'autorisation générale de régulation (pH + électrolyse)
            #   bit 6   (0x40)  : pompe_moins_active — pompe pH- en cours en mode AUTO uniquement ;
            #                     = 0 lorsque pompes_forcees=True (mode forcé bypass la régulation auto)
            ('pump_flags',    c_uint8),  # byte 12
            # byte 12 pump_flags (source officielle akeron.js + RE) :
            #   bit 7 (0x80) : pompe_plus_active      — relais pompe pH+ en cours
            #   bit 6 (0x40) : pompe_moins_active     — relais pompe pH- en cours (mode AUTO)
            #   bit 5 (0x20) : pompe_chl_elx_active   — relais chlore/électrolyseur actif
            #                  Alias local : regulation_active (sémantique identique)
            #                  = 0 si flux coupé ou si pompes_forcees=True
            #   bit 4 (0x10) : relais_fil_actif        — relais fil (câble) actif
            #   bits 0+1     : toujours 1 dans nos données (usage inconnu)
            # byte 13  sensor_config_flags (source officielle akeron.js) :
            #   bit 0 (0x01) : pompe_moins_presence   — pompe pH- configurée/présente
            #   bit 1 (0x02) : pompe_plus_presence    — pompe pH+ configurée/présente
            #   bit 2 (0x04) : capteur_temp           — capteur température présent
            #   bit 3 (0x08) : capteur_sel            — capteur SEL présent/actif
            #                  (observé : 0x19→0x11 à la désactivation)
            #   bit 4 (0x10) : flow_switch_m          — pressostat (|= avec Frame65 bit2)
            #   bit 5 (0x20) : pompe_chlore           — pompe chlore présente
            #   bit 7 (0x80) : pompes_forcees — CONFIRMÉ : 17→145 lors du forçage manuel
            ('sensor_config_flags', c_uint8),  # byte 13
            # byte 14 : constante fixe par type de trame (jamais un CRC)
            #   vérifié sur 5000 trames : Frame77=0x82 toujours
            #   Probablement un identifiant de sous-type ou version de protocole.
            ('frame_const',  c_uint8),  # byte 14  constante=0x82 pour Frame 77
            ('crc',       c_uint8),        # byte 15
            ('end',       c_uint8),        # byte 16
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        be = self._BE.from_buffer_copy(self.raw_bytes())
        ph   = be.ph   / 100.0
        temp = be.temp / 10.0
        sel  = be.sel  / 10.0
        d.update({
            'type':               77,
            'ph':                 ph   if 3.5 <= ph   <= 9.5  else None,
            'redox':              be.redox if 350 <= be.redox <= 1000 else None,
            'temp':               temp if 0   <= temp <= 50   else None,
            'sel':                sel  if 0   <= sel  <= 10   else None,
            'alarme':             be.alarme,
            'warning':            be.warning & 0x0F,
            'alarm_rdx':          be.warning >> 4,
            'pompe_plus_active':  bool(be.pump_flags & (1 << 7)),
            'pompe_moins_active': bool(be.pump_flags & (1 << 6)),
            # pompe_chl_elx_active = relais chlore/électrolyseur (officiel: PompeChlElxActive)
            # Alias sémantique local conservé pour rétrocompatibilité : regulation_active
            'pompe_chl_elx_active': bool(be.pump_flags & (1 << 5)),
            'regulation_active':    bool(be.pump_flags & (1 << 5)),  # alias
            'relais_fil_actif':     bool(be.pump_flags & (1 << 4)),
            'pompe_moins_presence': bool(be.sensor_config_flags & (1 << 0)),
            'pompe_plus_presence':  bool(be.sensor_config_flags & (1 << 1)),
            'capteur_temp':         bool(be.sensor_config_flags & (1 << 2)),
            'config_capteur_sel_actif': bool(be.sensor_config_flags & (1 << 3)),
            'flow_switch_m':        bool(be.sensor_config_flags & (1 << 4)),
            'pompe_chlore':         bool(be.sensor_config_flags & (1 << 5)),
            'pompes_forcees':       bool(be.sensor_config_flags & (1 << 7)),
            # Noms des bits connus pour l'UI Reverse Engineering
            '_bit_names': {
                12: {  # pump_flags
                    0: 'const_1_b0',
                    1: 'const_1_b1',
                    4: 'relais_fil_actif',
                    5: 'pompe_chl_elx_active',
                    6: 'pompe_moins_active',
                    7: 'pompe_plus_active',
                },
                13: {  # sensor_config_flags
                    0: 'pompe_moins_presence',
                    1: 'pompe_plus_presence',
                    2: 'capteur_temp',
                    3: 'capteur_sel',
                    4: 'flow_switch_m',
                    5: 'pompe_chlore',
                    7: 'pompes_forcees',
                },
            },
        })
        return d


# ---------------------------------------------------------------------------
# Frame 83 — Consigne pH, err_max, err_min
# ---------------------------------------------------------------------------

class Frame83(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync',       c_uint8),
            ('typ',        c_uint8),
            ('ph_consigne', c_uint16),  # bytes 2-3  (÷100)
            ('b4',  c_uint8), ('b5', c_uint8), ('b6', c_uint8),
            ('b7',  c_uint8), ('b8', c_uint8), ('b9', c_uint8),
            ('err_max',    c_uint16),   # bytes 10-11 (÷100)
            ('err_min',    c_uint16),   # bytes 12-13 (÷100)
            # byte 14 : constante fixe par type de trame
            #   vérifié sur 5000 trames : Frame83=0x03 toujours
            ('frame_const', c_uint8),   # byte 14  constante=0x03 pour Frame 83
            ('crc', c_uint8),           # byte 15
            ('end', c_uint8),           # byte 16
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        be = self._BE.from_buffer_copy(self.raw_bytes())
        d.update({
            'type':        83,
            'ph_consigne': be.ph_consigne / 100.0,
            'err_max':     be.err_max     / 100.0,
            'err_min':     be.err_min     / 100.0,
        })
        return d


# ---------------------------------------------------------------------------
# Frame 69 — Consigne Redox
# ---------------------------------------------------------------------------

class Frame69(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync',           c_uint8),
            ('typ',            c_uint8),
            ('redox_consigne', c_uint16),  # bytes 2-3
            ('b4',  c_uint8), ('b5',  c_uint8), ('b6',  c_uint8), ('b7',  c_uint8),
            ('b8',  c_uint8), ('b9',  c_uint8), ('b10', c_uint8), ('b11', c_uint8),
            # bytes 12-13 : PinCodeSoft (source officielle akeron.js)
            ('pin_code_soft', c_uint16),  # bytes 12-13
            # byte 14 : constante fixe par type de trame
            #   vérifié sur 5000 trames : Frame69=0x61 toujours
            ('frame_const', c_uint8),  # byte 14  constante=0x61 pour Frame 69
            ('crc', c_uint8),   # byte 15
            ('end', c_uint8),   # byte 16
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        be = self._BE.from_buffer_copy(self.raw_bytes())
        d.update({
            'type':           69,
            'redox_consigne': be.redox_consigne,
            'pin_code_soft':  be.pin_code_soft,
        })
        return d


# ---------------------------------------------------------------------------
# Frame 65 — Électrolyse, Boost, Cycles, Volet, Flow switch
# ---------------------------------------------------------------------------

class Frame65(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync',         c_uint8),
            ('typ',          c_uint8),
            ('electrolyse',  c_uint8),   # byte 2   current_electrolyse_percent
            ('boost_remain', c_uint16),  # bytes 3-4 boost_remaining_min (uint16 BE)
            #                           # CONFIRMÉ : boost 6h = 360 min = 0x0168
            #                           #   → byte 3 = 0x01, byte 4 = 0x68 (104)
            ('inversion_period', c_uint16),  # bytes 5-6 inversion_period_min (uint16 BE)
            #                               # Période config. d'inversion de polarité de l'électrolyseur
            #                               # (défaut observé : 240 min = 4h ; jusqu'à 24h = 1440 min)
            ('inversion_timer',  c_uint16),  # bytes 7-8 inversion_timer_min (uint16 BE)
            #                               # Compteur écoulé du cycle d'inversion courant (en minutes)
            ('shutter_mode', c_uint8),   # byte 9   shutter_mode_electrolyse_percent
            # byte 10  bitfield io_flags :
            #   bit 2 (0x04)    : flow_switch — état physique du pressostat d'eau.
            #                     1 = pressostat fermé (eau en circulation). Toujours 1
            #                     dans nos données observées (l'installation est normalement en eau).
            #                     Confirmé par RE externe (guix77/esphome-akeron-salt-duo).
            #   bit 3 (0x08)    : volet_force (non vérifié)
            #   bit 4 (0x10)    : volet_actif (non vérifié)
            #   bit 5 (0x20)    : indicateur de phase de polarité A.
            #                     1 = phase A (io_flags typique = 0x24),
            #                     0 = phase B après remise à 0 du compteur (io_flags = 0x04).
            #   bit 6 (0x40)    : flow_alarm — alarme défaut d'écoulement.
            #                     Bit distinct du pressostat physique (bit2) :
            #                     le pressostat peut rester fermé (bit2=1) pendant que l'alarme
            #                     est levée (bit6=1) → io_flags=0x64.
            #   Hypothèse initiale « bits 0+1 = polarité » INFIRMÉE :
            #   toutes les trames observées (n>31 000) ont bits 0+1 = 0.
            #   La valeur 0x23 mentionnée dans les notes antérieures était une lecture erronée de 0x24.
            ('io_flags',     c_uint8),   # byte 10
            ('b11',          c_uint8),   # byte 11 unknown
            # byte 12 : code d’arrêt de l’électrolyseur lié au défaut de flux
            #   0 = normal, 7 = arrêt défaut flux, 3 = transitoire (rétablissement)
            ('elx_fault_code', c_uint8), # byte 12
            # byte 13 (source officielle akeron.js) :
            #   bit 5 (0x20) : actif si Sleep OU Timer est en cours
            #   bit 6 (0x40) : combiné avec bit5 → Sleep mode
            #   bit 7 (0x80) : combiné avec bit5 → Timer mode
            #   bits 0-4 (0x1F) : DureeST — durée restante Sleep ou Timer (en minutes)
            ('b13',             c_uint8),   # byte 13 sleep/timer
            # byte 14 : CONSTANTE fixe par type de trame (jamais un CRC)
            #   vérifié sur 5000 trames : Frame65=0x49, Frame69=0x61, Frame77=0x82, Frame83=0x03
            #   Probablement un identifiant de sous-type ou version de protocole.
            ('frame_const',    c_uint8),   # byte 14  constante fixe par type
            ('crc',            c_uint8),   # byte 15
            ('end',          c_uint8),   # byte 16
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        be = self._BE.from_buffer_copy(self.raw_bytes())
        d.update({
            'type':                            65,
            'boost_active':                    be.boost_remain > 0,
            'boost_remaining_min':             be.boost_remain,
            'current_electrolyse_percent':     be.electrolyse,
            'inversion_period_min':             be.inversion_period,
            'shutter_mode_electrolyse_percent': be.shutter_mode,
            # flow_switch : True = pressostat fermé, eau en circulation (bit 2 actif).
            # Confirmé par RE externe : (f[10] >> 2) & 1
            'flow_switch':                     bool(be.io_flags & 0x04),
            # flow_alarm : True = alarme défaut d'écoulement (bit 6 actif).
            # Bit distinct de flow_switch : le pressostat peut être fermé (bit2=1)
            # pendant que l'alarme est levée (bit6=1) → 0x64.
            'flow_alarm':                      bool(be.io_flags & 0x40),
            'volet_actif':                     bool(be.io_flags & (1 << 4)),
            'volet_force':                     bool(be.io_flags & (1 << 3)),
            # polarity_phase_a : True = phase A de polarité (bit 5 actif).
            # Observé : io_flags=0x24 (bit5=1, phase A) → 0x04 (bit5=0, phase B) lors du reset.
            'polarity_phase_a':                bool(be.io_flags & 0x20),
            # salinite (source officielle akeron.js) : bits 0+1 de io_flags.
            # 0=faible, 1=moyen, 2=élevé. Toujours 0 sur notre installation (pas de salinomètre).
            'salinite':                        be.io_flags & 0x03,
            'inversion_timer_min':             be.inversion_timer,
            # elx_fault_code : nibble bas de l'octet 12 (0x0F masqué).
            # 0=normal, 7=arrêt défaut flux (E.07), 3=transitoire
            'elx_fault_code':                  be.elx_fault_code & 0x0F,
            # byte 13 : Sleep / Timer (source officielle akeron.js)
            'sleep':    bool(be.b13 & 0x20) and bool(be.b13 & 0x40),  # bit5 && bit6
            'timer_actif': bool(be.b13 & 0x20) and bool(be.b13 & 0x80),  # bit5 && bit7
            'duree_st': be.b13 & 0x1F,  # durée restante sleep/timer en minutes
            # Noms des bits connus de io_flags (byte 10) pour l'UI Reverse Engineering
            '_bit_names': {
                10: {
                    0: 'salinite_b0',
                    1: 'salinite_b1',
                    2: 'flow_switch',
                    3: 'volet_force',
                    4: 'volet_actif',
                    5: 'polarity_phase_a',
                    6: 'flow_alarm',
                },
            },
        })
        return d
