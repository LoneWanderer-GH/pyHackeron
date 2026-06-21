# # # clean_integration.py
# # import asyncio
# # import json
# # from datetime import datetime
# #
# # from bleak import BleakClient
# #
# # from corelec.BLE.bluetooth import build_ask
# # from corelec.BLE.frame import Frame
# # from ReverseEngineering.decoder import Decoder
# # from corelec.BLE.stream import StreamParser
# # from corelec.Analyse.model import RegulatorState
# # NAME = "REGUL."
# # ADDRESS = "B4:E3:F9:5A:0A:13"
# # CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"
# #
# # parser = StreamParser()
# # decoder = Decoder()
# # state = RegulatorState()
# #
# #
# # def notify(_, data):
# #     print("\nRAW BLE:", data.hex())
# #     frames = parser.feed(data)
# #
# #     for raw in frames:
# #         print("FRAME RAW:", raw.hex())
# #         f = Frame.parse(raw)
# #         if not f:
# #             continue
# #         db.store_raw_frame(f)
# #         for i, b in enumerate(f.raw):
# #             db.store_byte(f.type, i, b)
# #
# #         # print("TYPE:", f.type, "RAW:", f.raw.hex())
# #         d = decoder.decode(f)
# #         # print("DECODE:", d)
# #         for k, v in decoded.items():
# #             if isinstance(v, (int, float, bool)):
# #                 db.store_decoded(k, v)
# #         state.update(d)
# #         # print(state.json())
# #
# # SEQ_MAIN = [77, 83, 65, 69]
# # # SEQ_PIN  = [72, 78, 51, 58]
# #
# #
# # async def send_seq(client, seq):
# #     for cmd in seq:
# #         pkt = build_ask(cmd)
# #         await client.write_gatt_char(CHAR_UUID, pkt, response=True)
# #         await asyncio.sleep(0.5)
# #
# #
# # async def poll_loop(client):
# #     while True:
# #         await send_seq(client, SEQ_MAIN)
# #         await asyncio.sleep(2)
# #         #
# #         # await send_seq(client, SEQ_PIN)
# #         # await asyncio.sleep(2)
# #
# # async def dump_loop(state: RegulatorState):
# #     while True:
# #         print(f"\n=== STATE DUMP ===\n{datetime.now().isoformat()}")
# #         print(json.dumps(state.json(), indent=2, ensure_ascii=False))
# #         await asyncio.sleep(5)
# #
# # async def main():
# #     print(f"Connecting to {ADDRESS}")
# #     async with BleakClient(ADDRESS, timeout=120) as client:
# #         print(f"Connected to Corelec Regulator: {client.name} @ {ADDRESS}")
# #
# #         await client.start_notify(CHAR_UUID, notify)
# #
# #         asyncio.create_task(poll_loop(client))
# #         asyncio.create_task(dump_loop(state))
# #
# #         await asyncio.sleep(999999)
# #
# #
# # asyncio.run(main())
#
#
# # clean_integration.py
# import asyncio
# import sys
# import threading
#
# from PyQt6.QtWidgets import QApplication
# from pyreadline3.logger import control
#
# from corelec.Analyse.database import Database
# from corelec.Analyse.model import RegulatorState
# from corelec.BLE.Acquisition import Acquisition
# from corelec.UI.dashboard import Dashboard
# from corelec.UI.signals import signals
#
# ADDRESS = "B4:E3:F9:5A:0A:13"
# #
# # class Controller:
# #
# #     def __init__(self):
# #         self.state = RegulatorState()
# #         self.db = Database()
# #         self.address = ADDRESS
# #
# #         self.acq = None
# #         self.running = True
# #
# #     async def start(self):
# #
# #         while self.running:
# #
# #             self.acq = Acquisition(
# #                 self.address,
# #                 self.state,
# #                 self.db
# #             )
# #
# #             await self.acq.run()
# #
# #             # cancel global
# #             if self.acq.stop_event.is_set():
# #                 break
# #
# #     def stop(self):
# #         self.running = False
# #         if self.acq:
# #             self.acq.stop_event.set()
# #
# #     def restart(self):
# #         if self.acq:
# #             self.acq.stop_event.set()
#
#
# # def run_ble(acq):
# #
# #     asyncio.run(acq.run())
#
#
# def run_ble(address:str, state:RegulatorState, database:Database):
#     stop_all = threading.Event()
#     while not stop_all.is_set():
#         acq = Acquisition(address, state, database)
#         asyncio.run(acq.run())
#
# def main():
#
#     state = RegulatorState()
#     # controller = Controller()
#     database = Database()
#
#     # signals.cancel_requested.connect(controller.stop)
#     # signals.retry_requested.connect(controller.restart)
#     #
#     # acquisition = Acquisition(
#     #         ADDRESS,
#     #         state,
#     #         database
#     # )
#     #
#     # t = threading.Thread(
#     #         target=run_ble,
#     #         args=(acquisition,),
#     #         daemon=True
#     # )
#     #
#     # t.start()
#
#     app = QApplication(sys.argv)
#
#     dashboard = Dashboard(state,database)
#     dashboard.resize(1200, 900)
#     dashboard.setWindowTitle(
#             f"Corelec Monitor - {ADDRESS}"
#     )
#     dashboard.show()
#
#     t = threading.Thread(target=run_ble, args=(ADDRESS, state, database), daemon=True)
#     t.start()
#
#     sys.exit(app.exec())
#
#
# if __name__ == "__main__":
#     main()


import asyncio
import sys
import threading
import logging

from corelec.UI.qt_compat import QApplication

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.Acquisition import Acquisition
from corelec.UI.dashboard import Dashboard
from corelec.UI.signals import signals
from corelec.core_logging import setup_logging

ADDRESS = "B4:E3:F9:5A:0A:13"

logger = logging.getLogger(__name__)


# -----------------------------
# boucle BLE (auto restart)
# -----------------------------
def run_ble(stop_event: threading.Event, state: RegulatorState, db: Database, initial_retry: int = 0):
    
    retry_count = initial_retry
    
    while not stop_event.is_set():
        
        acq = Acquisition(
                ADDRESS,
                state,
                db,
                retry_count=retry_count
        )
        
        try:
            asyncio.run(acq.run())
        except Exception as e:
            logger.exception("BLE loop error: %s", e)
        
        retry_count += 1
        
        # petit délai pour éviter spam reconnect
        if not stop_event.is_set():
            asyncio.run(asyncio.sleep(1))


# -----------------------------
# main UI
# -----------------------------
def main():
    setup_logging("INFO")
    
    app = QApplication(sys.argv)
    
    state = RegulatorState()
    db = Database()
    
    dashboard = Dashboard(state, db)
    dashboard.resize(1200, 900)
    dashboard.setWindowTitle(f"Corelec Monitor - {ADDRESS}")
    dashboard.show()
    
    stop_event = threading.Event()
    
    # -----------------------------
    # callbacks UI
    # -----------------------------
    def cancel():
        stop_event.set()
    
    def restart():
        # Stop the current BLE loop and start a fresh one.
        stop_event.set()
        
        new_stop = threading.Event()
        
        t = threading.Thread(
                target=run_ble,
                args=(new_stop, state, db),
                daemon=True
        )
        t.start()
    
    signals.cancel_requested.connect(cancel)
    signals.retry_requested.connect(restart)
    
    # -----------------------------
    # start initial BLE
    # -----------------------------
    t = threading.Thread(
            target=run_ble,
            args=(stop_event, state, db),
            daemon=True
    )
    t.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
