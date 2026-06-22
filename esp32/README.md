# Corelec ESP32

Client BLE NimBLE + passerelle MQTT pour le régulateur de piscine Corelec.

## Prérequis

- [ESP-IDF ≥ 5.1](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- ESP32 avec contrôleur BLE (ESP32 classique, ESP32-S3…)
- Broker MQTT accessible depuis le réseau WiFi

## Configuration

```
idf.py menuconfig
```

Sous **Corelec configuration** :

| Paramètre | Description | Exemple |
|---|---|---|
| `CORELEC_WIFI_SSID` | SSID WiFi | `MonWifi` |
| `CORELEC_WIFI_PASSWORD` | Mot de passe WiFi | `motdepasse` |
| `CORELEC_MQTT_BROKER_URL` | URL broker MQTT | `mqtt://192.168.1.100` |
| `CORELEC_BLE_DEVICE_ADDR` | Adresse MAC BLE du régulateur | `AA:BB:CC:DD:EE:FF` |

## Compilation et flash

```bash
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## Topics MQTT publiés

Préfixe `corelec/`, QoS 0, retained.

| Topic | Type | Description |
|---|---|---|
| `corelec/connection` | string | `connected` / `disconnected` |
| `corelec/ph` | float | pH (frame 77) |
| `corelec/redox` | int | mV Redox (frame 77) |
| `corelec/temp` | float | Température °C (frame 77) |
| `corelec/sel` | float | Salinité g/L (frame 77) |
| `corelec/alarme` | uint | Code alarme |
| `corelec/warning` | uint | Code warning |
| `corelec/pompe_moins_active` | 0/1 | Pompe pH- active |
| `corelec/regulation_active` | 0/1 | Régulation en cours |
| `corelec/flow_switch` | 0/1 | Flux eau détecté |
| `corelec/boost_remaining_min` | int | Durée boost restante (min) |
| `corelec/current_electrolyse_percent` | uint | % électrolyse |
| `corelec/ph_consigne` | float | Consigne pH (frame 83) |
| `corelec/redox_consigne` | int | Consigne Redox (frame 69) |
| `corelec/elx_fault_code` | uint | Code défaut électrolyseur |

## Protocole BLE

- **UUID caractéristique** : `e7add780-b042-4876-aae1-112855353cc1`
- **Trame réponse** : 17 octets, `[0]=0x2A, [1]=type, [2-14]=payload, [15]=CRC XOR(0-14), [16]=0x2A`
- **Paquet ASK** : `[0x2A, 0x52, 0x3F, cmd, XOR(0-3), 0x2A]`
- **Séquence de polling** : cmd 77, 83, 65, 69 toutes les 2 s (500 ms entre chaque)
- **Timeout inactivité** : 60 s sans notification → reconnexion automatique

## Structure du code

```
main/
├── main.c                WiFi + init séquentiel
├── corelec_types.h       Types partagés (frame + décodé)
├── corelec_protocol.c/h  CRC, parse_frame, build_ask, StreamParser
├── corelec_decoder.c/h   Décodage trames 65/69/77/83
├── corelec_ble.c/h       Client GATT NimBLE (scan→connect→notify→poll)
└── corelec_mqtt.c/h      Publication MQTT des valeurs décodées
```
