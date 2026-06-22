"""
commands.py — Constructeurs de trames de commande BLE Corelec/Akeron.

Toutes les trames de commande sont de 17 octets, format identique aux trames
de mesure : sync(0x2A) | type | payload(13 octets) | CRC | end(0x2A).

Les octets de payload non utilisés sont mis à 0xFF ("ne pas modifier"),
sauf indication contraire.

AVERTISSEMENT DE SÉCURITÉ :
    Le protocole BLE Corelec/Akeron ne requiert aucune authentification
    ni code PIN pour envoyer des commandes. Toute application BLE à portée
    peut modifier les consignes ou déclencher un boost. Confirmé par RE externe
    (guix77/esphome-akeron-salt-duo). L'envoi de commandes est donc à sécuriser
    côté application (UI, accès réseau).

Architecture :
    Séparation des responsabilités sur le modèle de ctypes_frames.py / types.py :

    · CmdFrame65/69/83  — déclarations ctypes BigEndianStructure : source unique
                          de vérité pour le format de chaque octet de la trame.
                          Toute modification du protocole se fait ici.

    · build_command_*   — logique métier : validation, plafonnement, instanciation
                          via _new_cmd/_seal ; aucune constante d offset codée en dur.

    · build_from_payload — dispatch par payload dict (bus / ZMQ).

Types de trames de commande :
    65 (A) — Électrolyse : production %, boost, volet
    83 (S) — Consigne pH
    69 (E) — Consigne Redox
"""
from __future__ import annotations

import ctypes
from ctypes import BigEndianStructure, c_uint8, c_uint16
from typing import Any

from bleak import BleakClient

from corelec.BLE.frame import crc

CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"

FRAME_MARKER       = 0x2A
CMD_FRAME_LEN      = 17
BOOST_DURATION_MAX = 480


class CmdFrame83(BigEndianStructure):
    """Trame de commande 83 — Consigne pH.
    bytes 2-3  ph_x100 : pH x100 big-endian  (735 -> 7.35)
    bytes 4-14 _rN     : réservés 0xFF
    """
    _pack_ = 1
    _fields_ = [
        ('sync',    c_uint8),
        ('typ',     c_uint8),
        ('ph_x100', c_uint16),
        ('_r4',     c_uint8), ('_r5',  c_uint8), ('_r6',  c_uint8),
        ('_r7',     c_uint8), ('_r8',  c_uint8), ('_r9',  c_uint8),
        ('_r10',    c_uint8), ('_r11', c_uint8), ('_r12', c_uint8),
        ('_r13',    c_uint8), ('_r14', c_uint8),
        ('crc',     c_uint8),
        ('end',     c_uint8),
    ]


class CmdFrame69(BigEndianStructure):
    """Trame de commande 69 — Consigne Redox.
    bytes 2-3  rdx  : Redox mV big-endian
    bytes 4-14 _rN  : réservés 0xFF
    """
    _pack_ = 1
    _fields_ = [
        ('sync',  c_uint8),
        ('typ',   c_uint8),
        ('rdx',   c_uint16),
        ('_r4',   c_uint8), ('_r5',  c_uint8), ('_r6',  c_uint8),
        ('_r7',   c_uint8), ('_r8',  c_uint8), ('_r9',  c_uint8),
        ('_r10',  c_uint8), ('_r11', c_uint8), ('_r12', c_uint8),
        ('_r13',  c_uint8), ('_r14', c_uint8),
        ('crc',   c_uint8),
        ('end',   c_uint8),
    ]


