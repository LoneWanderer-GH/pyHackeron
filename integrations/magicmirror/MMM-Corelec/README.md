# MMM-Corelec — Plugin MagicMirror²

Affiche les paramètres de la piscine Corelec en temps réel dans MagicMirror².
Consomme l'API HTTP du `web_server.py` (pas de dépendance ZMQ directe).

## Installation

```bash
# Depuis le répertoire modules de MagicMirror :
cd ~/MagicMirror/modules

# Copier uniquement le dossier du plugin (pas tout le dépôt)
cp -r /path/to/pyHackeron/integrations/magicmirror/MMM-Corelec .

# Aucun npm install requis — pas de dépendances externes
```

## Configuration (`config/config.js`)

```javascript
{
  module: "MMM-Corelec",
  position: "top_right",       // toute position MagicMirror valide
  header: "🏊 Piscine",
  config: {
    webServerUrl: "http://192.168.0.20:8080",  // IP du NAS ou du Pi qui tourne web_server.py
    pollInterval: 30,   // secondes entre chaque rafraîchissement

    // Champs à afficher (dans l'ordre) :
    fields: ["ph", "temp", "electrolyse_pct", "boost"],

    // Champs disponibles :
    //   ph, ph_consigne, temp, redox, redox_consigne,
    //   electrolyse_pct, boost, connection

    showAlarms: true,    // bannière rouge si alarme active
    animateBoost: true,  // animation clignotante quand boost actif
  }
}
```

## Prérequis

- MagicMirror² ≥ 2.x (Node.js ≥ 18)
- `web_server.py` en cours d'exécution et accessible sur le réseau
