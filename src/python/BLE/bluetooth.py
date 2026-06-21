from src.python.BLE.frame import crc


def build_ask(cmd:int)-> bytes:
    pkt = bytearray([42, 82, 63, cmd, 0, 42])
    pkt[4] = crc(pkt[:4])
    return bytes(pkt)
