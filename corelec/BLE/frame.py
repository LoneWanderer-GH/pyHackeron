# frame.py
"""
frame.py — Parsing des trames BLE Corelec.

Format d’une trame (17 octets) :
    Octet  0      : sync start = 0x2A (42)
    Octet  1      : type (77 / 83 / 65 / 69)
    Octets 2–14   : payload spécifique au type
    Octet 15      : CRC = XOR des octets 0–14
    Octet 16      : sync end = 0x2A (42)
"""
from dataclasses import dataclass


def crc(data: bytes) -> int:
    """CRC XOR sur les octets 0–14 (l’octet 15 est le CRC attendu)."""
    c = 0
    for b in data:
        c ^= b
    return c & 0xFF


@dataclass
class Frame:
    """Trame BLE Corelec validée (sync + CRC OK).

    Attributs :
        type  Identifiant du type (77, 83, 65, 69).
        raw   Les 17 octets bruts de la trame.
    """
    type: int
    raw: bytearray

    @staticmethod
    def parse(buf: bytes):
        """Analyse ``buf`` (17 octets) et retourne un ``Frame`` ou ``None`` si invalide."""
        if len(buf) != 17:
            return None
        if buf[0] != 42 or buf[16] != 42:
            return None
        if crc(buf[:15]) != buf[15]:
            return None
        return Frame(type=buf[1], raw=bytearray(buf))