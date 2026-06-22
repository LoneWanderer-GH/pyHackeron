from __future__ import annotations
import asyncio
import time
from datetime import datetime
import logging

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.bluetooth import build_ask
from corelec.BLE.frame import Frame
from corelec.BLE.stream import StreamParser
from corelec.BLE.types import ConnectionInfo, ConnectionMetrics
from corelec.ReverseEngineering.decoder import Decoder
from corelec.core.bus import bus as signals  # bus pur Python, sans dépendance Qt

logger = logging.getLogger(__name__)

CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"

SEQ_MAIN = [77, 83, 65, 69]

# Délai sans réception de trame BLE avant de forcer une reconnexion.
# Le régulateur peut couper silencieusement les notifications GATT tout en
# maintenant la connexion TCP/BLE côté stack → Bleak reste is_connected=True
# mais plus aucun notify() n'est appelé. Ce watchdog détecte ce cas.
STALE_TIMEOUT_S = 60



# class Acquisition:
#
#     def __init__(
#             self,
#             address,
#             state,
#             database
#     ):
#         self.address = address
#         self.state = state
#         self.database = database
#
#         self.parser = StreamParser()
#         self.decoder = Decoder()
#         self.stop_event = asyncio.Event()
#         self.client = None
#         self.task_poll = None
#         self.cancelled = False
#         self.restart_requested = False
#         # signals.retry_requested.connect(self.request_restart)
#         # signals.cancel_requested.connect(self.request_cancel)
#
#     def notify(self, _, data):
#
#         frames = self.parser.feed(data)
#
#         for raw in frames:
#
#             frame = Frame.parse(raw)
#
#             if not frame:
#                 continue
#
#             self.database.store_frame(frame)
#
#             decoded = self.decoder.decode(frame)
#             signals.log.emit(f"RX frame {frame.type}")
#             signals.reverse.emit({
#                 "type": frame.type,
#                 "raw": list(frame.raw),
#                 "decoded": decoded
#             })
#
#             self.database.store_decoded(decoded)
#
#             self.state.update(decoded)
#             signals.state_updated.emit()
#
#     async def send_seq(self, client):
#
#         for cmd in SEQ_MAIN:
#
#             pkt = build_ask(cmd)
#
#             await client.write_gatt_char(
#                     CHAR_UUID,
#                     pkt,
#                     response=True
#             )
#
#             await asyncio.sleep(0.5)
#
#     async def poll_loop(self, client):
#
#         while True:
#
#             await self.send_seq(client)
#
#             await asyncio.sleep(2)
#
#     # # # async def run(self):
#     # # #
#     # # #     # async with BleakClient(
#     # # #     #     self.address,
#     # # #     #     timeout=120
#     # # #     # ) as client:
#     # # #     # try:
#     # # #     #
#     # # #     #     for i in range(121):
#     # # #     #
#     # # #     #         signals.connection.emit(
#     # # #     #             ConnectionInfo(
#     # # #     #                 state="connecting",
#     # # #     #                 message=f"Connexion {self.address}",
#     # # #     #                 progress=int(i / 120 * 100)
#     # # #     #             )
#     # # #     #         )
#     # # #     #
#     # # #     #         await asyncio.sleep(1)
#     # # #     #
#     # # #     #     async with BleakClient(
#     # # #     #         self.address,
#     # # #     #         timeout=120
#     # # #     #     ) as client:
#     # # #     #
#     # # #     #         signals.connection.emit(
#     # # #     #             ConnectionInfo(
#     # # #     #                 state="connected",
#     # # #     #                 message=f"{client.name} ({self.address})",
#     # # #     #                 progress=100
#     # # #     #             )
#     # # #     #         )
#     # # #     #         await client.start_notify(
#     # # #     #             CHAR_UUID,
#     # # #     #             self.notify
#     # # #     #         )
#     # # #     #
#     # # #     #         asyncio.create_task(
#     # # #     #             self.poll_loop(client)
#     # # #     #         )
#     # # #     #
#     # # #     #         while True:
#     # # #     #             await asyncio.sleep(60)
#     # # #     start = time.time()
#     # # #     connect_task = asyncio.create_task(
#     # # #         BleakClient(
#     # # #             self.address,
#     # # #             timeout=120
#     # # #         ).connect()
#     # # #     )
#     # # #
#     # # #     while not connect_task.done():
#     # # #
#     # # #         elapsed = time.time() - start
#     # # #
#     # # #         progress = min(
#     # # #             100,
#     # # #             int(elapsed / 120 * 100)
#     # # #         )
#     # # #
#     # # #         signals.connection.emit(...)
#     # # async def run(self):
#     # #     signals.cancel_requested.connect(lambda: self.stop_event.set())
#     # #     client = BleakClient(
#     # #             self.address,
#     # #             timeout=120
#     # #     )
#     # #
#     # #     try:
#     # #
#     # #         signals.connection.emit(
#     # #                 ConnectionInfo(
#     # #                         state="connecting",
#     # #                         message=f"Connexion à {self.address}",
#     # #                         progress=0
#     # #                 )
#     # #         )
#     # #
#     # #         start = time.time()
#     # #
#     # #         connect_task = asyncio.create_task(
#     # #                 client.connect()
#     # #         )
#     # #
#     # #         while not connect_task.done():
#     # #
#     # #             elapsed = time.time() - start
#     # #
#     # #             progress = min(
#     # #                     99,
#     # #                     int(elapsed / 120 * 100)
#     # #             )
#     # #
#     # #             signals.connection.emit(
#     # #                     ConnectionInfo(
#     # #                             state="connecting",
#     # #                             message=f"Connexion à {self.address}",
#     # #                             progress=progress
#     # #                     )
#     # #             )
#     # #
#     # #             await asyncio.sleep(0.2)
#     # #
#     # #         await connect_task
#     # #
#     # #         if not client.is_connected:
#     # #
#     # #             raise RuntimeError("Connexion refusée")
#     # #
#     # #         signals.connection.emit(
#     # #                 ConnectionInfo(
#     # #                         state="connected",
#     # #                         message=f"{client.address}",
#     # #                         progress=100
#     # #                 )
#     # #         )
#     # #
#     # #         signals.log.emit(
#     # #                 f"Connecté à {client.address}"
#     # #         )
#     # #
#     # #         await client.start_notify(
#     # #                 CHAR_UUID,
#     # #                 self.notify
#     # #         )
#     # #
#     # #         asyncio.create_task(
#     # #                 self.poll_loop(client)
#     # #         )
#     # #
#     # #         while True:
#     # #             await asyncio.sleep(60)
#     # #
#     # #     except Exception as ex:
#     # #
#     # #         signals.connection.emit(
#     # #                 ConnectionInfo(
#     # #                         state="error",
#     # #                         message=str(ex),
#     # #                         progress=0
#     # #                 )
#     # #         )
#     # #
#     # #         signals.error.emit(str(ex))
#     # #
#     # #     finally:
#     # #
#     # #         try:
#     # #             if client.is_connected:
#     # #                 await client.disconnect()
#     # #         except:
#     # #             pass
#     # async def run(self):
#     #
#     #     while True:
#     #
#     #         self.stop_event.clear()
#     #
#     #         try:
#     #             self.client = BleakClient(self.address, timeout=120)
#     #
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="connecting",
#     #                 message=f"Connexion {self.address}",
#     #                 progress=0
#     #             ))
#     #
#     #             await self.client.connect()
#     #
#     #             if not self.client.is_connected:
#     #                 raise RuntimeError("Connexion échouée")
#     #
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="connected",
#     #                 message=f"{self.address}",
#     #                 progress=100
#     #             ))
#     #
#     #             await self.client.start_notify(CHAR_UUID, self.notify)
#     #
#     #             self.task_poll = asyncio.create_task(self.poll_loop(self.client))
#     #
#     #             # boucle principale contrôlée
#     #             while not self.stop_event.is_set():
#     #                 await asyncio.sleep(0.5)
#     #
#     #             # arrêt propre
#     #             self.task_poll.cancel()
#     #
#     #             try:
#     #                 await self.client.disconnect()
#     #             except:
#     #                 pass
#     #
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="disconnected",
#     #                 message="Déconnecté",
#     #                 progress=0
#     #             ))
#     #
#     #         except Exception as e:
#     #
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="error",
#     #                 message=str(e),
#     #                 progress=0
#     #             ))
#     #
#     #             await asyncio.sleep(2)
#
#     # def request_cancel(self):
#     #     self.cancelled = True
#     #     self.stop_event.set()
#     #
#     # def request_restart(self):
#     #     self.cancelled = False
#     #     self.restart_requested = True
#     #     self.stop_event.set()
#     #
#
#     # async def run(self):
#     #     while True:
#     #         self.stop_event.clear()
#     #         self.restart_requested = False
#     #         try:
#     #             self.client = BleakClient(self.address, timeout=120)
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="connecting",
#     #                 message=f"Connexion {self.address}",
#     #                 progress=0
#     #             ))
#     #             await self.client.connect()
#     #             if not self.client.is_connected:
#     #                 raise RuntimeError("Connexion échouée")
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="connected",
#     #                 message=f"{self.address}",
#     #                 progress=100
#     #             ))
#     #             await self.client.start_notify(CHAR_UUID, self.notify)
#     #             self.task_poll = asyncio.create_task(self.poll_loop(self.client))
#     #             while not self.stop_event.is_set():
#     #                 await asyncio.sleep(0.5)
#     #             # arrêt propre
#     #             self.task_poll.cancel()
#     #             try:
#     #                 await self.client.disconnect()
#     #             except:
#     #                 pass
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="disconnected",
#     #                 message="Déconnecté",
#     #                 progress=0
#     #             ))
#     #             # CAS IMPORTANT
#     #             if self.cancelled:
#     #                 break  # sortie totale
#     #             if not self.restart_requested:
#     #                 break  # sécurité
#     #         except Exception as e:
#     #             signals.connection.emit(ConnectionInfo(
#     #                 state="error",
#     #                 message=str(e),
#     #                 progress=0
#     #             ))
#     #
#     #             if self.cancelled:
#     #                 break
#     #
#     #             await asyncio.sleep(2)
#
#
#     async def run(self):
#
#         try:
#             self.client = BleakClient(self.address, timeout=120)
#
#             await self.client.connect()
#
#             if not self.client.is_connected:
#                 raise RuntimeError("Connexion échouée")
#
#             await self.client.start_notify(CHAR_UUID, self.notify)
#
#             self.task_poll = asyncio.create_task(self.poll_loop(self.client))
#
#             while not self.stop_event.is_set():
#                 await asyncio.sleep(0.5)
#
#         finally:
#             try:
#                 if self.task_poll:
#                     self.task_poll.cancel()
#             except:
#                 pass
#
#             try:
#                 if self.client and self.client.is_connected:
#                     await self.client.disconnect()
#             except:
#                 pass


