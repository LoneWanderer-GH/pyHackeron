# def crc(data):
#     c = 0
#     for b in data:
#         c ^= b
#     return c & 0xFF
#
#
# def u16(msb, lsb):
#     return (msb << 8) | lsb
#
#
# def bit(byte, n):
#     return (byte >> n) & 1
#
# class FrameDecoder:
#
#     def decode(self, frame: bytes):
#         if len(frame) != 17:
#             return None
#
#         if frame[0] != 42 or frame[16] != 42:
#             return None
#
#         if crc(frame[:15]) != frame[15]:
#             return None
#
#         typ = frame[1]
#
#         if typ == 77:
#             return self.decode_77(frame)
#
#         if typ == 83:
#             return self.decode_83(frame)
#
#         if typ == 65:
#             return self.decode_65(frame)
#
#         if typ == 69:
#             return self.decode_69(frame)
#
#         return None
#
#     def decode_77(self, f):
#
#         ph = u16(f[2], f[3]) / 100.0
#         redox = u16(f[4], f[5])
#         temp = u16(f[6], f[7]) / 10.0
#         sel = u16(f[8], f[9]) / 10.0
#
#         return {
#             "type": 77,
#             "ph": ph if 3.5 <= ph <= 9.5 else None,
#             "redox": redox if 350 <= redox <= 1000 else None,
#             "temp": temp if 0 <= temp <= 50 else None,
#             "sel": sel if 0 <= sel <= 10 else None,
#             "alarme": f[10],
#             "warning": f[11] & 0x0F,
#             "alarm_rdx": f[11] >> 4,
#             "pompe_moins_active": bool(f[12] & (1 << 6)),
#             "pompe_chl_elx": bool(f[12] & (1 << 5)),
#             "pompes_forcees": bool(f[13] & (1 << 7)),
#         }
#
#     def decode_83(self, f):
#
#         ph_consigne = u16(f[2], f[3]) / 100.0
#         err_max = u16(f[10], f[11]) / 100.0
#         err_min = u16(f[12], f[13]) / 100.0
#
#         return {
#             "type": 83,
#             "ph_consigne": ph_consigne,
#             "err_max": err_max,
#             "err_min": err_min,
#         }
#
#
#     def decode_69(self, f):
#
#         redox_consigne = u16(f[2], f[3])
#
#         return {
#             "type": 69,
#             "redox_consigne": redox_consigne
#         }
#
#
#     def decode_65(self, f):
#
#         elx = f[2]
#         boost_duration = u16(f[2], f[3])
#
#         boost_active = boost_duration > 0
#
#         return {
#             "type": 65,
#             "elx": elx,
#             "boost_duration": boost_duration,
#             "boost_active": boost_active,
#             "flow_switch": bool(f[10] & (1 << 2)),
#             "volet_actif": bool(f[10] & (1 << 4)),
#             "volet_force": bool(f[10] & (1 << 3)),
#             "raw_field_a10": f[10],
#             "alarme_elx": f[12] & 0x0F,
#         }
#
#     def decode_unknown(self, f):
#
#         return {
#             "type": f[1],
#             "raw": list(f),
#             "hint": "unknown frame (possibly auth / UI / pairing)"
#         }
#
# class Decoder:
#
#     def __init__(self):
#         self.frames = []
#
#     def push(self, frame):
#         d = FrameDecoder().decode(frame)
#         if d:
#             self.frames.append(d)
#             print("DECODE:", d)


# decoder.py

from src.python.BLE.frame import Frame
from src.python.BLE.types import Decoded65, Decoded69, Decoded77, Decoded83, DecodedBase
from src.python.ReverseEngineering.ctypes_frames import (
    Frame65 as CFrame65, Frame69 as CFrame69,
    Frame77 as CFrame77, Frame83 as CFrame83,
)


