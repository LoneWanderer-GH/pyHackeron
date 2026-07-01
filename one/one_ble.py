"""
one_ble.py — Bibliothèque BLE Python 3 pour le module One (WA Conception)
==========================================================================

Gère :
  - scan des dispositifs One (mode utilisation ou mode appairage)
  - appairage (bouton sur le module + lecture shared_key + handshake AES)
  - connexion (reconnexion avec shared_key stockée)
  - lecture / notification du statut (pompe + éclairage)

Protocole extrait du code JS décompilé (Hermes/React Native).

Dépendances : bleak, pycryptodome (Crypto.Cipher.AES)
"""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from Crypto.Cipher import AES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UUIDs BLE
# ---------------------------------------------------------------------------

# -- Service système (auth, commun à tous les produits One) --
SVC_SYSTEM_UUID      = "fbde0000-4c7b-4e67-8292-a9b8e686cf87"
CHR_RANDOM_KEY_UUID  = "fbde0001-4c7b-4e67-8292-a9b8e686cf87"
CHR_SHARED_KEY_UUID  = "fbde0002-4c7b-4e67-8292-a9b8e686cf87"
CHR_ENCRYPT_KEY_UUID = "fbde0003-4c7b-4e67-8292-a9b8e686cf87"

# -- Service infos périphérique (GATT standard) --
SVC_DEVINFO_UUID     = "0000180a-0000-1000-8000-00805f9b34fb"
CHR_MODEL_UUID       = "00002a24-0000-1000-8000-00805f9b34fb"
CHR_SERIAL_UUID      = "00002a25-0000-1000-8000-00805f9b34fb"
CHR_FIRMWARE_UUID    = "00002a26-0000-1000-8000-00805f9b34fb"

# -- Service heure (GATT standard) --
SVC_TIME_UUID        = "00001805-0000-1000-8000-00805f9b34fb"
CHR_DATETIME_UUID    = "00002a08-0000-1000-8000-00805f9b34fb"
CHR_DAYOFWEEK_UUID   = "00002a09-0000-1000-8000-00805f9b34fb"

# -- Service One (pompe + éclairage) --
SVC_ONE_UUID         = "fbde0100-4c7b-4e67-8292-a9b8e686cf87"
CHR_CONTROLE_UUID    = "fbde0101-4c7b-4e67-8292-a9b8e686cf87"
CHR_FILTRATION_UUID  = "fbde0102-4c7b-4e67-8292-a9b8e686cf87"
CHR_ECLAIRAGE_UUID   = "fbde0103-4c7b-4e67-8292-a9b8e686cf87"
CHR_STATUS_UUID      = "fbde0104-4c7b-4e67-8292-a9b8e686cf87"

# UUID de service annoncé par le module selon son mode :
#   FBDE0100 → mode appairage (bouton pressé)
#   FBDE0000 → mode utilisation normale
ADV_UUID_PAIR = "fbde0100-4c7b-4e67-8292-a9b8e686cf87"
ADV_UUID_USE  = "fbde0000-4c7b-4e67-8292-a9b8e686cf87"

# Clé privée fixe (extraite du binaire JS)
PRIVATE_KEY = bytes.fromhex("1141a80537444a6a85888d84115f2811")

# ---------------------------------------------------------------------------
# Modèle de données
# ---------------------------------------------------------------------------

FILTRATION_MODES = {0: "Manuel", 1: "Horloge", 2: "Auto"}
ECLAIRAGE_MODES  = {0: "Manuel", 1: "Horloge", 2: "Auto"}


@dataclass
class OneStatus:
    """État instantané pompe + éclairage."""
    filtration_mode:  int = 0   # 0=Manuel 1=Horloge 2=Auto
    filtration_state: int = 0   # 0=arrêté 1=en marche
    eclairage_mode:   int = 0   # 0=Manuel 1=Horloge 2=Auto
    eclairage_state:  int = 0   # 0=éteint 1=allumé
    eclairage_type:   int = 0   # 0/1 selon type d'éclairage installé

    @classmethod
    def from_byte(cls, b: int) -> "OneStatus":
        return cls(
            filtration_mode  = b & 0x03,
            filtration_state = (b >> 2) & 0x01,
            eclairage_mode   = (b >> 3) & 0x03,
            eclairage_state  = (b >> 5) & 0x01,
            eclairage_type   = (b >> 6) & 0x01,
        )

    def as_dict(self) -> dict:
        return {
            "filtration_mode":       self.filtration_mode,
            "filtration_mode_label": FILTRATION_MODES.get(self.filtration_mode, "?"),
            "filtration_state":      self.filtration_state,
            "eclairage_mode":        self.eclairage_mode,
            "eclairage_mode_label":  ECLAIRAGE_MODES.get(self.eclairage_mode, "?"),
            "eclairage_state":       self.eclairage_state,
            "eclairage_type":        self.eclairage_type,
        }


