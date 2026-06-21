from __future__ import annotations

import ctypes
import re
from ctypes import BigEndianStructure, Structure, c_int8, c_uint8, c_uint16
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
            # byte 13  sensor_config_flags :
            #   bit 3 (0x08) : config_capteur_sel_actif — présent (1) quand le capteur SEL est activé,
            #                  absent (0) quand désactivé (observé : 0x19→0x11 à la désactivation)
            #   bit 7 (0x80) : pompes_forcees — CONFIRMÉ : 17 (0x11)→145 (0x91) lors du forçage
            #                  manuel de la pompe pH- pendant 1 min, retour à 17 après ~1,5 min.
            #                  Pendant ce temps : pump_flags (byte 12) = 0x03 (regulation_active=0,
            #                  pompe_moins_active=0) — le mode forcé suspend la régulation auto.
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
            'pompe_moins_active': bool(be.pump_flags & (1 << 6)),
            'regulation_active':  bool(be.pump_flags & (1 << 5)),
            'config_capteur_sel_actif': bool(be.sensor_config_flags & (1 << 3)),
            'pompes_forcees':     bool(be.sensor_config_flags & (1 << 7)),
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
            ('b12', c_uint8), ('b13', c_uint8),
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
            #   bit 2 (0x04) : toujours à 1 dans les données observées (usage inconnu)
            #   bit 3 (0x08) : volet_force (non vérifié)
            #   bit 4 (0x10) : volet_actif (non vérifié)
            #   bits 5+6 (0x60) : alarme défaut d’écoulement — 0 = flux OK, non-zéro = pas de flux
            ('io_flags',     c_uint8),   # byte 10
            ('b11',          c_uint8),   # byte 11 unknown
            # byte 12 : code d’arrêt de l’électrolyseur lié au défaut de flux
            #   0 = normal, 7 = arrêt défaut flux, 3 = transitoire (rétablissement)
            ('elx_fault_code', c_uint8), # byte 12
            ('b13',             c_uint8),   # byte 13 unknown
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
            # flow_switch : True = eau en écoulement (bits 5+6 de io_flags non-actifs)
            # Les bits 5 et 6 passent à 1 simultanément quand l’écoulement s’arrête.
            'flow_switch':                     (be.io_flags & 0x60) == 0,
            'volet_actif':                     bool(be.io_flags & (1 << 4)),
            'volet_force':                     bool(be.io_flags & (1 << 3)),
            'inversion_timer_min':             be.inversion_timer,
            'elx_fault_code':                  be.elx_fault_code,
        })
        return d
