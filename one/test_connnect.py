import asyncio
from bleak import BleakClient
from ctypes import Structure, c_uint8, c_uint16, LittleEndianStructure

serviceUUID_SERVICE_ONE_UUID = 'FBDE0100-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONE_PARAMETRAGE_FILTRATION_UUID = 'FBDE0102-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONE_PARAMETRAGE_ECLAIRAGE_UUID = 'FBDE0103-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONE_CONTROLE_UUID = 'FBDE0101-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONE_STATUS_UUID = 'FBDE0104-4C7B-4E67-8292-A9B8E686CF87'
serviceUUID_SERVICE_ONEVS2K2_UUID = 'FBDE0600-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS2K2_PARAMETRAGE_FILTRATION_UUID = 'FBDE0602-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS2K2_STATUS_UUID = 'FBDE0603-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS2K2_CONTROLE_UUID = 'FBDE0601-4C7B-4E67-8292-A9B8E686CF87'

serviceUUID_SERVICE_TLC3ONE_UUID = 'FBDE0500-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_TLC3ONE_PARAMETRAGE_UUID = 'FBDE0502-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_TLC3ONE_CONTROLE_UUID = 'FBDE0501-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_TLC3ONE_STATUS_UUID = 'FBDE0503-4C7B-4E67-8292-A9B8E686CF87'


serviceUUID_SERVICE_ONEVS_UUID = 'FBDE0200-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS_CONTROLE_UUID = 'FBDE0201-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS_STATUS_UUID = 'FBDE0203-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEVS_PARAMETRAGE_FILTRATION_UUID = 'FBDE0202-4C7B-4E67-8292-A9B8E686CF87'


serviceUUID_SERVICE_ONECONNECT_UUID = 'FBDE0300-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_CONTROLEWIFI_UUID = 'FBDE0301-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_INSTALLATIONWIFI_UUID = 'FBDE0302-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_CONTROLEMQTTMAJCERT_UUID = 'FBDE0305-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_STATUTMQTTMAJCERT_UUID = 'FBDE0306-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_DATAFILE_UUID = 'FBDE0304-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_STATUTMQTT_UUID = 'FBDE0307-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONNECT_TABLEAURESEAUWIFI_UUID = 'FBDE0303-4C7B-4E67-8292-A9B8E686CF87'

descriptorUUID_SERVICE_USER_DESCRIPTOR = '2901'
ADVERTISING_SERVICE_UUID_ASSOCIATION = 'FBDE0100-4C7B-4E67-8292-A9B8E686CF87' # MQTT <-> BLE UUID transforms
ADVERTISING_SERVICE_UUID_USE = 'FBDE0000-4C7B-4E67-8292-A9B8E686CF87' # MQTT <-> BLE UUID transforms
serviceUUID_SERVICE_SYSTEM_UUID = 'FBDE0000-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_SYSTEM_SHAREDKEY_UUID = 'FBDE0002-4C7B-4E67-8292-A9B8E686CF87' # MQTT <-> BLE UUID transforms
caracteristicUUID_SERVICE_SYSTEM_ENCRYPTKEY_UUID = 'FBDE0003-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_SYSTEM_RANDOMKEY_UUID = 'FBDE0001-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_DEVICE_UUID = '180A'
caracteristicUUID_SERVICE_DEVICE_MODELNUMBER_UUID = '2A24'
caracteristicUUID_SERVICE_DEVICE_SERIALNUMBER_UUID = '2A25'
caracteristicUUID_SERVICE_DEVICE_FIRMWAREVERSION_UUID = '2A26'
serviceUUID_SERVICE_TIME_UUID = '2A27'
caracteristicUUID_SERVICE_TIME_DATETIME_UUID = '2A08'
caracteristicUUID_SERVICE_TIME_DAY_UUID = '2A09'
PRIVATE_KEY = '1141a80537444a6a85888d84115f2811'
SERVICE_OTA = '1D14D6EE-FD63-4FA1-BFA4-8F47B42119F0'
SERVICE_OTA_CONTROL = 'F7BF3564-FB6D-4E53-88A4-5E37E0326063'
SERVICE_OTA_DATA = '984227F3-34FC-4045-A5D0-2C581F81A153'

