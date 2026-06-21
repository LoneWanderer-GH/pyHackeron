# # import asyncio
# # from bleak import BleakClient
# #
# # ADDRESS = "B4:E3:F9:5A:0A:13"
# # CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"
# #
# #
# # def crc(data):
# #     c = 0
# #     for b in data:
# #         c ^= b
# #     return c & 0xFF
# #
# #
# # def build_ask(cmd: int):
# #     pkt = bytearray([42, 82, 63, cmd, 0, 42])
# #     pkt[4] = crc(pkt[:4])
# #     return bytes(pkt)
# #
# #
# # def notify(sender, data):
# #     print("\nNOTIFY:", data.hex(), data)
# #
# #
# # async def send_sequence(client, name, seq):
# #     print(f"\n--- {name} ---")
# #
# #     for cmd in seq:
# #         pkt = build_ask(cmd)
# #
# #         print("TX:", pkt.hex())
# #
# #         await client.write_gatt_char(CHAR_UUID, pkt, response=False)
# #         await asyncio.sleep(0.5)
# #
# #
# # async def main():
# #     async with BleakClient(ADDRESS) as client:
# #
# #         print("Connected:", client.is_connected)
# #
# #         await client.start_notify(CHAR_UUID, notify)
# #
# #         # EXACT MATCH CODE C++
# #         seq_main = [77, 83, 65, 69]
# #
# #         # HYPOTHÈSE PIN (ASCII split)
# #         seq_pin = [72, 78, 51, 58]
# #
# #         await send_sequence(client, "SEQ MAIN (77/83/65/69)", seq_main)
# #
# #         await asyncio.sleep(1)
# #
# #         await send_sequence(client, "SEQ PIN DERIVED (!7278+5158!)", seq_pin)
# #
# #         print("\nListening...")
# #         await asyncio.sleep(20)
# #
# #
# # asyncio.run(main())
#
#
# import asyncio
# from bleak import BleakClient
#
# ADDRESS = "B4:E3:F9:5A:0A:13"
# SERVICE_UUID = "0bd51666-e7cb-469b-8e4d-2742f1ba77cc"
# CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"
#
#
# def crc(data):
#     c = 0
#     for b in data:
#         c ^= b
#     return c & 0xFF
#
#
# def build_ask(cmd):
#     pkt = bytearray([42, 82, 63, cmd, 0, 42])
#     pkt[4] = crc(pkt[:4])
#     return bytes(pkt)
#
# #
# # class StateMachine:
# #     def __init__(self):
# #         self.queue = asyncio.Queue()
# #         self.done = asyncio.Event()
# #
# #     async def notify(self, sender, data):
# #         print("RX:", data.hex())
# #
# #         # chaque notif = potentiel ACK valide
# #         await self.queue.put(data)
# #
# #     async def wait_ack(self, timeout=2):
# #         try:
# #             obj  = await asyncio.wait_for(self.queue.get(), timeout)
# #             print(f"Wait ack {obj=}")
# #             return True
# #         except asyncio.TimeoutError:
# #             return False
#
#
# async def run_sequence(client,
#                        # sm,
#                        seq,
#                        name):
#     print(f"\n--- {name} ---")
#
#     for cmd in seq:
#         print("CMD:", cmd)
#         pkt = build_ask(cmd)
#
#         print("TX:", pkt.hex())
#         rep = await client.write_gatt_char(CHAR_UUID, pkt, response=True)
#         # print("REP:", rep)
#         # CRITIQUE : attendre ACK BLE (INDICATE)
#         # ok = await sm.wait_ack(timeout=0.5)
#         # print(f"Reply is={ok}")
#         #
#         # if not ok:
#         #     print("NO ACK → abort sequence")
#         #     return False
#         #
#         # await asyncio.sleep(0.2)
#         await asyncio.sleep(0.5)
# #     print("Last REP:", rep)
#     return True
#
# def notification_handler(sender, data):
#     print(f"Notification BLE received {data.hex()=}")
#
# async def main():
#     # sm = StateMachine()
#
#     async with BleakClient(ADDRESS, timeout=120) as client:
#
#         print("Connected:", client.is_connected)
#
#         # await client.start_notify(CHAR_UUID, sm.notify)
#         await client.start_notify(CHAR_UUID, notification_handler)
#
#         seq_main = [77, 83, 65, 69]
#         seq_pin = [72, 78, 51, 58]
#
#         ok = await run_sequence(client,
#                                 # sm,
#                                 seq_main,
#                                 "SEQ MAIN")
#         #
#         # if not ok:
#         #     print("MAIN FAILED")
#         #     # return
#         #
#         # await asyncio.sleep(0.5)
#         #
#         ok = await run_sequence(client,
#                                 # sm,
#                                 seq_pin,
#                                 "SEQ PIN")
#         # if not ok:
#         #     print("SEQ PIN FAILED")
#         #     return
#         # print("Listening...")
#         # await asyncio.sleep(30)
#
#
# asyncio.run(main())





import asyncio
from bleak import BleakClient

from corelec.ReverseEngineering.decoder import FrameDecoder, crc

ADDRESS = "B4:E3:F9:5A:0A:13"
CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"

#
# def crc(data):
#     c = 0
#     for b in data:
#         c ^= b
#     return c & 0xFF


def build_ask(cmd):
    pkt = bytearray([42, 82, 63, cmd, 0, 42])
    pkt[4] = crc(pkt[:4])
    return bytes(pkt)


# class StreamParser:
#     def __init__(self):
#         self.buf = deque(maxlen=2048)
#
#     def feed(self, data: bytes):
#         for b in data:
#             self.buf.append(b)
#
#         frames = []
#
#         arr = list(self.buf)
#
#         i = 0
#         while i < len(arr) - 16:
#             if arr[i] == 42 and arr[i + 16] == 42:
#                 frame = arr[i:i + 17]
#                 frames.append(frame)
#                 i += 17
#             else:
#                 i += 1
#
#         return frames

decoder = FrameDecoder()

class StreamParser:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf.extend(data)

        frames = []

        while True:
            start = self.buf.find(0x2A)  # '*'
            if start == -1:
                self.buf.clear()
                return frames

            if len(self.buf) < start + 17:
                self.buf = self.buf[start:]
                return frames

            if self.buf[start + 16] != 0x2A:
                self.buf.pop(0)
                continue

            frame = bytes(self.buf[start:start + 17])
            del self.buf[:start + 17]

            frames.append(frame)

        return frames

parser = StreamParser()


def notify(sender, data: bytearray):
    frames = parser.feed(data)
    print("BUF SIZE:", len(parser.buf))
    print("RAW:", data.hex())

    for f in frames:
        print("FRAME:", bytes(f).hex())
        d = decoder.decode(f)
        print(d)


async def send_seq(client, seq, name):
    print(f"\n--- {name} ---")

    for cmd in seq:
        pkt = build_ask(cmd)

        print("TX:", pkt.hex())
        await client.write_gatt_char(CHAR_UUID, pkt, response=True)

        await asyncio.sleep(0.7)


async def main():
    async with BleakClient(ADDRESS, timeout=120) as client:

        print("Connected:", client.is_connected)

        await client.start_notify(CHAR_UUID, notify)

        seq_main = [77, 83, 65, 69]
        seq_pin = [72, 78, 51, 58]

        await send_seq(client, seq_main, "SEQ MAIN")
        await asyncio.sleep(30)

        await send_seq(client, seq_pin, "SEQ PIN")

        await asyncio.sleep(30)
        

asyncio.run(main())