class Acquisition:

    def __init__(self, address:str, state: RegulatorState, database: Database, retry_count:int=0):
        self.address = address
        self.state: RegulatorState = state
        self.database: Database = database
        self.retry_count = retry_count

        self.parser = StreamParser()
        self.decoder = Decoder()

        self.stop_event = asyncio.Event()
        self.client :BleakClient | None= None
        self.task_poll = None
        
        self.metrics = ConnectionMetrics()
        self.connection_start_time = None
        self.last_frame_at: float = 0.0   # time.monotonic() du dernier notify() valide

        signals.retry_requested.connect(self.request_restart)
        signals.cancel_requested.connect(self.request_cancel)
        self.connection_time_out_s = 120

    def request_cancel(self):
        self.stop_event.set()

    def request_restart(self):
        self.stop_event.set()

    def notify(self, _ :BleakGATTCharacteristic, data: bytearray):
        self.metrics.packets_received += 1

        frames = self.parser.feed(data)

        logger.debug("RAW: %s", data.hex())
        logger.debug("FRAMES: %s", len(frames))
        
        for i, raw in enumerate(frames):
            logger.debug("FRAME %s: %s", i, raw.hex() if frames else None)
            frame = Frame.parse(raw)
            if not frame:
                continue

            self.metrics.frames_parsed += 1
            self.database.store_frame(frame)

            decoded = self.decoder.decode(frame)

            self.database.store_decoded(decoded)

            self.state.update(decoded)
            signals.state_updated.emit()

            # signals.reverse.emit({
            #     "type": frame.type,
            #     "raw": list(frame.raw),
            #     "decoded": decoded
            # })
            signals.reverse.emit(decoded)

    async def send_seq(self, client:BleakClient):

        for cmd in SEQ_MAIN:
            pkt = build_ask(cmd)

            await client.write_gatt_char(
                CHAR_UUID,
                pkt,
                response=True
            )
            self.metrics.packets_sent += 1
            
            await asyncio.sleep(0.5)

    async def update_metrics(self, client:BleakClient):
        """Periodically update connection metrics (RSSI, MTU, uptime)."""
        try:
            if self.connection_start_time:
                self.metrics.connection_uptime_s = time.monotonic() - self.connection_start_time
            
            # Try to get RSSI (signal strength)
            try:
                rssi = None
                if hasattr(client, "rssi"):
                    rssi = getattr(client, "rssi")
                elif hasattr(client, "get_rssi"):
                    getter = getattr(client, "get_rssi")
                    if callable(getter):
                        rssi = await getter()
                elif hasattr(client, "_device") and hasattr(client._device, "rssi"):
                    rssi = client._device.rssi
                if rssi is not None:
                    self.metrics.rssi = int(rssi)
            except Exception:
                pass  # RSSI not always available
            
            # Try to get MTU
            try:
                mtu = getattr(client, "mtu_size", None)
                if mtu is None:
                    mtu = getattr(client, "mtu", None)
                if mtu:
                    self.metrics.mtu_size = mtu
            except Exception:
                pass
            
            self.metrics.last_update = datetime.now().isoformat()
        except Exception as e:
            logger.warning("Error updating metrics: %s", e)

    async def poll_loop(self, client:BleakClient):

        while not self.stop_event.is_set():
            await self.send_seq(client)
            await asyncio.sleep(2)

    async def run(self):

        self.stop_event.clear()
        elapsed = 0
        try:
            self.client = BleakClient(self.address, timeout=self.connection_time_out_s)
            assert(self.client is not None)
            signals.connection.emit(ConnectionInfo(
                state="connecting",
                message=f"Connexion {self.address} (120 sec left)",
                elapsed=0,
                remaining=self.connection_time_out_s,
                timeout=self.connection_time_out_s,
                retry_count=self.retry_count,
                metrics=self.metrics,
            ))

            start = time.monotonic()
            connect_task = asyncio.create_task(self.client.connect())

            while not connect_task.done():
                elapsed = time.monotonic() - start
                signals.connection.emit(ConnectionInfo(
                    state="connecting",
                    message=f"Connexion {self.address} ({int(elapsed)}s)",
                    elapsed=int(elapsed),
                    remaining=max(0, int(self.connection_time_out_s - elapsed)),
                    timeout=self.connection_time_out_s,
                    retry_count=self.retry_count,
                    metrics=self.metrics,
                ))
                await asyncio.sleep(0.2)

            await connect_task
            elapsed = time.monotonic() - start

            if not self.client.is_connected:
                raise RuntimeError("Connexion échouée")

            self.connection_start_time = time.monotonic()
            self.last_frame_at = time.monotonic()  # grace period : watchdog à partir d'ici
            self.metrics = ConnectionMetrics()

            device_name = getattr(self.client, "name", None) or ""
            conn_msg = f"{device_name}  {self.address}".strip() if device_name else self.address

            signals.connection.emit(ConnectionInfo(
                state="connected",
                message=conn_msg,
                elapsed=int(elapsed),
                remaining=max(0, int(self.connection_time_out_s - elapsed)),
                timeout=self.connection_time_out_s,
                retry_count=self.retry_count,
                metrics=self.metrics,
            ))

            await self.client.start_notify(CHAR_UUID, self.notify)

            self.task_poll = asyncio.create_task(self.poll_loop(self.client))

            while not self.stop_event.is_set():
                await self.update_metrics(self.client)
                # Watchdog silence BLE : si plus aucune notification GATT depuis STALE_TIMEOUT_S,
                # le régulateur a probablement coupé silencieusement la connexion.
                if self.last_frame_at > 0:
                    silence = time.monotonic() - self.last_frame_at
                    if silence > STALE_TIMEOUT_S:
                        logger.warning(
                            "Silence BLE depuis %.0fs (> %ds) — reconnexion forcée",
                            silence, STALE_TIMEOUT_S,
                        )
                        signals.connection.emit(ConnectionInfo(
                            state="error",
                            message=f"Silence BLE {silence:.0f}s — reconnexion forcée",
                            elapsed=int(time.monotonic() - self.connection_start_time),
                            remaining=0,
                            timeout=self.connection_time_out_s,
                            retry_count=self.retry_count,
                            metrics=self.metrics,
                        ))
                        self.stop_event.set()
                await asyncio.sleep(0.5)

        except Exception as e:

            signals.connection.emit(ConnectionInfo(
                state="error",
                message=str(e),
                elapsed=int(elapsed),
                remaining=int(self.connection_time_out_s - elapsed),
                timeout=self.connection_time_out_s,
                retry_count=self.retry_count,
                metrics=self.metrics,
            ))

        finally:
            try:
                if self.task_poll:
                    self.task_poll.cancel()
            except:
                pass
        
            try:
                if self.client and self.client.is_connected:
                    await self.client.disconnect()
            except:
                pass
        
            # IMPORTANT : attend relance naturelle
            await asyncio.sleep(1)