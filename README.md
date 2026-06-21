# Corelec Monitor

Outil de supervision et de rétro-ingénierie d'un régulateur de piscine **Corelec** via BLE.  
Le régulateur communique en Bluetooth Low Energy ; ce projet intercepte, décode et affiche les données en temps réel, et permet d'explorer les trames inconnues.

---

## Architecture déployée

```
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│  Raspberry Pi 3 (headless)      │   ZMQ   │  PC / Mac / Linux (UI Qt)       │
│                                 │  PUB/   │                                 │
│  ble_daemon.py                  │◄──────► │  monitor.py --network <IP>      │
│  ├── BLE (bleak)                │  PUSH   │  ├── NetworkClient (ZMQ SUB)    │
│  ├── Decoder                    │         │  ├── Dashboard Qt               │
│  ├── SQLite (pool.db)           │         │  └── SQLite locale (optionnel)  │
│  └── ZMQ PUB :5555 CMD :5556   │         │                                 │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

Le PC peut aussi se connecter directement en BLE (mode direct, sans Pi) :
```
  monitor.py --address B4:E3:F9:5A:0A:13
```

---

## Structure des fichiers

```
ble_daemon.py                 Démon headless (BLE → ZMQ + SQLite)
monitor.py                    Interface graphique Qt (mode BLE direct ou réseau)
raspi/
├── install_raspi.sh          Script d'installation automatique sur Pi3
├── corelec-daemon.service    Unité systemd
└── config.env.example        Modèle de configuration
src/python/
├── net_protocol.py           Protocole réseau (topics ZMQ, sérialisation JSON)
├── net_client.py             Client réseau ZMQ pour l'UI
├── BLE/                      Acquisition BLE (bleak), parsing trames, types
│   ├── Acquisition.py        Boucle async BLE, séquence de polling
│   ├── bluetooth.py          Constructeur de paquet « ask »
│   ├── frame.py              Parsing trame (sync=42, CRC XOR, 17 octets)
│   ├── stream.py             Réassemblage flux BLE → trames complètes
│   └── types.py              Dataclasses Decoded65/69/77/83, ConnectionInfo…
├── Analyse/
│   ├── database.py           SQLite — stockage trames brutes + valeurs décodées
│   └── model.py              RegulatorState — état courant du régulateur
├── ReverseEngineering/
│   ├── decoder.py            Décodeur des 4 types de trames (77/83/65/69)
│   └── ctypes_frames.py      Structures ctypes pour la vue byte-par-byte de l'UI
├── UI/
│   ├── qt_compat.py          Couche de compatibilité Qt (PyQt5/6, PySide2/6)
│   ├── signals.py            Signaux Qt inter-couches
│   ├── dashboard.py          Dashboard principal (graphiques, métriques, logs)
│   └── reverse_ui.py         Panneau rétro-ingénierie (table bytes, tracé libre)
├── core_logging.py           Logging coloré + redirection HTML vers l'UI Qt
├── requirements_daemon.txt   Pi3 headless uniquement (bleak + pyzmq)
├── requirements_raspi3.txt   Pi3 avec UI Qt (via apt)
└── requirements_windows.txt  Desktop (PyQt6 + pyzmq)
└── Ada/                      Bibliothèque Ada 2022 (logique métier, API C)
```

---

## Protocole réseau ZeroMQ

Transport : **ZMQ PUB/SUB** (daemon → UI) + **ZMQ PUSH/PULL** (UI → daemon).  
Sérialisation : **JSON UTF-8** — lisible depuis n'importe quel langage/plateforme.

### Topics (stables — compatibles MQTT / Home Assistant / Jeedom)

| Topic                 | Direction     | Description                                 |
|-----------------------|---------------|---------------------------------------------|
| `corelec/connection`  | daemon → UI   | Statut BLE, métriques réseau                |
| `corelec/state`       | daemon → UI   | Snapshot complet du RegulatorState (~2 s)   |
| `corelec/value`       | daemon → UI   | Une valeur par message `{name, value, ts}`  |
| `corelec/frame/raw`   | daemon → UI   | Trame brute hex pour rétro-ingénierie       |
| `corelec/db/sync`     | daemon → UI   | Chunk d'export SQLite (réponse à cmd)       |
| `corelec/cmd/retry`   | UI → daemon   | Demande de reconnexion BLE                  |
| `corelec/cmd/cancel`  | UI → daemon   | Arrêt de la connexion                       |
| `corelec/cmd/db_sync` | UI → daemon   | Demande d'export SQLite                     |

### Ports par défaut

| Port | Usage                    |
|------|--------------------------|
| 5555 | ZMQ PUB (daemon publie)  |
| 5556 | ZMQ PULL (daemon écoute) |

### Codes statut connexion (`corelec/connection`)

| Code | Nom           |
|------|---------------|
| 0    | disconnected  |
| 1    | connecting    |
| 2    | connected     |
| 3    | error         |

---

## Protocole BLE

| Champ      | Octets | Description                              |
|------------|--------|------------------------------------------|
| Sync start | 0      | `0x2A` (42)                              |
| Type       | 1      | 77 / 83 / 65 / 69                        |
| Payload    | 2–14   | Données spécifiques au type              |
| CRC        | 15     | XOR des octets 0–14                      |
| Sync end   | 16     | `0x2A` (42)                              |

### Types de trames décodés

| Type | Contenu                                                              |
|------|----------------------------------------------------------------------|
| 77   | pH, Redox, Température, Sel, Alarmes, Pompe pH−, Pompe chl/élx      |
| 83   | Consigne pH, erreur max/min                                          |
| 65   | Électrolyse %, Boost, Cycle A/B, Flow switch, Volet                 |
| 69   | Consigne Redox                                                       |

---

## Fonctionnalités UI

### Dashboard
- Valeurs temps réel : pH, Redox, Température, Sel, Électrolyse
- État des commutateurs : Boost, Flow switch, Volet actif/forcé
- Métriques BLE : RSSI, paquets envoyés/reçus, uptime

### Graphiques
- **pH et consigne pH** — axe secondaire droit pour l'état de la pompe pH− (0/1)
- **Électrolyse % et consigne volet**
- **Cycles A / B**
- Curseur interactif (barre verticale + labels valeurs au survol)

### Rétro-ingénierie
- Table byte-par-byte pour chaque type de trame (65/69/77/83)
  - Coloration : vert = octet décodé connu, orange = inconnu
  - Clic droit sur une sélection : interprétation uint16, int16, float16, ASCII, bitmask
  - Case à cocher « Plot » pour tracer un octet ou une interprétation multi-octets
- Graphe libre — séries ajoutées manuellement, gestion dans le panneau de droite

### Logs
- Vue console avec coloration par niveau (DEBUG/INFO/WARNING/ERROR)

---

## Installation

### Raspberry Pi 3 — daemon headless (recommandé)

```bash
# Installation automatique (une seule commande)
sudo bash raspi/install_raspi.sh B4:E3:F9:5A:0A:13

