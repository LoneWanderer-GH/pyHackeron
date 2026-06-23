# homebridge-corelec — Plugin Homebridge pour la piscine Corelec/Akeron

Expose le régulateur piscine dans **HomeKit** via Homebridge.  
Consomme l'API HTTP du `web_server.py` — aucune dépendance ZMQ directe.

## Accessoires exposés dans HomeKit

| Service HomeKit       | Nom              | Valeur                                          |
|-----------------------|------------------|-------------------------------------------------|
| `ContactSensor`       | Connexion BLE    | Contact = connecté / Ouvert = déconnecté        |
| `TemperatureSensor`   | pH               | Valeur pH (ex : 7.12 affiché comme 7.12 °C)     |
| `TemperatureSensor`   | Température eau  | Température eau (°C)                            |
| `Fanv2`               | Électrolyse      | % production — vitesse rotation 0-100 %         |
| `Switch`              | Boost            | ON = démarrer boost / OFF = arrêter             |

> **pH dans HomeKit** : le service `TemperatureSensor` est réutilisé pour afficher
> le pH. L'app Home affiche "7.12 °C" — nommer l'accessoire "pH" lève toute ambiguïté.
> Les apps tierces (Eve, Controller for HomeKit) peuvent afficher l'unité personnalisée.

## Installation

### Prérequis
- Homebridge ≥ 1.6 (Node.js ≥ 18)
- `web_server.py` en cours d'exécution sur le réseau local

### Copie du plugin

```bash
# Depuis le répertoire plugins de Homebridge (en général ~/.homebridge/node_modules)
# OU dans le dossier où Homebridge cherche ses plugins :

cd /var/lib/homebridge   # ou ~/.homebridge selon votre installation

# Créer le dossier du plugin
mkdir -p node_modules/homebridge-corelec

# Copier les deux fichiers depuis le dépôt
cp /path/to/pyHackeron/integrations/homebridge/homebridge-corelec/index.js \
   /path/to/pyHackeron/integrations/homebridge/homebridge-corelec/package.json \
   node_modules/homebridge-corelec/

# Aucun npm install requis — pas de dépendances npm externes
```

### Via Homebridge UI (méthode recommandée)

1. Copiez le dossier `homebridge-corelec/` dans un répertoire temporaire accessible
2. Dans Homebridge UI → **Plugins** → **Install Plugin** → fournissez le chemin local  
   (ou publiez sur npm pour une installation standard)

### Configuration (`~/.homebridge/config.json`)

```json
{
  "accessories": [
    {
      "accessory": "CoreLecPool",
      "name": "Piscine",
      "webServerUrl": "http://192.168.0.20:8080",
      "pollInterval": 30,
      "boostMinutes": 120
    }
  ]
}
```

| Paramètre      | Défaut                    | Description                                      |
|----------------|---------------------------|--------------------------------------------------|
| `webServerUrl` | `http://localhost:8080`   | URL du `web_server.py`                           |
| `pollInterval` | `30`                      | Intervalle de mise à jour (secondes)             |
| `boostMinutes` | `120`                     | Durée du boost quand on active le Switch HomeKit |

## Remarques de sécurité

- Le plugin envoie des commandes BLE sans authentification (limitation du protocole Corelec).
- Le `web_server.py` doit être accessible **uniquement sur le réseau local**.
- Ne pas exposer le port 8080 sur Internet.