serviceUUID_SERVICE_ONESALT_UUID = 'FBDE0400-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONESALT_PARAMETRES_UUID = 'FBDE0403-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONESALT_INSTALLATION_UUID = 'FBDE0402-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONESALT_CONTROLE_UUID = 'FBDE0401-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONESALT_STATUS_UUID = 'FBDE0404-4C7B-4E67-8292-A9B8E686CF87'

serviceUUID_SERVICE_ONECONSTANCE_UUID = 'FBDE0800-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONSTANCE_FILLINGPARAMETERS_UUID = 'FBDE0801-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONSTANCE_GENERALSETTINGS_UUID = 'FBDE0804-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONSTANCE_DRAININGPARAMETERS_UUID = 'FBDE0802-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONSTANCE_CONTROL_UUID = 'FBDE0803-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONECONSTANCE_STATUS_UUID = 'FBDE0805-4C7B-4E67-8292-A9B8E686CF87'

serviceUUID_SERVICE_ONELIBRA_UUID = 'FBDE0700-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONELIBRA_LIQUIDPARAMETERS_UUID = 'FBDE0701-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONELIBRA_REGULATIONPARAMETERS_UUID = 'FBDE0702-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONELIBRA_GENERALSETTINGS_UUID = 'FBDE0704-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONELIBRA_INJECTIONCONTROL_UUID = 'FBDE0703-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONELIBRA_STATUS_UUID = 'FBDE0705-4C7B-4E67-8292-A9B8E686CF87'

serviceUUID_SERVICE_ONEREVOLUSEL_UUID = 'FBDE0900-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEREVOLUSEL_REGULATIONPARAMETER_UUID = 'FBDE0902-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEREVOLUSEL_EXTENSIONPARAMETER_UUID = 'FBDE0903-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEREVOLUSEL_GENERALSETTING_UUID = 'FBDE0904-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEREVOLUSEL_CONTROL_UUID = 'FBDE0901-4C7B-4E67-8292-A9B8E686CF87'
caracteristicUUID_SERVICE_ONEREVOLUSEL_STATUS_UUID = 'FBDE0905-4C7B-4E67-8292-A9B8E686CF87'

DAYS = [
    "lundi", "mardi", "mercredi", "jeudi",
    "vendredi", "samedi", "dimanche", "all"
]


# ---------------------------
# BITFIELD MODELS (ctypes)
# ---------------------------

class StatusRegister(LittleEndianStructure):
    _fields_ = [
        ("filtration_mode", c_uint8, 2),
        ("filtration_state", c_uint8, 1),
        ("eclairage_mode", c_uint8, 2),
        ("eclairage_state", c_uint8, 1),
        ("eclairage_type", c_uint8, 1),
        ("reserved", c_uint8, 1),
    ]


class ControlRegister(LittleEndianStructure):
    _fields_ = [
        ("filtration_mode", c_uint8, 2),
        ("eclairage_mode", c_uint8, 2),
        ("extra", c_uint8, 4),
    ]


# ---------------------------
# TIME ENCODING (48 slots)
# ---------------------------

SLOT = 1800
SLOTS = 48
DAY_SECONDS = 86400


