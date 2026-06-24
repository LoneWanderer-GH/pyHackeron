# Installation

## Raspberry Pi 3 — daemon headless (recommandé)

```bash
# Installation automatique (adresse BLE en argument)
sudo bash raspi/install_raspi.sh B4:E3:F9:5A:0A:13
```

Le script :
1. Installe `bleak` et `pyzmq` dans un venv
2. Copie et active le service systemd `corelec-daemon`
3. Configure `/etc/corelec/config.env`

### Manuellement

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r corelec/requirements_daemon.txt   # bleak + pyzmq uniquement
python ble_daemon.py --address B4:E3:F9:5A:0A:13
```

> **PyQt5 sur Pi3** : `pip install PyQt5` échoue sur Python 3.9 ARM.  
> Le daemon n'a **aucune dépendance Qt**. Pour l'UI Qt sur Pi, passer par apt :
> ```bash
> sudo apt-get install python3-pyqt5 python3-pyqtgraph
> python3 -m venv --system-site-packages venv
> ```

### Gestion du service systemd

```bash
sudo systemctl status  corelec-daemon
sudo journalctl -fu    corelec-daemon          # logs en temps réel
sudo nano /etc/corelec/config.env              # modifier adresse BLE, ports…
sudo systemctl restart corelec-daemon
```

Variables disponibles dans `/etc/corelec/config.env` :

| Variable                | Défaut           | Description                          |
|-------------------------|------------------|--------------------------------------|
| `CORELEC_ADDRESS`       | _(obligatoire)_  | Adresse MAC BLE du régulateur        |
| `CORELEC_PUB_PORT`      | `5555`           | Port ZMQ PUB (publication données)   |
| `CORELEC_CMD_PORT`      | `5556`           | Port ZMQ PULL (réception commandes)  |
| `CORELEC_DB_PATH`       | `pool.db`        | Chemin de la base SQLite             |
| `CORELEC_POLL_INTERVAL` | `5.0`            | Intervalle de polling BLE (secondes) |
| `CORELEC_LOG_LEVEL`     | `INFO`           | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

---

## Windows / macOS / Linux — interface graphique Qt

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1            # Windows
# source venv/bin/activate             # Linux/macOS
pip install -r corelec/requirements_windows.txt

# Mode réseau (daemon sur Pi3)
python monitor.py --network 192.168.1.42

# Mode BLE direct (sans Pi3)
python monitor.py --address B4:E3:F9:5A:0A:13

# Avec synchronisation de la base de données
python monitor.py --network 192.168.1.42 --sync-db --redecode
```

Toutes les options CLI sont aussi disponibles via variables d'environnement :

| Variable              | Équivalent CLI      | Défaut    |
|-----------------------|---------------------|-----------|
| `CORELEC_NETWORK`     | `--network`         | _(vide)_  |
| `CORELEC_ADDRESS`     | `--address`         | _(vide)_  |
| `CORELEC_PUB_PORT`    | `--pub-port`        | `5555`    |
| `CORELEC_CMD_PORT`    | `--cmd-port`        | `5556`    |
| `CORELEC_DB_PATH`     | `--db-path`         | `pool.db` |
| `CORELEC_POLL_INTERVAL` | `--poll-interval` | `5.0`     |
| `CORELEC_LOG_LEVEL`   | `--log-level`       | `INFO`    |

---

## NAS Synology — serveur web (daemon)

Testé sur DS415 / DSM 7.x. Le serveur web (`web_server.py`) s'abonne au ZMQ du daemon
sur le Pi3 et expose le dashboard HTML + l'API REST sur le réseau local.

### Installation automatique

```bash
# Depuis une session SSH sur le NAS (activer SSH dans DSM → Panneau de config
# → Terminal & SNMP → Terminal)

# Prérequis : Python 3 installé via Synology Package Center
# (chercher "Python 3.11" ou utiliser SynoCommunity)

git clone <repo> /volume1/corelec-src
bash /volume1/corelec-src/nas/install_nas.sh 192.168.0.16 8080
#                                              ^IP daemon Pi3  ^port HTTP
```

