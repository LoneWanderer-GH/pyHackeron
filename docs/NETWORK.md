# Protocole réseau ZeroMQ

Transport : **ZMQ PUB/SUB** (daemon → clients) + **ZMQ PUSH/PULL** (clients → daemon).  
Sérialisation : **JSON UTF-8** — lisible depuis n'importe quel langage.

---

## Ports par défaut

| Port | Usage                                |
|------|--------------------------------------|
| 5555 | ZMQ PUB — daemon publie les données  |
| 5556 | ZMQ PULL — daemon reçoit commandes   |

Configurables via `--pub-port` / `--cmd-port` ou variables d'environnement
`CORELEC_PUB_PORT` / `CORELEC_CMD_PORT`.

---

## Topics (stables — compatibles MQTT / Home Assistant / Jeedom)

| Topic                   | Direction        | Description                                   |
|-------------------------|------------------|-----------------------------------------------|
| `corelec/connection`    | daemon → clients | Statut BLE, métriques (RSSI, paquets, uptime) |
| `corelec/frame/raw`     | daemon → clients | Trame brute hex pour rétro-ingénierie         |
| `corelec/state`         | daemon → clients | Snapshot complet RegulatorState (~toutes 2 s) |
| `corelec/value`         | daemon → clients | Une valeur décodée `{name, value, ts}`        |
| `corelec/db/sync`       | daemon → clients | Chunk export SQLite (réponse à CMD_DB_SYNC)   |
| `corelec/cmd/retry`     | clients → daemon | Demande de reconnexion BLE                    |
| `corelec/cmd/cancel`    | clients → daemon | Arrêt de la connexion                         |
| `corelec/cmd/db_sync`   | clients → daemon | Demande d'export SQLite                       |
| `corelec/cmd/ble_command` | clients → daemon | Commande GATT (boost, pH, élx…)             |

---

## Codes statut connexion (`corelec/connection`)

| Code | Nom           |
|------|---------------|
| 0    | disconnected  |
| 1    | connecting    |
| 2    | connected     |
| 3    | error         |

---

## Exemples de payloads JSON

### `corelec/connection`
```json
{
  "status": 2, "status_name": "connected", "message": "Connected",
  "retry_count": 0,
  "metrics": { "rssi": -62, "packets_received": 1240, "frames_parsed": 410, "uptime_s": 3600 }
}
```

### `corelec/frame/raw`
```json
{ "frame_type": 77, "hex": "2a4d07101a02a40000002300000000000023002a", "ts": "2026-06-21T10:30:00" }
```

### `corelec/value`
```json
{ "name": "ph", "value": 7.12, "ts": "2026-06-21T10:30:00" }
```

### `corelec/cmd/ble_command` — exemples
```json
{ "type": "boost_start", "minutes": 120 }
{ "type": "boost_stop" }
{ "type": "elx_production", "value": 80 }
{ "type": "ph_setpoint",   "value": 7.3 }
```

---

## API HTTP (`web_server.py`)

Le serveur web expose une API REST+SSE consommable par n'importe quel client HTTP.

| Méthode | Route           | Description                                              |
|---------|-----------------|----------------------------------------------------------|
| GET     | `/`             | Dashboard HTML                                            |
| GET     | `/api/state`    | Snapshot JSON de l'état courant                          |
| GET     | `/api/stream`   | Server-Sent Events — push état en temps réel             |
| POST    | `/api/cmd`      | Commande vers le daemon (même payload que `corelec/cmd`) |
| POST    | `/api/retry`    | Demande reconnexion BLE                                  |
