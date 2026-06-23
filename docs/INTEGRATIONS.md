# Intégrations

## Home Assistant / Jeedom via MQTT

Le topic `corelec/value` publie un message JSON par valeur à chaque mise à jour :

```json
{"name": "ph",                        "value": 7.12, "ts": "2026-06-21T10:30:00"}
{"name": "temp",                      "value": 26.5, "ts": "..."}
{"name": "current_electrolyse_percent","value": 75,  "ts": "..."}
```

Le topic `corelec/state` publie le snapshot complet `RegulatorState` (~toutes les 2 s),
utilisable directement comme entités MQTT JSON dans Home Assistant.

Pour brancher ZMQ sur un broker MQTT, utiliser un bridge Python simple qui s'abonne
à `corelec/#` et republié sur MQTT, ou un outil comme [zmq2mqtt](https://github.com/zeromq/zmq2mqtt).

---

## Serveur web (`web_server.py`)

Pont ZMQ → HTTP exposant un dashboard HTML et une API REST/SSE.
Conçu pour tourner sur un NAS Synology (DS415, DSM 7.x, Python 3.9).

```bash
python web_server.py --daemon-host 192.168.0.16 --http-port 8080
```

L'API `/api/state` retourne le snapshot JSON courant — consommable directement
par Homebridge, MagicMirror, scripts shell, ou n'importe quel client HTTP.

Voir [docs/NETWORK.md](NETWORK.md#api-http-web_serverpy) pour le détail des routes.

---

## MagicMirror² — `MMM-Corelec`

Plugin sans dépendance npm (http natif Node.js). Affiche les paramètres configurables
sur le miroir.

**Installation :**
```bash
cp -r integrations/magicmirror/MMM-Corelec ~/MagicMirror/modules/
# pas de npm install requis
```

**Configuration (`config/config.js`) :**
```javascript
{
  module: "MMM-Corelec",
  position: "top_right",
  header: "🏊 Piscine",
  config: {
    webServerUrl: "http://192.168.0.20:8080",
    pollInterval: 30,
    fields: ["ph", "temp", "electrolyse_pct", "boost"],
    // Champs disponibles : ph, ph_consigne, temp, redox, redox_consigne,
    //                      electrolyse_pct, boost, connection
  }
}
```

Voir [integrations/magicmirror/MMM-Corelec/README.md](../integrations/magicmirror/MMM-Corelec/README.md).

---

## Homebridge / HomeKit — `homebridge-corelec`

Plugin sans dépendance npm. Expose dans HomeKit :

| Service HomeKit      | Nom              | Valeur                                      |
|----------------------|------------------|---------------------------------------------|
| `ContactSensor`      | Connexion BLE    | Contact = connecté / Ouvert = déconnecté    |
| `TemperatureSensor`  | pH               | Valeur pH (ex : 7.12 affiché comme 7.12 °C) |
| `TemperatureSensor`  | Température eau  | °C                                          |
| `Fanv2`              | Électrolyse      | vitesse rotation = % production             |
| `Switch`             | Boost            | ON/OFF → démarre/arrête le boost            |

**Installation :**
```bash
# Installer depuis le chemin local (npm enregistre le plugin dans son index)
cd /var/lib/homebridge       # ou ~/.homebridge selon l'installation
npm install --save /path/to/pyHackeron/integrations/homebridge/homebridge-corelec
sudo hb-service restart

# Un simple cp ne suffit pas : Homebridge ignore les dossiers non enregistrés par npm.
```

**Configuration (`~/.homebridge/config.json`) :**
```json
{
  "accessories": [{
    "accessory":    "CoreLecPool",
    "name":         "Piscine",
    "webServerUrl": "http://192.168.0.20:8080",
    "pollInterval": 30,
    "boostMinutes": 120
  }]
}
```

Voir [integrations/homebridge/homebridge-corelec/README.md](../integrations/homebridge/homebridge-corelec/README.md).

---

## ESP32 — passerelle MQTT autonome

Firmware NimBLE + MQTT — ne nécessite ni Raspberry Pi ni PC.
Topics publiés : `corelec/ph`, `corelec/temp`, `corelec/boost_remaining_min`, etc.

Voir [esp32/README.md](../esp32/README.md).
