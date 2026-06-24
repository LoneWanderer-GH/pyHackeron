#!/usr/bin/env bash
# =============================================================================
# install_nas.sh — Installation du serveur web Corelec sur NAS Synology DSM 7
# =============================================================================
# Usage :
#   bash nas/install_nas.sh <DAEMON_IP> [HTTP_PORT]
#
#   DAEMON_IP  : IP du Raspberry Pi qui exécute ble_daemon.py
#   HTTP_PORT  : port HTTP du serveur web (défaut : 8080)
#
# Exemples :
#   bash nas/install_nas.sh 192.168.0.16
#   bash nas/install_nas.sh 192.168.0.16 8080
#
# Prérequis sur le NAS :
#   - DSM 7.x
#   - Python 3 installé via Synology Package Center
#     (paquet "Python 3.11" ou équivalent, ou via SynoCommunity)
#   - Accès SSH activé (Panneau de config → Terminal & SNMP → Terminal)
#
# Ce script :
#   1. Crée le répertoire de travail /volume1/corelec/
#   2. Copie les sources depuis le dossier courant
#   3. Crée un virtualenv Python et installe flask + pyzmq
#   4. Écrit /etc/corelec/web.env
#   5. Installe le service systemd dans /usr/local/lib/systemd/system/
#      (emplacement persistant aux mises à jour DSM)
#   6. Active et démarre le service

set -euo pipefail

DAEMON_IP="${1:-}"
HTTP_PORT="${2:-8080}"

[[ -z "$DAEMON_IP" ]] && { echo "Usage : $0 <DAEMON_IP> [HTTP_PORT]"; exit 1; }

# Répertoire stable sur le volume principal (survit aux mises à jour DSM)
INSTALL_DIR="/volume1/corelec"
VENV_DIR="$INSTALL_DIR/venv"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="/etc/corelec"
SERVICE_NAME="corelec-web"
SERVICE_USER="corelec"
# /usr/local/lib/systemd/system/ est l'emplacement recommandé sur Synology
# pour les services tiers — non écrasé par les mises à jour DSM
SERVICE_DIR="/usr/local/lib/systemd/system"
SERVICE_FILE="$SERVICE_DIR/${SERVICE_NAME}.service"

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ---------------------------------------------------------------------------
# Vérifications préliminaires
# ---------------------------------------------------------------------------
info "=== Installation Corelec Web Server ==="
info "Daemon IP : $DAEMON_IP"
info "HTTP port : $HTTP_PORT"
info "Sources   : $SRC_DIR"

# Trouver l'interpréteur Python 3 disponible sur le NAS
PYTHON3=""
for candidate in \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    /usr/local/bin/python3.9  \
    /usr/bin/python3; do
    if "$candidate" --version &>/dev/null; then
        PYTHON3="$candidate"
        break
    fi
done
[[ -z "$PYTHON3" ]] && error "Python 3 introuvable. Installez-le via Synology Package Center."
info "Python trouvé : $PYTHON3 ($($PYTHON3 --version))"

# ---------------------------------------------------------------------------
# Répertoire d'installation
# ---------------------------------------------------------------------------
info "Création de $INSTALL_DIR…"
mkdir -p "$INSTALL_DIR"

info "Copie des sources vers $INSTALL_DIR…"
rsync -a --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.git' --exclude='pool.db' --exclude='*.log' \
    "$SRC_DIR/" "$INSTALL_DIR/"

# ---------------------------------------------------------------------------
# Virtualenv Python
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    info "Création du virtualenv dans $VENV_DIR…"
    "$PYTHON3" -m venv "$VENV_DIR"
fi

info "Installation des dépendances Python (flask, pyzmq)…"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/corelec/requirements_web.txt"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
info "Création de $CONFIG_DIR/web.env…"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/web.env" <<EOF
# Configuration Corelec Web Server
# Généré par install_nas.sh le $(date)

# IP du Raspberry Pi exécutant ble_daemon.py
CORELEC_HOST=$DAEMON_IP

# Ports ZeroMQ du daemon BLE
CORELEC_PUB_PORT=5555
CORELEC_CMD_PORT=5556

# Port HTTP du serveur web
CORELEC_WEB_PORT=$HTTP_PORT

# Niveau de log : DEBUG | INFO | WARNING | ERROR
CORELEC_LOG_LEVEL=INFO
EOF
chmod 600 "$CONFIG_DIR/web.env"

# ---------------------------------------------------------------------------
# Utilisateur dédié
# ---------------------------------------------------------------------------
if ! id -u "$SERVICE_USER" &>/dev/null; then
    info "Création de l'utilisateur système $SERVICE_USER…"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER" \
        || error "Impossible de créer l'utilisateur $SERVICE_USER. Sur Synology, le créer manuellement via Panneau de config → Utilisateur → Créer un utilisateur système. Assigner au groupe http."
fi

info "Attribution des permissions à $SERVICE_USER…"
# Conserver root comme propriétaire ; donner au groupe $SERVICE_USER le droit
# de lecture/traversal (sécurité : le service ne peut pas modifier ses propres
# binaires ou bibliothèques en cas de compromission).
chown -R "$SERVICE_USER":http "$INSTALL_DIR"
chmod -R g+rX "$INSTALL_DIR"
# Le fichier de configuration contient des valeurs potentiellement sensibles :
# accès réservé à root et au groupe $SERVICE_USER (pas de lecture publique).
chown "$SERVICE_USER":http "$CONFIG_DIR/web.env"
chmod 640 "$CONFIG_DIR/web.env"

# ---------------------------------------------------------------------------
# Service systemd
# ---------------------------------------------------------------------------
info "Installation du service systemd $SERVICE_NAME…"
mkdir -p "$SERVICE_DIR"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Corelec Web Server
Documentation=file://$INSTALL_DIR/docs/INSTALL.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_DIR/web.env
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/web_server.py
Restart=on-failure
RestartSec=10s
StartLimitIntervalSec=120
StartLimitBurst=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
sleep 2
STATUS=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)
if [[ "$STATUS" == "active" ]]; then
    info "✓ Service $SERVICE_NAME démarré avec succès"
    # info "  Dashboard : http://$(hostname -I | awk '{print $1}'):$HTTP_PORT"
    info "  Dashboard : http://$(hostname | awk '{print $1}'):$HTTP_PORT"
else
    warn "  Service status : $STATUS"
    warn "  Voir les logs : journalctl -fu $SERVICE_NAME"
fi

info ""
info "Commandes utiles :"
info "  sudo systemctl status  $SERVICE_NAME"
info "  sudo journalctl -fu    $SERVICE_NAME"
info "  sudo nano              $CONFIG_DIR/web.env"
info "  sudo systemctl restart $SERVICE_NAME"
