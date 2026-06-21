# import asyncio
# from bleak import BleakClient
#
# # ADDRESS = "B4:E3:F9:5A:0A:13"
# CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"
# ADDRESS = "B4:E3:F9:5A:0A:13"
# CODES = [b"!7278+5158!",
# b"7278+5158",
# b"72785158",
# b"AUTH=7278+5158",
# ]
#
# def notification_handler(sender, data):
#     print("\n=== INDICATION ===")
#     print("HEX :", data.hex())
#     print("TXT :", data.decode("ascii", errors="replace"))
#
# async def main():
#     async with BleakClient(ADDRESS) as client:
#         print("Connected:", client.is_connected)
#
#         await client.start_notify(CHAR_UUID, notification_handler)
#
#         print("Notify enabled")
#         for CODE in CODES:
#             print(f"Sending auth code... {CODE=}")
#             await client.write_gatt_char(CHAR_UUID, CODE)
#
#             await asyncio.sleep(2)
#
#             print("Waiting for responses (30s)...")
#             await asyncio.sleep(30)
#
#         await client.stop_notify(CHAR_UUID)
#
# asyncio.run(main())

import asyncio
from bleak import BleakClient

ADDRESS = "B4:E3:F9:5A:0A:13"
CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"

TESTS = [
    b"!7278+5158!",
    b"!7278+5158",
    b"7278+5158",
    b"72785158",
    b"AUTH!7278+5158!",
    b"LOGIN!7278+5158!",
    b"PASS!7278+5158!",
    b"OPEN!7278+5158!",
    b"!7278+5158!\r",
    b"!7278+5158!\n",
    b"!7278+5158!" + b"\x00"*5,
    b"\x01" + b"!7278+5158!",
    b"\x02" + b"!7278+5158!",
]

def notify(sender, data):
    print("RX HEX :", data.hex())
    print("RX TXT :", data.decode("ascii", errors="replace"))

async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connected:", client.is_connected)

        await client.start_notify(CHAR_UUID, notify)

        for i, payload in enumerate(TESTS):
            print(f"\nTX {i+1}/{len(TESTS)}:", payload)

            try:
                await client.write_gatt_char(CHAR_UUID, payload)
                await asyncio.sleep(1.5)
            except Exception as e:
                print("ERR:", e)

        print("\nListening 20s...")
        await asyncio.sleep(20)

        await client.stop_notify(CHAR_UUID)

asyncio.run(main())