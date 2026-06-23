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

> **Pourquoi pas un simple `cp` ?**  
> Homebridge découvre les plugins via `npm` : il inspecte `node_modules/*/package.json`
> mais ne charge que les packages dont npm a enregistré les métadonnées dans son index local.
> Un copier-coller ne crée pas cet enregistrement → le plugin est ignoré silencieusement.

### Méthode 1 — `npm install` depuis le chemin local (recommandée)

```bash
# Aller dans le dossier de stockage Homebridge
cd /var/lib/homebridge          # Homebridge installé via hb-service
# OU
cd ~/.homebridge                # installation manuelle

# Installer le plugin depuis le dépôt local
npm install --save \
  /path/to/pyHackeron/integrations/homebridge/homebridge-corelec

# Redémarrer Homebridge
sudo hb-service restart         # ou : sudo systemctl restart homebridge
```

### Méthode 2 — `npm link` (développement)

```bash
# Dans le dossier du plugin
cd /path/to/pyHackeron/integrations/homebridge/homebridge-corelec
npm link

# Dans le dossier Homebridge
cd /var/lib/homebridge           # ou ~/.homebridge
npm link homebridge-corelec

sudo hb-service restart
```

### Via Homebridge UI

1. Dans **Plugins** → **⋯** → **Install Plugin from local path / tarball**
2. Saisir le chemin absolu vers `integrations/homebridge/homebridge-corelec/`
3. Redémarrer Homebridge depuis l'UI

### Vérification dans les logs

Après redémarrage, chercher dans les logs Homebridge :

```
[Homebridge] Loaded plugin: homebridge-corelec
[Corelec] Plugin initialisé — http://192.168.0.20:8080 (poll 30s)
```

Si rien n'apparaît → le plugin n'est pas chargé. Vérifier :
```bash
# Le package est bien dans node_modules ?
ls /var/lib/homebridge/node_modules/homebridge-corelec/

# npm le connaît ?
cd /var/lib/homebridge && npm list homebridge-corelec
```

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
