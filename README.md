# Corelec Monitor

Outil de supervision et de rétro-ingénierie d'un régulateur de piscine **Corelec** via BLE.  
Le régulateur communique en Bluetooth Low Energy ; ce projet intercepte, décode et affiche les données en temps réel, et permet d'explorer les trames inconnues.

---

## Architecture

```
src/
├── python/                   Python 3.9+ — interface BLE, UI, stockage
│   ├── BLE/                  Acquisition BLE (bleak), parsing trames, types
│   │   ├── Acquisition.py    Boucle async BLE, séquence de polling
│   │   ├── bluetooth.py      Constructeur de paquet « ask »
│   │   ├── frame.py          Parsing trame (sync=42, CRC XOR, 17 octets)
│   │   ├── stream.py         Réassemblage flux BLE → trames complètes
│   │   └── types.py          Dataclasses Decoded65/69/77/83, ConnectionInfo…
│   ├── Analyse/
│   │   ├── database.py       SQLite — stockage trames brutes + valeurs décodées
│   │   └── model.py          RegulatorState — état courant du régulateur
│   ├── ReverseEngineering/
│   │   ├── decoder.py        Décodeur des 4 types de trames (77/83/65/69)
│   │   └── ctypes_frames.py  Structures ctypes pour la vue byte-par-byte de l'UI
│   ├── UI/
│   │   ├── qt_compat.py      Couche de compatibilité Qt (PyQt5/6, PySide2/6)
│   │   ├── signals.py        Signaux Qt inter-couches (connexion, log, état…)
│   │   ├── dashboard.py      Dashboard principal (graphiques, métriques, logs)
│   │   └── reverse_ui.py     Panneau rétro-ingénierie (table bytes, tracé libre)
│   ├── core_logging.py       Logging coloré + redirection HTML vers l'UI Qt
│   ├── requirements_windows.txt
│   └── requirements_raspi3.txt
└── Ada/                      Bibliothèque Ada 2022 (logique métier, API C)
    ├── corelec_ada.gpr
    ├── alire.toml
    ├── src/                  Packages Ada (connexion, décodeur, protocole…)
    ├── include/              Headers C publics (corelec_ada.h)
    └── examples/             Harness de décodage Ada
```

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

### Windows (développement)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r src/python/requirements_windows.txt
```

### Raspberry Pi 3 (Python 3.9, PyQt5)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r src/python/requirements_raspi3.txt
```

> PyQt6 n'est pas disponible sur Pi3/Python 3.9. Le module `qt_compat.py` détecte automatiquement le binding disponible (PyQt5/6, PySide2/6) via pyqtgraph.

---

## Lancement

```powershell
# depuis la racine du projet
python -m src.python.UI.dashboard
```

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

| Composant                     | État              |
|-------------------------------|-------------------|
| Acquisition BLE (bleak)       | Fonctionnel       |
| Décodeur trames 77/83/65/69   | Fonctionnel       |
| Stockage SQLite               | Fonctionnel       |
| Dashboard graphiques          | Fonctionnel       |
| Rétro-ingénierie UI           | Fonctionnel       |
| Compatibilité PyQt5/Pi3       | Implémentée       |
| Bibliothèque Ada              | En cours (0.1-dev)|
| Backend BLE Ada (BlueZ/BTstack)| Non démarré      |

---

## Licence

MIT
