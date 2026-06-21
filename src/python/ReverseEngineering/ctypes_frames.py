from __future__ import annotations

import ctypes
import re
from ctypes import BigEndianStructure, Structure, Union, c_int8, c_uint8, c_uint16
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
# Bitfield helpers
# ---------------------------------------------------------------------------

class _WarningBits(BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('alarm_rdx', c_uint8, 4),
        ('warning',   c_uint8, 4),
    ]


class _WarningUnion(Union):
    _fields_ = [('asByte', c_uint8), ('bits', _WarningBits)]


class _FlagsBits(BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('b7', c_uint8, 1), ('b6', c_uint8, 1),
        ('b5', c_uint8, 1), ('b4', c_uint8, 1),
        ('b3', c_uint8, 1), ('b2', c_uint8, 1),
        ('b1', c_uint8, 1), ('b0', c_uint8, 1),
    ]


class _FlagsUnion(Union):
    _fields_ = [('asByte', c_uint8), ('bits', _FlagsBits)]


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
            ('alarme',    c_uint8),        # byte 10
            ('warning_u', _WarningUnion),  # byte 11  (alarm_rdx[7:4] | warning[3:0])
            ('flags12_u', _FlagsUnion),    # byte 12  (pompe_moins=b6, pompe_chl=b5)
            ('b13',       c_uint8),        # byte 13  (pompes_forcees = bit7)
            ('b14',       c_uint8),        # byte 14  unknown
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
            'warning':            int(be.warning_u.bits.warning),
            'alarm_rdx':          int(be.warning_u.bits.alarm_rdx),
            'pompe_moins_active': bool(be.flags12_u.bits.b6),
            'pompe_chl_elx':      bool(be.flags12_u.bits.b5),
            'pompes_forcees':     bool(be.b13 & (1 << 7)),
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
            ('b14', c_uint8),
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
            ('b12', c_uint8), ('b13', c_uint8), ('b14', c_uint8),
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
            ('electrolyse',  c_uint8),   # byte 2  current_electrolyse_percent
            ('b3',           c_uint8),   # byte 3  unknown
            ('boost_remain', c_uint8),   # byte 4  boost_remaining_min
            ('b5',           c_uint8),   # byte 5  unknown
            ('cycle_period', c_uint8),   # byte 6  cycle_period_min
            ('b7',           c_uint8),   # byte 7  unknown
            ('cycle_a',      c_uint8),   # byte 8  cycle_a_min
            ('shutter_mode', c_uint8),   # byte 9  shutter_mode_electrolyse_percent
            ('flags10_u',    _FlagsUnion),  # byte 10  flow_switch/volet_actif/volet_force
            ('b11',          c_uint8),   # byte 11 unknown
            ('b12',          c_uint8),   # byte 12 unknown
            ('b13',          c_uint8),   # byte 13 unknown
            ('b14',          c_uint8),   # byte 14 unknown
            ('cycle_b',      c_int8),    # byte 15 cycle_b_min (signed) — overlaps CRC slot
            ('end',          c_uint8),   # byte 16
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        be = self._BE.from_buffer_copy(self.raw_bytes())
        flags = be.flags10_u.bits
        d.update({
            'type':                            65,
            'boost_active':                    be.boost_remain > 0,
            'boost_remaining_min':             be.boost_remain,
            'current_electrolyse_percent':     be.electrolyse,
            'cycle_period_min':                be.cycle_period,
            'shutter_mode_electrolyse_percent': be.shutter_mode,
            'flow_switch':                     bool(flags.b2),
            'volet_actif':                     bool(flags.b4),
            'volet_force':                     bool(flags.b3),
            'cycle_a_min':                     be.cycle_a,
            'cycle_b_min':                     be.cycle_b,
        })
        return d