# Ou manuellement :
pip install -r src/python/requirements_daemon.txt
python ble_daemon.py --address B4:E3:F9:5A:0A:13
```

> **Remarque PyQt5 / Pi3** : `pip install PyQt5` échoue sur Python 3.9 ARM  
> (`sipbuild.pyproject.PyProjectOptionException`).  
> Le daemon headless n'a **aucune dépendance Qt** — seuls `bleak` et `pyzmq` sont nécessaires.  
> Si l'UI est souhaitée sur le Pi, installer via apt :  
> ```bash
> sudo apt-get install python3-pyqt5 python3-pyqtgraph
> python3 -m venv --system-site-packages venv
> ```

### Windows / macOS / Linux — interface graphique

```powershell
python -m venv venv
venv\Scripts\Activate.ps1          # Windows
# source venv/bin/activate          # Linux/macOS
pip install -r src/python/requirements_windows.txt

# Mode réseau (Pi3 comme daemon)
python monitor.py --network 192.168.1.42

# Mode BLE direct (sans Pi3)
python monitor.py --address B4:E3:F9:5A:0A:13

# Avec sync DB au démarrage
python monitor.py --network 192.168.1.42 --sync-db
```

### Déploiement Pi3 — détails systemd

```bash
# Vérifier l'état du service
sudo systemctl status corelec-daemon

