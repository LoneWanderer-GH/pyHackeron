# frame.py
from dataclasses import dataclass

def crc(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c & 0xFF


@dataclass
class Frame:
    type: int
    raw: bytearray

    @staticmethod
    def parse(buf: bytes):
        if len(buf) != 17:
            return None
        if buf[0] != 42 or buf[16] != 42:
            return None
        if crc(buf[:15]) != buf[15]:
            return None
        return Frame(type=buf[1], raw=bytearray(buf))