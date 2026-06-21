# import asyncio
# from bleak import BleakClient
#
# ADDRESS = "B4:E3:F9:5A:0A:13"
#
# async def main():
#     async with BleakClient(ADDRESS) as client:
#         print("Connected:", client.is_connected)
#
#         services = client.services
#
#         for service in services:
#             print(f"\nSERVICE {service.uuid}")
#
#             for char in service.characteristics:
#                 print(
#                     f"  CHAR {char.uuid}"
#                     f" properties={char.properties}"
#                 )
#                 if "read" in char.properties:
#                     try:
#                         value = await client.read_gatt_char(char.uuid)
#                         print(char.uuid, value)
#                     except Exception as e:
#                         print(e)
#
# asyncio.run(main())


import asyncio
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "REGUL"
CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"
ADDRESS = "B4:E3:F9:5A:0A:13"
def notification_handler(sender, data):
    try:
        ascii_data = data.decode("ascii", errors="replace")
    except Exception:
        ascii_data = ""

    print("\n=== NOTIFICATION ===")
    print("HEX  :", data.hex())
    print("ASCII:", ascii_data)

async def main():
    # print("Recherche du régulateur...")
    # print(" - par nom")
    # device = await BleakScanner.find_device_by_name(
    #     DEVICE_NAME,
    #     timeout=10
    # )
    #
    # if not device:
    #     print(f" - {DEVICE_NAME} introuvable par NOM, essai par adresse mac {ADDRESS}")
    #     device = await BleakScanner.find_device_by_address(ADDRESS,
    #                                                        timeout=20)
    # if not device:
    #     print("Device pas trouvé par nom ni adresse ...")
    #     return
    # print(f"Trouvé : {device}")
    #
    # async with BleakClient(device) as client:
    
    async with BleakClient(ADDRESS) as client:

        print(f"Connecté : {client.is_connected}")
        print(client.services)
        print("\n=== SERVICES ===")

        for service in client.services:
            print(f"\nSERVICE {service.uuid}")

            for char in service.characteristics:

                print(
                    f"  CHAR {char.uuid}"
                    f" properties={char.properties}"
                )

                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        print("    VALUE HEX :", value.hex())

                        try:
                            print(
                                "    VALUE TXT :",
                                value.decode("ascii")
                            )
                        except Exception:
                            pass

                    except Exception as e:
                        print("    READ ERROR:", e)

        print("\nActivation des indications...")

        try:
            await client.start_notify(
                CHAR_UUID,
                notification_handler
            )
            print("Notify OK")
        except Exception as e:
            print("Notify KO:", e)

        test_commands = [
            b"\x00",
            b"\x01",
            b"\x02",
            b"\x03",
            b"\x10",
            b"\x20",
            b"\x30",
            b"\xAA",
            b"\xAA\x55",
            b"\x55\xAA",
            b"STATUS",
            b"READ",
            b"GET",
            b"INFO",
            b"DATA",
        ]

        print("\n=== TEST COMMANDES ===")

        for cmd in test_commands:

            try:
                print(
                    f"\nTX: {cmd.hex()} "
                    f"({repr(cmd)})"
                )

                await client.write_gatt_char(
                    CHAR_UUID,
                    cmd
                )

                await asyncio.sleep(2)

            except Exception as e:
                print("Erreur:", e)

        print(
            "\nLaisse tourner le programme."
            "\nOuvre maintenant l'application Corelec,"
            "\nconnecte-toi au régulateur,"
            "\nnavigue dans les écrans."
        )

        while True:
            await asyncio.sleep(1)

asyncio.run(main())