# Voir les logs en temps réel
sudo journalctl -fu corelec-daemon

# Modifier la configuration (adresse BLE, ports…)
sudo nano /etc/corelec/config.env
sudo systemctl restart corelec-daemon
```

---

## Intégration Home Assistant / Jeedom / Homebridge

Le topic `corelec/value` publie un message JSON par valeur à chaque mise à jour :

```json
{"name": "ph", "value": 7.12, "ts": "2026-06-21T10:30:00"}
{"name": "temp", "value": 26.5, "ts": "2026-06-21T10:30:00"}
{"name": "current_electrolyse_percent", "value": 75, "ts": "..."}
```

Pour intégrer dans Home Assistant via MQTT, brancher un bridge ZMQ→MQTT  
(ex : [zmq2mqtt](https://github.com/mqttjs/MQTT.js)) ou un script Python simple  
qui subscribe à `corelec/#` et publie sur le broker MQTT local.

Le topic `corelec/state` publie le snapshot complet du `RegulatorState` (~toutes les 2 s),  
utilisable directement comme entités MQTT JSON dans HA.

---

## Fonctionnalités UI

### Dashboard
- Valeurs temps réel : pH, Redox, Température, Sel, Électrolyse
- État des commutateurs : Boost, Flow switch, Volet actif/forcé
- Métriques BLE : RSSI, paquets envoyés/reçus, uptime
- Bouton **Sync DB** (mode réseau) — télécharge la base distante

### Graphiques
- **pH et consigne pH** — axe secondaire droit pour l'état de la pompe pH− (0/1)
- **Électrolyse % et consigne volet**
- **Cycles A / B**
- Curseur interactif (barre verticale + labels valeurs au survol)

### Rétro-ingénierie
- Table byte-par-byte pour chaque type de trame (65/69/77/83)
  - Coloration : vert = octet décodé connu, orange = inconnu
  - Clic droit sur une sélection : interprétation uint16, int16, float16, ASCII, bitmask
  - Case à cocher « Plot » pour tracer un octet ou une interprétation multi-octets
- Graphe libre — séries ajoutées manuellement

### Logs
- Vue console avec coloration par niveau (DEBUG/INFO/WARNING/ERROR)

---

## Partie Ada

Bibliothèque Ada 2022 portant la logique métier (machine d'état BLE, décodeur, API C).  
Conçue pour être compilée en bibliothèque statique et liée depuis n'importe quel backend BLE (BlueZ, BTstack, NimBLE, WinRT).

```powershell
cd src/Ada
alr build            # avec Alire
# ou
gprbuild -P corelec_ada.gpr
```

Voir [src/Ada/README.md](src/Ada/README.md) pour les options de cross-compilation (ARM, Linux x86_64).

---

## État du projet

| Composant                        | État               |
|----------------------------------|--------------------|
| Acquisition BLE (bleak)          | Fonctionnel        |
| Décodeur trames 77/83/65/69      | Fonctionnel        |
| Stockage SQLite                  | Fonctionnel        |
| Dashboard graphiques             | Fonctionnel        |
| Rétro-ingénierie UI              | Fonctionnel        |
| Daemon headless (ble_daemon.py)  | Fonctionnel        |
| Protocole réseau ZMQ/JSON        | Fonctionnel        |
| Monitor UI dual-mode             | Fonctionnel        |
| Sync DB réseau                   | Fonctionnel        |
| Scripts systemd Pi3              | Fournis            |
| Compatibilité PyQt5/Pi3 (Qt UI)  | Via apt uniquement |
| Bibliothèque Ada                 | En cours (0.1-dev) |
| Backend BLE Ada (BlueZ/BTstack)  | Non démarré        |

---

## Licence

MIT