def model_to_bitmap(intervals):
    bitmap = [0] * SLOTS

    for itv in intervals:
        start = itv["start"]
        end = itv["end"]

        if start >= end:
            end = DAY_SECONDS + end

        t = start
        while t < end:
            idx = (t // SLOT) % SLOTS
            bitmap[idx] = 1
            t += SLOT

    return bytes(bitmap)


def bitmap_to_model(data: bytes):
    bitmap = list(data)
    intervals = []

    start = None

    for i in range(SLOTS + 1):
        v = bitmap[i % SLOTS] if i < SLOTS else 0

        if v == 1 and start is None:
            start = i * SLOT

        if v == 0 and start is not None:
            end = i * SLOT
            intervals.append({"start": start, "end": end})
            start = None

    return intervals


# ---------------------------
# DEVICE MODEL
# ---------------------------

class DeviceModel:
    def __init__(self):
        self.status = StatusRegister()
        self.filtration = {d: {"horaires": []} for d in DAYS}
        self.eclairage = {d: {"horaires": []} for d in DAYS}
        self.filtration_mode = 0
        self.eclairage_mode = 0
        self.redem_eclairage = 0
        self.rupture = 0


# ---------------------------
# BLE CLIENT WRAPPER
# ---------------------------

class DeviceClient:
    def __init__(self, address: str):
        self.address = address
        self.model = DeviceModel()

    async def connect(self):
        self.client = BleakClient(self.address)
        await self.client.connect()

    async def disconnect(self):
        await self.client.disconnect()

    # -----------------------
    # STATUS PARSER
    # -----------------------

    def parse_status(self, data: bytearray):
        reg = StatusRegister.from_buffer_copy(data[:1])
        self.model.status = reg

    # -----------------------
    # RECEIVE DISPATCHER
    # -----------------------

    def on_notification(self, uuid, data: bytearray):

        if uuid == caracteristicUUID_SERVICE_ONE_STATUS_UUID:  # STATUS_UUID:
            self.parse_status(data)
            return

        if uuid == caracteristicUUID_SERVICE_ONE_PARAMETRAGE_FILTRATION_UUID:  # FILTRATION_UUID:
            mode = data[0] & 0x01
            redem = (data[0] >> 7) & 0x01

            day_idx = 0
            day = DAYS[day_idx]

            intervals = bitmap_to_model(bytes(data[1:]))

            self.model.filtration[day]["horaires"] = intervals
            self.model.filtration_mode = mode
            self.model.redem_eclairage = redem

        if uuid == caracteristicUUID_SERVICE_ONE_PARAMETRAGE_ECLAIRAGE_UUID:  # ECLAIRAGE_UUID:
            mode = data[0] & 0x01
            rupture = int.from_bytes(data[1:3], "little")

            day_idx = 0
            day = DAYS[day_idx]

            intervals = bitmap_to_model(data[3:])

            self.model.eclairage[day]["horaires"] = intervals
            self.model.eclairage_mode = mode
            self.model.rupture = rupture

    # -----------------------
    # WRITE CONTROL REGISTER
    # -----------------------

    def build_control(self):
        reg = ControlRegister()
        reg.filtration_mode = self.model.filtration_mode
        reg.eclairage_mode = self.model.eclairage_mode
        reg.extra = 0
        return bytes(reg)

    async def send_control(self):
        await self.client.write_gatt_char(
            caracteristicUUID_SERVICE_ONE_CONTROLE_UUID,  # CTRL_UUID,
            self.build_control(),
            response=False
        )

    # -----------------------
    # WRITE FILTRATION
    # -----------------------

    async def send_filtration(self, day_index=0):
        day = DAYS[day_index]
        intervals = self.model.filtration[day]["horaires"]

        payload = bytearray(1 + 48)
        payload[0] = (self.model.redem_eclairage << 7) | (
            self.model.filtration_mode & 0x01)
        payload[1:] = model_to_bitmap(intervals)

        await self.client.write_gatt_char(caracteristicUUID_SERVICE_ONE_PARAMETRAGE_FILTRATION_UUID, payload, False)

    # -----------------------
    # WRITE ECLAIRAGE
    # -----------------------

    async def send_eclairage(self, day_index=0):
        day = DAYS[day_index]
        intervals = self.model.eclairage[day]["horaires"]

        payload = bytearray(3 + 48)
        payload[0] = self.model.eclairage_mode & 0x01
        payload[1:3] = self.model.rupture.to_bytes(2, "little")
        payload[3:] = model_to_bitmap(intervals)

        await self.client.write_gatt_char(caracteristicUUID_SERVICE_ONE_PARAMETRAGE_ECLAIRAGE_UUID, payload, False)

    # -----------------------
    # SYNC
    # -----------------------

    async def sync(self):
        await self.client.start_notify(caracteristicUUID_SERVICE_ONE_STATUS_UUID, self.on_notification)
        status = await self.client.read_gatt_char(caracteristicUUID_SERVICE_ONE_STATUS_UUID)
        self.parse_status(status)
