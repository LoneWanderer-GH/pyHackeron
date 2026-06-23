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

---

## NAS Synology / serveur — interface web

```bash
pip install -r corelec/requirements_web.txt    # flask + pyzmq

python web_server.py --daemon-host 192.168.0.16 --http-port 8080
# Ouvrir http://<nas-ip>:8080 dans un navigateur ou sur smartphone
```

Variables d'environnement disponibles : `CORELEC_HOST`, `CORELEC_PUB_PORT`,
`CORELEC_CMD_PORT`, `CORELEC_WEB_PORT`.

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
