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

Utilisation :
    from corelec.BLE.commands import build_command_boost_start, send_command
    frame = build_command_boost_start(120)   # boost 2h
    # via Acquisition :
    await send_command(client, frame)

Types de trames de commande :
    65 (A) — Électrolyse : production %, boost, volet
    83 (S) — Consigne pH
    69 (E) — Consigne Redox
"""
from __future__ import annotations

from typing import Any

from bleak import BleakClient

from corelec.BLE.frame import crc

# UUID de la caractéristique GATT (identique pour lecture et écriture)
CHAR_UUID = "e7add780-b042-4876-aae1-112855353cc1"

FRAME_MARKER = 0x2A
CMD_FRAME_LEN = 17
BOOST_DURATION_MAX = 480   # 8 heures — cap de sécurité (sanity cap)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _base_frame(frame_type: int) -> bytearray:
    """Crée une trame initialisée avec 0xFF pour les bytes payload."""
    buf = bytearray([0xFF] * CMD_FRAME_LEN)
    buf[0] = FRAME_MARKER
    buf[1] = frame_type
    buf[16] = FRAME_MARKER
    return buf


def _seal(buf: bytearray) -> bytes:
    """Calcule et insère le CRC (XOR bytes 0–14) puis retourne bytes."""
    buf[15] = crc(buf[:15])
    return bytes(buf)


# ---------------------------------------------------------------------------
# Commandes trame 83 (S) — Consigne pH
# ---------------------------------------------------------------------------

def build_command_ph_setpoint(consigne: float) -> bytes:
    """Trame de commande : consigne pH.

    Args:
        consigne: valeur cible ex. 7.35. Encodée ×100 en big-endian bytes[2..3].
                  Plage recommandée : 6.5–8.0.

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.
    """
    buf = _base_frame(83)
    val = round(consigne * 100)
    buf[2] = (val >> 8) & 0xFF
    buf[3] = val & 0xFF
    return _seal(buf)


# ---------------------------------------------------------------------------
# Commandes trame 69 (E) — Consigne Redox
# ---------------------------------------------------------------------------

def build_command_redox_setpoint(setpoint_mv: float) -> bytes:
    """Trame de commande : consigne Redox.

    Args:
        setpoint_mv: valeur cible en mV ex. 750. Encodée en big-endian bytes[2..3].
                     Plage recommandée : 400–1100 mV.

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.
    """
    buf = _base_frame(69)
    val = round(setpoint_mv)
    buf[2] = (val >> 8) & 0xFF
    buf[3] = val & 0xFF
    return _seal(buf)


# ---------------------------------------------------------------------------
# Commandes trame 65 (A) — Électrolyse, Boost, Volet
# ---------------------------------------------------------------------------

def build_command_elx_production(percent: int) -> bytes:
    """Trame de commande : taux de production d'électrolyse.

    Args:
        percent: 0–100 (multiple de 10 recommandé selon appareil).
                 Encodé directement dans byte[2].

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.
    """
    if not 0 <= percent <= 100:
        raise ValueError(f"percent hors plage [0, 100] : {percent}")
    buf = _base_frame(65)
    buf[2] = percent & 0xFF
    return _seal(buf)


def build_command_boost_start(minutes: int) -> bytes:
    """Trame de commande : démarrage du boost électrolyse.

    Args:
        minutes: durée du boost en minutes. Plafonné à BOOST_DURATION_MAX (480 min = 8h).
                 Encodé en big-endian bytes[3..4].

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.

    Raises:
        ValueError: si minutes <= 0.
    """
    if minutes <= 0:
        raise ValueError(f"minutes doit être > 0 : {minutes}")
    minutes = min(minutes, BOOST_DURATION_MAX)
    buf = _base_frame(65)
    buf[3] = (minutes >> 8) & 0xFF
    buf[4] = minutes & 0xFF
    return _seal(buf)


def build_command_boost_stop() -> bytes:
    """Trame de commande : arrêt du boost électrolyse (remet bytes[3..4] à 0x0000).

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.
    """
    buf = _base_frame(65)
    buf[3] = 0x00
    buf[4] = 0x00
    return _seal(buf)


def build_command_cover_force(state: bool, current_a10: int) -> bytes:
    """Trame de commande : forçage du volet (cover).

    Bascule le bit 3 de byte[10] en préservant tous les autres bits.
    Il est impératif de passer la dernière valeur de io_flags reçue (byte 10
    de la dernière trame 65) pour ne pas écraser les autres bits.

    Args:
        state: True = activer le forçage, False = désactiver.
        current_a10: dernière valeur de io_flags (byte 10) reçue depuis l'appareil.

    Returns:
        17 octets prêts à écrire sur la caractéristique GATT.
    """
    buf = _base_frame(65)
    mask = 1 << 3   # bit3 = volet_force
    buf[10] = (current_a10 | mask) if state else (current_a10 & ~mask & 0xFF)
    return _seal(buf)


# ---------------------------------------------------------------------------
# Envoi effectif via BleakClient
# ---------------------------------------------------------------------------

async def send_command(client: BleakClient, frame: bytes) -> None:
    """Écrit une trame de commande sur la caractéristique GATT.

    Utilise write_gatt_char avec response=True pour garantir l'acquittement
    (ATT Write Request / Write Response), plus fiable qu'un Write Command
    sans réponse pour les commandes de consigne.

    Args:
        client: BleakClient connecté et actif.
        frame:  17 octets produits par l'un des build_command_* ci-dessus.

    Raises:
        BleakError: si la caractéristique n'est pas accessible ou si la
                    connexion est perdue.
    """
    await client.write_gatt_char(CHAR_UUID, frame, response=True)


# ---------------------------------------------------------------------------
# Dispatch par payload dict (bus / ZMQ)
# ---------------------------------------------------------------------------

def build_from_payload(payload: dict[str, Any]) -> bytes | None:
    """Construit une trame de commande à partir d'un payload dict.

    Format du payload :
        {'type': 'ph_setpoint',    'value': 7.35}
        {'type': 'redox_setpoint', 'value': 730}
        {'type': 'elx_production', 'value': 70}
        {'type': 'boost_start',    'minutes': 120}
        {'type': 'boost_stop'}
        {'type': 'cover_force',    'state': True, 'a10': 0x24}

    Returns:
        17 octets prêts à écrire, ou None si le type est inconnu / paramètres invalides.
    """
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
            "build_from_payload: paramètres invalides pour '%s': %s", cmd_type, exc
        )
    return None
