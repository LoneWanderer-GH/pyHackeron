#!/usr/bin/env bash
# =============================================================================
# install_raspi.sh — Installation et configuration du daemon Corelec sur Pi3
# =============================================================================
# Usage :
#   sudo bash raspi/install_raspi.sh [BLE_ADDRESS]
#
# Ce script :
#   1. Installe les dépendances système (Python 3.9+, ZeroMQ, BlueZ)
#   2. Crée un virtualenv Python dans /opt/corelec/venv
#   3. Installe les paquets Python (corelec/requirements_daemon.txt)
#   4. Crée /etc/corelec/config.env avec l’adresse BLE
#   5. Installe et active le service systemd corelec-daemon.service
#
# Lancé depuis la racine du projet :
#   git clone ... && cd corelec-monitor
#   sudo bash raspi/install_raspi.sh B4:E3:F9:5A:0A:13
#
# Testé sur Raspberry Pi OS Bullseye (Debian 11) avec Python 3.9+

set -euo pipefail

BLE_ADDRESS="${1:-}"
INSTALL_DIR="/opt/corelec"
VENV_DIR="$INSTALL_DIR/venv"
# SRC_DIR = racine du projet (répertoire parent de raspi/)
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="/etc/corelec"
SERVICE_NAME="corelec-daemon"
RUN_USER="pi"   # à adapter si l'utilisateur est différent
DB_PATH="$INSTALL_DIR/pool.db"
LOG_LEVEL="INFO"

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ---------------------------------------------------------------------------
# Vérifications
# ---------------------------------------------------------------------------
[[ $EUID -ne 0 ]] && error "Ce script doit être lancé en root (sudo)"

info "Répertoire source : $SRC_DIR"

# ---------------------------------------------------------------------------
# Dépendances système
# ---------------------------------------------------------------------------
info "Mise à jour des paquets système…"
apt-get update -qq

info "Installation des dépendances système…"
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    libzmq3-dev \
    bluetooth bluez \
    libglib2.0-dev

# ---------------------------------------------------------------------------
# Répertoire d'installation
# ---------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR"
chown "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"

# Copie des sources
info "Copie des sources vers $INSTALL_DIR…"
rsync -a --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.git' --exclude='pool.db' \
    "$SRC_DIR/" "$INSTALL_DIR/"
chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"

# ---------------------------------------------------------------------------
# Virtualenv Python
# ---------------------------------------------------------------------------
info "Création du virtualenv dans $VENV_DIR…"
sudo -u "$RUN_USER" python3 -m venv "$VENV_DIR"

info "Installation des paquets Python (mode headless)…"
sudo -u "$RUN_USER" "$VENV_DIR/bin/pip" install --upgrade pip wheel
sudo -u "$RUN_USER" "$VENV_DIR/bin/pip" install \
    -r "$INSTALL_DIR/corelec/requirements_daemon.txt"

# ---------------------------------------------------------------------------
# Fichier de configuration
# ---------------------------------------------------------------------------
mkdir -p "$CONFIG_DIR"

if [[ -z "$BLE_ADDRESS" ]]; then
    warn "Aucune adresse BLE fournie. Éditer $CONFIG_DIR/config.env manuellement."
    BLE_ADDRESS="00:00:00:00:00:00"
fi

cat > "$CONFIG_DIR/config.env" <<EOF
# Configuration Corelec BLE Daemon
# Éditer ce fichier et relancer : sudo systemctl restart $SERVICE_NAME

CORELEC_ADDRESS=$BLE_ADDRESS
CORELEC_PUB_PORT=5555
CORELEC_CMD_PORT=5556
CORELEC_DB_PATH=$DB_PATH
CORELEC_LOG_LEVEL=$LOG_LEVEL
EOF

chmod 640 "$CONFIG_DIR/config.env"
chown root:"$RUN_USER" "$CONFIG_DIR/config.env"
info "Configuration écrite dans $CONFIG_DIR/config.env"

# ---------------------------------------------------------------------------
# Service systemd
# ---------------------------------------------------------------------------
info "Installation du service systemd $SERVICE_NAME…"

cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Corelec BLE Daemon
Documentation=https://github.com/yourrepo/corelec
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_DIR/config.env
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/ble_daemon.py
Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=60
StartLimitBurst=5

# Sécurité minimale
NoNewPrivileges=yes
PrivateTmp=yes

# Journalisation
StandardOutput=journal
StandardError=journal
SyslogIdentifier=corelec-daemon

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

info "Service $SERVICE_NAME démarré et activé au boot."
info ""
info "Commandes utiles :"
info "  sudo systemctl status  $SERVICE_NAME"
info "  sudo systemctl restart $SERVICE_NAME"
info "  sudo journalctl -fu     $SERVICE_NAME"
info "  sudo nano $CONFIG_DIR/config.env"
