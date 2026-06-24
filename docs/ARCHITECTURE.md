# Architecture

## Structure des fichiers

```
ble_daemon.py                   Démon headless (BLE → ZMQ + SQLite)
monitor.py                      Interface graphique Qt (BLE direct ou réseau)
web_server.py                   Serveur web HTTP/SSE (ZMQ → navigateur / intégrations)
raspi/
├── install_raspi.sh            Script d'installation automatique Pi3
├── corelec-daemon.service      Unité systemd
└── config.env.example          Modèle de configuration
corelec/
├── net_protocol.py             Protocole réseau (topics ZMQ, sérialisation JSON)
├── net_client.py               Client réseau ZMQ pour l'UI Qt
├── BLE/
│   ├── Acquisition.py          Boucle async BLE, séquence de polling
│   ├── bluetooth.py            Constructeur du paquet « ask »
│   ├── commands.py             Constructeurs de trames de commande (boost, pH, élx)
│   ├── frame.py                Parsing trame (sync=0x2A, CRC XOR, 17 octets)
│   ├── stream.py               Réassemblage flux BLE → trames complètes
│   └── types.py                Dataclasses Decoded65/69/77/83, ConnectionInfo…
├── Analyse/
│   ├── database.py             SQLite — stockage trames brutes
│   └── model.py                RegulatorState — snapshot courant du régulateur
├── ReverseEngineering/
│   ├── decoder.py              Décodeur des 4 types de trames (77/83/65/69)
│   └── ctypes_frames.py        Structures ctypes — source unique de vérité pour les offsets
├── UI/
│   ├── qt_compat.py            Couche de compatibilité Qt (PyQt5/6, PySide2/6)
│   ├── signals.py              Signaux Qt inter-couches
│   ├── dashboard.py            Dashboard principal (graphiques, métriques, logs)
│   └── reverse_ui.py           Panneau rétro-ingénierie (table bytes, tracé libre)
├── web/
│   └── templates/index.html   Dashboard web (HTML/CSS/JS pur, SSE)
├── core_logging.py             Logging coloré + redirection HTML vers l'UI Qt
├── requirements_daemon.txt     Pi3 headless (bleak + pyzmq)
├── requirements_raspi3.txt     Pi3 avec UI Qt (via apt)
├── requirements_windows.txt    Desktop (PyQt6 + pyzmq)
└── requirements_web.txt        Serveur web (flask + pyzmq)
ada/                            Bibliothèque Ada 2022 (voir ada/README.md)
esp32/                          Firmware ESP32 NimBLE + MQTT (voir esp32/README.md)
integrations/
├── magicmirror/MMM-Corelec/    Plugin MagicMirror²
└── homebridge/homebridge-corelec/  Plugin Homebridge / HomeKit
```

---

## Base de données SQLite

La table **`raw_frames`** est la seule source de vérité pour l'historique.
Les graphiques de l'UI la décodent à la volée ; les autres tables sont conservées pour compatibilité.

| Table             | Colonnes                              | Rôle                                      |
|-------------------|---------------------------------------|-------------------------------------------|
| `raw_frames`      | id, ts, frame_type, frame_hex         | Trames brutes reçues (hex 17 octets)      |
| `decoded_values`  | id, ts, name, value                   | Conservée pour compatibilité, non écrite  |
| `frame_bytes`     | id, ts, frame_type, byte_index, value | Conservée pour compatibilité, non écrite  |

Lors d'un **Sync DB**, seule `raw_frames` est transférée depuis le daemon vers l'UI.

---

## Flux de données

```
Régulateur BLE
    │  GATT notify (17 octets)
    ▼
Acquisition.py (bleak)
    │  Frame (raw bytearray)
    ├──► SQLite raw_frames        ← source de vérité
    ├──► Decoder → RegulatorState ← état temps réel
    └──► ZMQ PUB :5555
              │
    ┌─────────┴──────────────────┐
    ▼                            ▼
NetworkClient (UI Qt)      ZmqListener (web_server.py)
    │                            │
    ├── Dashboard Qt             ├── /api/stream  (SSE → navigateur)
    └── SQLite locale            ├── /api/state   (JSON REST)
                                 └── /api/cmd     (commandes → ZMQ PULL :5556)
```
