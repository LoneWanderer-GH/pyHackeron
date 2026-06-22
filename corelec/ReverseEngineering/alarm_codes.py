"""
alarm_codes.py — Tables de texte pour les codes d'alarme et d'avertissement Corelec/Akeron.

Sources :
  - RE externe : guix77/esphome-akeron-salt-duo (akeron_protocol.h)
  - Documentations Corelec SMAC / AKE-SALT-DUO

Utilisation :
    from corelec.ReverseEngineering.alarm_codes import alarm_elx_text, alarm_rdx_text, warning_text

    # Trame 65 byte 12 nibble bas, ou Trame 77 byte 10 (code E affiché contrôleur)
    print(alarm_elx_text(7))  # "E.07 Défaut d'écoulement"

    # Trame 77 byte 11 nibble haut
    print(alarm_rdx_text(1))  # "E.10 Sonde pH : lecture hors plage"

    # Trame 77 byte 11 nibble bas
    print(warning_text(1))    # "W.01 Dérive pH détectée"
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Alarmes électrolyseur
# Frame 65 byte 12 (& 0x0F) et Frame 77 byte 10
# ---------------------------------------------------------------------------

_ELX_ALARM: dict[int, str] = {
    0:  "OK",
    1:  "E.01 Court-circuit électrode ou entartrée",
    2:  "E.02 Défaut sel ou température de l'eau",
    3:  "E.03 Électrode usée ou déconnectée",
    4:  "E.04 Court-circuit électrique",
    6:  "E.06 Surchauffe appareil",
    7:  "E.07 Défaut d'écoulement (pas de flux)",
}


def alarm_elx_text(code: int) -> str:
    """Texte pour le code d'alarme électrolyseur (0–15).

    Utilisé pour :
      - Frame 65 (Trame A) : byte 12 nibble bas (elx_fault_code & 0x0F)
      - Frame 77 (Trame M) : byte 10 full byte (alarme)
    """
    return _ELX_ALARM.get(code, f"E.?? Alarme inconnue ({code})")


# ---------------------------------------------------------------------------
# Alarmes régulateur (pH / Redox)
# Frame 77 byte 11 nibble haut
# ---------------------------------------------------------------------------

_RDX_ALARM: dict[int, str] = {
    0:  "OK",
    1:  "E.10 Sonde pH : lecture hors plage (< 5.2 ou > 9.5)",
    2:  "E.11 pH stagnant malgré les injections",
    3:  "E.13 pH en dessous du seuil d'alarme (< 6.0)",
    4:  "E.14 pH au-dessus du seuil d'alarme (> 9.0)",
    5:  "E.15 Correction pH inversée",
    6:  "E.18 Température de l'eau trop basse (< 12 °C)",
    7:  "E.19 Taux de sel trop bas (< 2.0 g/L)",
    8:  "E.20 Redox trop élevé (> 950 mV)",
    9:  "E.21 Redox bas (< 350 mV)",
    10: "E.22 Redox trop bas (< 250 mV)",
}


def alarm_rdx_text(code: int) -> str:
    """Texte pour le code d'alarme régulateur pH/Redox (nibble 0–15).

    Utilisé pour :
      - Frame 77 (Trame M) : byte 11 nibble haut (alarm_rdx = warning >> 4)

    Note : la correspondance nibble → E.xx est estimée d'après la documentation ;
    les codes E.12, E.16, E.17 sont absents de la liste connue.
    """
    return _RDX_ALARM.get(code, f"E.?? Alarme inconnue ({code})")


# ---------------------------------------------------------------------------
# Avertissements (non bloquants)
# Frame 77 byte 11 nibble bas
# ---------------------------------------------------------------------------

_WARNING: dict[int, str] = {
    0: "OK",
    1: "W.01 Dérive pH détectée",
    2: "W.02 Dérive Redox détectée",
    3: "W.03 Taux de sel bas",
    4: "W.04 Taux de sel élevé",
    5: "W.05 Température de l'eau basse",
}


def warning_text(code: int) -> str:
    """Texte pour le code d'avertissement (nibble 0–15).

    Utilisé pour :
      - Frame 77 (Trame M) : byte 11 nibble bas (warning & 0x0F)

    Les avertissements sont informatifs ; ils ne bloquent pas le fonctionnement.
    """
    return _WARNING.get(code, f"W.?? Avertissement inconnu ({code})")


# ---------------------------------------------------------------------------
# Helpers combinés
# ---------------------------------------------------------------------------

def is_any_alarm(alarme: int, alarm_rdx: int) -> bool:
    """True si au moins une alarme (ELX ou régulateur) est active."""
    return alarme != 0 or alarm_rdx != 0


def alarm_summary(alarme: int, alarm_rdx: int, warning: int) -> str:
    """Résumé compact pour logs / tooltip : liste les codes actifs."""
    parts: list[str] = []
    if alarme:
        parts.append(alarm_elx_text(alarme))
    if alarm_rdx:
        parts.append(alarm_rdx_text(alarm_rdx))
    if warning:
        parts.append(warning_text(warning))
    return " | ".join(parts) if parts else "OK"
