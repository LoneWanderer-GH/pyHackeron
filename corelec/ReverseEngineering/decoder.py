# decoder.py

from corelec.BLE.frame import Frame
from corelec.BLE.types import Decoded65, Decoded69, Decoded77, Decoded83, DecodedBase
from corelec.ReverseEngineering.ctypes_frames import (
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

