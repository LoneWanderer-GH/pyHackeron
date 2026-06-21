# from bleak import BleakClient
# import asyncio
#
# ADDRESS = "E7:4A:DB:3B:62:E5"
#
# async def main():
#     try:
#         async with BleakClient(ADDRESS, timeout=120) as client:
#             print("connected", client.is_connected, "to name", client.name )
#
#             for service in client.services:
#                 print(service.uuid)
#
#     except Exception as e:
#         print(e)
#
# asyncio.run(main())


import asyncio
from bleak import BleakClient

ADDRESS = "E7:4A:DB:3B:62:E5"

NOTIFY_UUID = "fbde0104-4c7b-4e67-8292-a9b8e686cf87"

async def main():

    def cb(_, data):
        print("NOTIFY:", data.hex())

    async with BleakClient(ADDRESS, timeout=120) as client:

        print("connected =", client.is_connected)

        await client.start_notify(NOTIFY_UUID, cb)

        while True:
            await asyncio.sleep(1)

asyncio.run(main())