Le script :
1. Copie les sources dans `/volume1/corelec/`
2. Crée un virtualenv et installe `flask` + `pyzmq`
3. Écrit la configuration dans `/etc/corelec/web.env`
4. Installe et active le service systemd `corelec-web`
   dans `/usr/local/lib/systemd/system/` *(emplacement persistant aux mises à jour DSM)*

### Installation manuelle (pas à pas)

```bash
# 1 — Préparer le répertoire
mkdir -p /volume1/corelec
rsync -a --exclude='venv' --exclude='.git' /path/to/repo/ /volume1/corelec/

# 2 — Virtualenv
python3 -m venv /volume1/corelec/venv
/volume1/corelec/venv/bin/pip install -r /volume1/corelec/corelec/requirements_web.txt

# 3 — Configuration
mkdir -p /etc/corelec
cp /volume1/corelec/nas/config.env.example /etc/corelec/web.env
nano /etc/corelec/web.env          # adapter CORELEC_HOST et CORELEC_WEB_PORT

# 4 — Service systemd
cp /volume1/corelec/nas/corelec-web.service \
   /usr/local/lib/systemd/system/corelec-web.service
systemctl daemon-reload
systemctl enable corelec-web
systemctl start  corelec-web
```

### Gestion du service

```bash
sudo systemctl status  corelec-web
sudo journalctl -fu    corelec-web       # logs en temps réel
sudo nano /etc/corelec/web.env           # modifier IP daemon, port…
sudo systemctl restart corelec-web
```

Variables disponibles dans `/etc/corelec/web.env` :

| Variable            | Défaut       | Description                              |
|---------------------|--------------|------------------------------------------|
| `CORELEC_HOST`      | _(obligatoire)_ | IP du Raspberry Pi (daemon BLE)       |
| `CORELEC_PUB_PORT`  | `5555`       | Port ZMQ PUB du daemon                   |
| `CORELEC_CMD_PORT`  | `5556`       | Port ZMQ PULL du daemon                  |
| `CORELEC_WEB_PORT`  | `8080`       | Port HTTP du serveur web Corelec         |
| `CORELEC_LOG_LEVEL` | `INFO`       | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

### Alternative sans SSH — Planificateur de tâches DSM

Si l'accès SSH n'est pas souhaité, le Planificateur de tâches DSM peut lancer
le serveur au démarrage :

1. **DSM → Panneau de configuration → Planificateur de tâches**
2. Créer → Tâche déclenchée → Script défini par l'utilisateur
3. Paramètres :
   - Événement : **Démarrage**
   - Utilisateur : `root`
   - Script :
     ```bash
     #!/bin/bash
     source /etc/corelec/web.env
     cd /volume1/corelec
     ./venv/bin/python web_server.py \
         >> /volume1/corelec/web_server.log 2>&1 &
     ```
4. Cocher "Envoyer les détails d'exécution par e-mail" pour le suivi

> Cette méthode ne redémarre pas automatiquement le processus en cas de crash.
> Le service systemd est préférable si SSH est disponible.

### Mise à jour des sources

```bash
# Mettre à jour le code sans recréer le venv ni toucher la configuration
rsync -a --exclude='venv' --exclude='.git' --exclude='pool.db' \
    /path/to/new-repo/ /volume1/corelec/
sudo systemctl restart corelec-web
```

---

## ESP32 — firmware NimBLE + MQTT

```bash
cd esp32
idf.py menuconfig   # configurer SSID WiFi, broker MQTT, adresse BLE
idf.py build
idf.py -p COMx flash monitor
```

Voir [esp32/README.md](../esp32/README.md).

---

## Bibliothèque Ada

```powershell
cd ada
alr build -- -XCORELEC_BLE_BACKEND=winrt
# Fetch des sources vendeur si nécessaire :
.\backends\fetch_vendors.ps1
```

Voir [ada/README.md](../ada/README.md).
