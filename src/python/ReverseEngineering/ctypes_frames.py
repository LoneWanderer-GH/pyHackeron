from ctypes import Structure, c_uint8, c_int8
from ctypes import BigEndianStructure, c_uint16, Union
from typing import Dict, Any, ByteString


def u16(msb: int, lsb: int) -> int:
    return (msb << 8) | lsb


class FrameBase(Structure):
    _fields_ = [(f'b{i}', c_uint8) for i in range(17)]

    @classmethod
    def from_bytes(cls, raw: ByteString):
        inst = cls()
        # raw may be shorter; fill available bytes
        for i in range(min(len(raw), 17)):
            setattr(inst, f'b{i}', raw[i])
        return inst

    def raw_list(self):
        return [getattr(self, f'b{i}') for i in range(17)]

    def as_dict(self) -> Dict[str, Any]:
        # default: expose raw bytes as raw_b0..raw_b16
        d: Dict[str, Any] = {}
        for i in range(17):
            d[f'raw_b{i}'] = getattr(self, f'b{i}')
        # default: no known offsets at base
        d['_known_offsets'] = [0, 1, 15, 16]
        return d


# Bitfield helpers
class _WarningBits(BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('alarm_rdx', c_uint8, 4),
        ('warning', c_uint8, 4),
    ]


class _WarningUnion(Union):
    _fields_ = [
        ('asByte', c_uint8),
        ('bits', _WarningBits),
    ]


class _FlagsBits(BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('b7', c_uint8, 1),
        ('b6', c_uint8, 1),
        ('b5', c_uint8, 1),
        ('b4', c_uint8, 1),
        ('b3', c_uint8, 1),
        ('b2', c_uint8, 1),
        ('b1', c_uint8, 1),
        ('b0', c_uint8, 1),
    ]


class _FlagsUnion(Union):
    _fields_ = [
        ('asByte', c_uint8),
        ('bits', _FlagsBits),
    ]


class Frame77(FrameBase):
    # Big-endian overlay declaring explicit multi-byte fields
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync', c_uint8),
            ('typ', c_uint8),
            ('ph', c_uint16),      # bytes 2-3
            ('redox', c_uint16),   # bytes 4-5
            ('temp', c_uint16),    # bytes 6-7 (temp*10)
            ('sel', c_uint16),     # bytes 8-9 (sel*10)
                ('alarme', c_uint8),   # byte 10
                ('warning_u', _WarningUnion),  # byte 11 as bitfields
                ('flags12_u', _FlagsUnion),    # byte 12 as bitfields
                ('b13', c_uint8),
            ('b14', c_uint8),
            ('crc', c_uint8),
            ('end', c_uint8),
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        # create BE view from raw bytes
        raw = bytes(self.raw_list())
        be = Frame77._BE.from_buffer_copy(raw)
        ph = be.ph / 100.0
        redox = be.redox
        temp = be.temp / 10.0
        sel = be.sel / 10.0
        d.update({
            'type': 77,
            'ph': ph if 3.5 <= ph <= 9.5 else None,
            'redox': redox if 350 <= redox <= 1000 else None,
            'temp': temp if 0 <= temp <= 50 else None,
            'sel': sel if 0 <= sel <= 10 else None,
            'alarme': be.alarme,
            'warning': int(be.warning_u.bits.warning),
            'alarm_rdx': int(be.warning_u.bits.alarm_rdx),
            'pompe_moins_active': bool(be.flags12_u.bits.b6),
            'pompe_chl_elx': bool(be.flags12_u.bits.b5),
            'pompes_forcees': bool(be.b13 & (1 << 7)),
        })
        d['_known_offsets'] = sorted(set(d['_known_offsets']) | {2,3,4,5,6,7,8,9,10,11,12})
        return d


class Frame83(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync', c_uint8),
            ('typ', c_uint8),
            ('ph_consigne', c_uint16),  # 2-3
            ('b4', c_uint8),
            ('b5', c_uint8),
            ('b6', c_uint8),
            ('b7', c_uint8),
            ('b8', c_uint8),
            ('b9', c_uint8),
            ('err_max', c_uint16),      # 10-11
            ('err_min', c_uint16),      # 12-13
            ('b14', c_uint8),
            ('crc', c_uint8),
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        raw = bytes(self.raw_list())
        be = Frame83._BE.from_buffer_copy(raw)
        d.update({
            'type': 83,
            'ph_consigne': be.ph_consigne / 100.0,
            'err_max': be.err_max / 100.0,
            'err_min': be.err_min / 100.0,
        })
        d['_known_offsets'] = sorted(set(d['_known_offsets']) | {2,3,10,11,12,13})
        return d


class Frame69(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync', c_uint8),
            ('typ', c_uint8),
            ('redox_consigne', c_uint16),
            ('b4', c_uint8), ('b5', c_uint8), ('b6', c_uint8), ('b7', c_uint8),
            ('b8', c_uint8), ('b9', c_uint8), ('b10', c_uint8), ('b11', c_uint8),
            ('b12', c_uint8), ('b13', c_uint8), ('crc', c_uint8), ('end', c_uint8),
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        raw = bytes(self.raw_list())
        be = Frame69._BE.from_buffer_copy(raw)
        d.update({
            'type': 69,
            'redox_consigne': be.redox_consigne,
        })
        d['_known_offsets'] = sorted(set(d['_known_offsets']) | {2,3})
        return d


class Frame65(FrameBase):
    class _BE(BigEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('sync', c_uint8), ('typ', c_uint8),
            ('b2', c_uint8), ('b3', c_uint8),
            ('b4', c_uint8), ('b5', c_uint8),
            ('b6', c_uint8), ('b7', c_uint8),
            ('b8', c_uint8), ('b9', c_uint8),
            ('flags10_u', _FlagsUnion), ('b11', c_uint8),
            ('b12', c_uint8), ('b13', c_uint8),
            ('b14', c_uint8),
            ('b15', c_int8), # signed ?
            ('end', c_uint8),
        ]

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        raw = bytes(self.raw_list())
        be = Frame65._BE.from_buffer_copy(raw)
        boost_remaining_min = be.b4
        cycle_period_min = be.b6
        flags10_bits = be.flags10_u.bits
        d.update({
            'type': 65,
            'boost_active': boost_remaining_min > 0,
            'boost_remaining_min': boost_remaining_min,
            'current_electrolyse_percent': be.b2,
            'cycle_period_min': cycle_period_min,
            'shutter_mode_electrolyse_percent': be.b9,
            'flow_switch': bool(flags10_bits.b2),
            'volet_actif': bool(flags10_bits.b4),
            'volet_force': bool(flags10_bits.b3),
            'cycle_a_min': be.b8,
            'cycle_b_min': be.b15,
        })
        d['_known_offsets'] = sorted(set(d['_known_offsets']) | {2,4,6,8,9,10})
        return d