@dataclass
class OnePairingResult:
    """Résultat d'un appairage réussi — à sauvegarder pour reconnexion future."""
    address:    str
    model:      str
    serial:     str
    firmware:   str
    shared_key: bytes   # 16 octets, à persister (hex ou b64)


# ---------------------------------------------------------------------------
# Helpers auth
# ---------------------------------------------------------------------------

def _aes_encrypt(shared_key: bytes, random_key: bytes) -> bytes:
    """Calcule la réponse au challenge d'authentification.

    Protocole :
      plaintext  = shared_key(16) + random_key(16)  → 32 octets
      ciphertext = AES-ECB(PRIVATE_KEY, plaintext)
      réponse    = reversed(ciphertext)
    """
    plaintext  = shared_key + random_key
    cipher     = AES.new(PRIVATE_KEY, AES.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)
    return bytes(reversed(ciphertext))


def _encode_datetime(dt: datetime) -> bytes:
    """Encode une datetime au format GATT Current Time (7 octets).

    struct: year(2LE), month(1), day(1), hour(1), minute(1), second(1)
    """
    return struct.pack(
        "<HBBBBBB",
        dt.year, dt.month, dt.day,
        dt.hour, dt.minute, dt.second,
        0,  # fractions256 — ignoré
    )


def _day_of_week_byte(dt: datetime) -> bytes:
    """1 = lundi … 7 = dimanche (GATT Day of Week)."""
    return bytes([dt.isoweekday()])


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class OneBLEClient:
    """Client BLE asynchrone pour le module One WA Conception.

    Cycle de vie normal :
        client = OneBLEClient(address, shared_key)
        await client.connect_and_auth()   # connexion + auth + sync RTC
        await client.subscribe_status(callback)
        status = await client.read_status()
        ...
        await client.disconnect()

    Pour un premier appairage (bouton sur le module) :
        device, result = await OneBLEClient.pair(address_or_ble_device)
        # sauvegarder result.shared_key.hex() pour reconnexion
    """

    def __init__(self, address: str, shared_key: bytes):
        self.address    = address
        self.shared_key = shared_key
        self._client: Optional[BleakClient] = None

    # ---------------------------------------------------------------- scan

    @staticmethod
    async def scan_for_use(timeout: float = 10.0) -> list[BLEDevice]:
        """Scan les modules One en mode utilisation normale (ADV_UUID_USE)."""
        found: list[BLEDevice] = []

        def _cb(device: BLEDevice, ad_data):
            uuids = [u.lower() for u in (ad_data.service_uuids or [])]
            if ADV_UUID_USE in uuids and device not in found:
                found.append(device)
                logger.debug("Trouvé (use): %s %s", device.address, device.name)

        async with BleakScanner(detection_callback=_cb) as scanner:
            await asyncio.sleep(timeout)

        return found

    @staticmethod
    async def scan_for_pairing(timeout: float = 30.0) -> list[BLEDevice]:
        """Scan les modules One en mode appairage (ADV_UUID_PAIR).

        Le bouton sur le module doit être pressé au préalable.
        """
        found: list[BLEDevice] = []

        def _cb(device: BLEDevice, ad_data):
            uuids = [u.lower() for u in (ad_data.service_uuids or [])]
            if ADV_UUID_PAIR in uuids and device not in found:
                found.append(device)
                logger.info("Module en mode appairage: %s %s", device.address, device.name)

        async with BleakScanner(detection_callback=_cb) as scanner:
            await asyncio.sleep(timeout)

        return found

    # ---------------------------------------------------------------- appairage

    @classmethod
    async def pair(cls, address: str) -> tuple["OneBLEClient", OnePairingResult]:
        """Appaire un module One vierge (ou réinitalisé).

        Pré-requis : le bouton d'appairage du module doit être pressé.

        Retourne le client authentifié + les données d'appairage
        (notamment shared_key à persister).
        """
        logger.info("Démarrage appairage avec %s", address)
        client = cls.__new__(cls)
        client.address = address
        client._client = BleakClient(address)
        await client._client.connect()
        logger.info("Connecté (appairage)")

        # 1. Identification
        model    = (await client._client.read_gatt_char(CHR_MODEL_UUID)).decode().strip("\x00")
        serial   = (await client._client.read_gatt_char(CHR_SERIAL_UUID)).decode().strip("\x00")
        firmware = (await client._client.read_gatt_char(CHR_FIRMWARE_UUID)).decode().strip("\x00")
        logger.info("Modèle=%s  Série=%s  FW=%s", model, serial, firmware)

        # 2. Lecture shared_key (inversé, 16 octets)
        raw_shared = await client._client.read_gatt_char(CHR_SHARED_KEY_UUID)
        shared_key = bytes(reversed(raw_shared[:16]))
        logger.info("Shared key: %s", shared_key.hex())
        client.shared_key = shared_key

        # 3. Authentification
        await client._authenticate()

        # 4. Synchronisation RTC
        await client._sync_rtc()

        result = OnePairingResult(
            address=address,
            model=model,
            serial=serial,
            firmware=firmware,
            shared_key=shared_key,
        )
        return client, result

    # ---------------------------------------------------------------- connexion normale

    async def connect_and_auth(self) -> None:
        """Connexion + authentification + sync RTC (module déjà appairé)."""
        logger.info("Connexion à %s", self.address)
        self._client = BleakClient(self.address)
        await self._client.connect()
        logger.info("Connecté")
        await self._authenticate()
        await self._sync_rtc()
        logger.info("Auth + RTC OK")

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    # ---------------------------------------------------------------- statut

    async def read_status(self) -> OneStatus:
        """Lit le statut courant (pompe + éclairage) en une seule lecture GATT."""
        data = await self._client.read_gatt_char(CHR_STATUS_UUID)
        status = OneStatus.from_byte(data[0])
        logger.debug("Status lu: %s", status)
        return status

    async def subscribe_status(self, callback: Callable[[OneStatus], None]) -> None:
        """S'abonne aux notifications de statut.

        callback(status: OneStatus) est appelé à chaque changement.
        """
        def _handler(_, data: bytearray):
            status = OneStatus.from_byte(data[0])
            logger.debug("Notification status: %s", status)
            callback(status)

        await self._client.start_notify(CHR_STATUS_UUID, _handler)
        logger.debug("Abonné aux notifications STATUS")

    async def unsubscribe_status(self) -> None:
        await self._client.stop_notify(CHR_STATUS_UUID)

    # ---------------------------------------------------------------- interne auth

    async def _authenticate(self) -> None:
        """Handshake AES d'autorisation.

        Séquence :
          1. read  CHR_RANDOM  → random_key (inversé)
          2. AES-ECB(PRIVATE_KEY, shared_key + random_key) inversé
          3. write CHR_ENCRYPT → réponse chiffrée
        """
        raw_random = await self._client.read_gatt_char(CHR_RANDOM_KEY_UUID)
        random_key = bytes(reversed(raw_random[:16]))
        logger.debug("Random key: %s", random_key.hex())

        response = _aes_encrypt(self.shared_key, random_key)
        logger.debug("Auth response: %s", response.hex())

        await self._client.write_gatt_char(CHR_ENCRYPT_KEY_UUID, response, response=True)
        logger.info("Authentification réussie")

    async def _sync_rtc(self) -> None:
        """Synchronise l'horloge du module avec l'heure locale."""
        now = datetime.now()
        try:
            await self._client.write_gatt_char(
                CHR_DATETIME_UUID, _encode_datetime(now), response=True
            )
            await self._client.write_gatt_char(
                CHR_DAYOFWEEK_UUID, _day_of_week_byte(now), response=True
            )
            logger.debug("RTC synchronisée: %s", now.isoformat())
        except Exception as e:
            # Non bloquant — certains firmwares ignorent l'écriture RTC
            logger.warning("Sync RTC ignorée: %s", e)