class Decoder:
    """Décode une Frame BLE en Decoded* en déléguant aux ctypes_frames."""

    def decode(self, frame: Frame) -> DecodedBase:
        dispatch = {77: self._77, 83: self._83, 65: self._65, 69: self._69}
        handler = dispatch.get(frame.type)
        if handler:
            return handler(frame.raw)
        return DecodedBase(type=frame.type, raw=frame.raw)

    def _77(self, f: bytearray) -> Decoded77:
        d = CFrame77.from_bytes(f).as_dict()
        return Decoded77(
            type=77, raw=f,
            ph=d['ph'], redox=d['redox'], temp=d['temp'], sel=d['sel'],
            alarme=d['alarme'], warning=d['warning'], alarm_rdx=d['alarm_rdx'],
            pompe_moins_active=d['pompe_moins_active'],
            pompe_chl_elx=d['pompe_chl_elx'],
            pompes_forcees=d['pompes_forcees'],
        )

    def _83(self, f: bytearray) -> Decoded83:
        d = CFrame83.from_bytes(f).as_dict()
        return Decoded83(
            type=83, raw=f,
            ph_consigne=d['ph_consigne'],
            err_max=d['err_max'],
            err_min=d['err_min'],
        )

    def _69(self, f: bytearray) -> Decoded69:
        d = CFrame69.from_bytes(f).as_dict()
        return Decoded69(type=69, raw=f, redox_consigne=d['redox_consigne'])

    def _65(self, f: bytearray) -> Decoded65:
        d = CFrame65.from_bytes(f).as_dict()
        return Decoded65(
            type=65, raw=f,
            boost_active=d['boost_active'],
            boost_remaining_min=d['boost_remaining_min'],
            current_electrolyse_percent=d['current_electrolyse_percent'],
            cycle_period_min=d['cycle_period_min'],
            shutter_mode_electrolyse_percent=d['shutter_mode_electrolyse_percent'],
            flow_switch=d['flow_switch'],
            volet_actif=d['volet_actif'],
            volet_force=d['volet_force'],
            cycle_a_min=d['cycle_a_min'],
            cycle_b_min=d['cycle_b_min'],
        )

        ph = u16(f[2], f[3]) / 100
        redox = u16(f[4], f[5])
        temp = u16(f[6], f[7]) / 10
        sel = u16(f[8], f[9]) / 10
        
        # return {
        #         "type"              : 77,
        #         "ph"                : ph if 3.5 <= ph <= 9.5 else None,
        #         "redox"             : redox if 350 <= redox <= 1000 else None,
        #         "temp"              : temp if 0 <= temp <= 50 else None,
        #         "sel"               : sel if 0 <= sel <= 10 else None,
        #         "alarme"            : f[10],
        #         "warning"           : f[11] & 0x0F,
        #         "alarm_rdx"         : f[11] >> 4,
        #         "pompe_moins_active": bool(f[12] & (1 << 6)),
        #         "pompe_chl_elx"     : bool(f[12] & (1 << 5)),
        #         "pompes_forcees"    : bool(f[13] & (1 << 7)),
        # }
        return Decoded77(
                type=77,
                ph=ph if 3.5 <= ph <= 9.5 else None,
                redox=redox if 350 <= redox <= 1000 else None,
                temp=temp if 0 <= temp <= 50 else None,
                sel=sel if 0 <= sel <= 10 else None,
                alarme=f[10],
                warning=f[11] & 0x0F,
                alarm_rdx=f[11] >> 4,
                pompe_moins_active=bool(f[12] & (1 << 6)),
                pompe_chl_elx=bool(f[12] & (1 << 5)),
                pompes_forcees=bool(f[13] & (1 << 7)),
                raw=f,
        )
    
    def _83(self, f: bytearray) -> Decoded83:
        # return {
        #         "type"       : 83,
        #         "ph_consigne": u16(f[2], f[3]) / 100,
        #         "err_max"    : u16(f[10], f[11]) / 100,
        #         "err_min"    : u16(f[12], f[13]) / 100,
        # }
        return Decoded83(
                type=83,
                ph_consigne=u16(f[2], f[3]) / 100,
                err_max=u16(f[10], f[11]) / 100,
                err_min=u16(f[12], f[13]) / 100,
                raw=f,
        )
    
    def _69(self, f: bytearray) -> Decoded69:
        return Decoded69(
                type=69,
                redox_consigne=u16(f[2], f[3]),
                raw=f,
        )
    
    # def _65(self, f):
    #     print(f"65 RAW {f.hex()=} ({type(f)=}) {len(f)=}")
    #     # boost = u16(f[2], f[3])
    #     # print("DEBUG 65 boost raw:", f[2], f[3], hex(boost))
    #     for i in range(0, len(f)):
    #         print(f"byte {i}", f[i], int(f[i]), float(f[i]), ascii(f[i]))
    #     # return {
    #     #     "type": 65,
    #     #     "elx": f[2],
    #     #     "boost_duration": boost,
    #     #     "boost_active": boost > 0,
    #     #     "flow_switch": bool(f[10] & (1 << 2)),
    #     #     "volet_actif": bool(f[10] & (1 << 4)),
    #     #     "volet_force": bool(f[10] & (1 << 3)),
    #     #     "raw_field_a10": f[10],
    #     #     "alarme_elx": f[12] & 0x0F,
    #     # }
    #     return {
    #             "type"            : 65,
    #
    #             # production chlorinateur
    #             "elx"             : f[2],
    #             "boost_flag" : bool(f[3] & 0x01),
    #             # boost preset (UI default)
    #             "boost_preset_min": f[6],
    #
    #             # production mode volet
    #             "volet_prod"      : f[9],
    #
    #             # flags IO
    #             "flow_switch"     : bool(f[10] & (1 << 2)),
    #             "volet_actif"     : bool(f[10] & (1 << 4)),
    #             "volet_force"     : bool(f[10] & (1 << 3)),
    #
    #             # état interne inconnu
    #             "state_3"         : f[3],
    #             "state_4"         : f[4],
    #             "state_8"         : f[8],
    #             "state_11"        : f[11],
    #
    #             "raw"             : list(f),
    #     }
    
    def _65(self, f: bytearray) -> Decoded65:
        boost_remaining_min = f[4]
        cycle_period_min = f[6]
        
        boost_active = boost_remaining_min > 0
        
        # return {
        #         "type"                            : 65,
        
        #         # boost utilisateur
        #         "boost_active"                    : boost_active,
        #         "boost_remaining_min"             : boost_remaining_min,
        #         "current_electrolyse_percent"     : f[2],
        #         # paramètre système
        #         "cycle_period_min"                : cycle_period_min,
        
        #         # shutter mode
        #         "shutter_mode_electrolyse_percent": f[9],
        
        #         # capteurs
        #         "flow_switch"                     : bool(f[10] & (1 << 2)),
        #         "volet_actif"                     : bool(f[10] & (1 << 4)),
        #         "volet_force"                     : bool(f[10] & (1 << 3)),
        
        #         # cycles internes (non interprétés)
        #         "cycle_a_min"                     : f[8],
        #         "cycle_b_min"                     : f[15],
        
        #         "raw"                             : list(f),
        # }
        return Decoded65(
                type=65,
                boost_active=boost_active,
                boost_remaining_min=boost_remaining_min,
                current_electrolyse_percent=f[2],
                cycle_period_min=cycle_period_min,
                shutter_mode_electrolyse_percent=f[9],
                flow_switch=bool(f[10] & (1 << 2)),
                volet_actif=bool(f[10] & (1 << 4)),
                volet_force=bool(f[10] & (1 << 3)),
                cycle_a_min=f[8],
                cycle_b_min=f[15],
                raw=f,
        )