class CmdFrame65(BigEndianStructure):
    """Trame de commande 65 — Électrolyse / Boost / Volet.
    byte  2      elx_pct   : production %  (0xFF = inchangé)
    bytes 3-4    boost_min : durée boost minutes BE  (0=stop, 0xFFFF=inchangé)
    bytes 5-9    _rN       : réservés 0xFF
    byte  10     io_flags  : bit3=volet_force  (0xFF = inchangé)
    bytes 11-14  _rN       : réservés 0xFF
    """
    _pack_ = 1
    _fields_ = [
        ('sync',      c_uint8),
        ('typ',       c_uint8),
        ('elx_pct',   c_uint8),
        ('boost_min', c_uint16),
        ('_r5',  c_uint8), ('_r6',  c_uint8), ('_r7',  c_uint8),
        ('_r8',  c_uint8), ('_r9',  c_uint8),
        ('io_flags',  c_uint8),
        ('_r11', c_uint8), ('_r12', c_uint8), ('_r13', c_uint8), ('_r14', c_uint8),
        ('crc',       c_uint8),
        ('end',       c_uint8),
    ]


def _new_cmd(cmd_cls: type) -> BigEndianStructure:
    """Instancie une trame initialisée à 0xFF (reserved) avec sync positionné."""
    f = cmd_cls.from_buffer_copy(bytes([0xFF] * CMD_FRAME_LEN))
    f.sync = FRAME_MARKER
    return f


def _seal(f: BigEndianStructure) -> bytes:
    """CRC = XOR(bytes 0-14), end = 0x2A, retourne bytes."""
    f.crc = crc(bytes(f)[:15])
    f.end = FRAME_MARKER
    return bytes(f)


def build_command_ph_setpoint(consigne: float) -> bytes:
    f = _new_cmd(CmdFrame83)
    f.typ     = 83
    f.ph_x100 = round(consigne * 100)
    return _seal(f)


def build_command_redox_setpoint(setpoint_mv: float) -> bytes:
    f = _new_cmd(CmdFrame69)
    f.typ = 69
    f.rdx = round(setpoint_mv)
    return _seal(f)


def build_command_elx_production(percent: int) -> bytes:
    if not 0 <= percent <= 100:
        raise ValueError(f"percent hors plage [0, 100] : {percent}")
    f = _new_cmd(CmdFrame65)
    f.typ     = 65
    f.elx_pct = percent
    return _seal(f)


def build_command_boost_start(minutes: int) -> bytes:
    if minutes <= 0:
        raise ValueError(f"minutes doit etre > 0 : {minutes}")
    minutes = min(minutes, BOOST_DURATION_MAX)
    f = _new_cmd(CmdFrame65)
    f.typ       = 65
    f.boost_min = minutes
    return _seal(f)


def build_command_boost_stop() -> bytes:
    f = _new_cmd(CmdFrame65)
    f.typ       = 65
    f.boost_min = 0
    return _seal(f)


def build_command_cover_force(state: bool, current_a10: int) -> bytes:
    f = _new_cmd(CmdFrame65)
    f.typ      = 65
    mask       = 1 << 3
    f.io_flags = (current_a10 | mask) if state else (current_a10 & ~mask & 0xFF)
    return _seal(f)


async def send_command(client: BleakClient, frame: bytes) -> None:
    await client.write_gatt_char(CHAR_UUID, frame, response=True)


def build_from_payload(payload: dict[str, Any]) -> bytes | None:
    cmd_type = payload.get('type')
    try:
        if cmd_type == 'ph_setpoint':
            return build_command_ph_setpoint(float(payload['value']))
        if cmd_type == 'redox_setpoint':
            return build_command_redox_setpoint(float(payload['value']))
        if cmd_type == 'elx_production':
            return build_command_elx_production(int(payload['value']))
        if cmd_type == 'boost_start':
            return build_command_boost_start(int(payload['minutes']))
        if cmd_type == 'boost_stop':
            return build_command_boost_stop()
        if cmd_type == 'cover_force':
            return build_command_cover_force(bool(payload['state']), int(payload['a10']))
    except (KeyError, ValueError, TypeError) as exc:
        import logging
        logging.getLogger(__name__).error(
            "build_from_payload: parametres invalides pour '%s': %s", cmd_type, exc
        )
    return None
