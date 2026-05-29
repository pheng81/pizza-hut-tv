#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="https://api.everydayadvertise.com"
TARGET_USER="$(id -un)"
INSTALL_DIR="${HOME}/everydayadvertise_tv_client"
SERVICE_NAME="everydayadvertise_tv"
START_NOW=0
FINALIZE_ONLY=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${INSTALL_DIR}/venv"

usage() {
    cat <<'EOF'
Usage: prepare_golden_image.sh [options]

Prepare a Raspberry Pi as a reusable EverydayAdvertise TV golden image.

Options:
  --server URL          Server URL for the Pi client.
  --install-dir PATH    Install directory for client files.
  --service-name NAME   systemd service name.
  --user NAME           User account that should run the client.
  --start-now           Start the client immediately for testing.
  --finalize-image      Stop service and remove device-specific state so the SD card can be cloned.
  --help                Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server)
            SERVER_URL="${2:-}"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="${2:-}"
            VENV_DIR="${INSTALL_DIR}/venv"
            shift 2
            ;;
        --service-name)
            SERVICE_NAME="${2:-}"
            shift 2
            ;;
        --user)
            TARGET_USER="${2:-}"
            shift 2
            ;;
        --start-now)
            START_NOW=1
            shift
            ;;
        --finalize-image)
            FINALIZE_ONLY=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

FILES=(
  "complete_pi_client.py"
  "pi_mobile_sync_addon.py"
  "pi_vnc_tunnel.py"
  "transition_engine.py"
)

copy_client_files() {
    mkdir -p "${INSTALL_DIR}"

    for file_name in "${FILES[@]}"; do
        install -m 0644 "${REPO_ROOT}/${file_name}" "${INSTALL_DIR}/${file_name}"
    done

    install -m 0644 "${REPO_ROOT}/pi_deployment/seamless_video_player.py" "${INSTALL_DIR}/seamless_video_player.py"
}

install_dependencies() {
    sudo apt-get update -y
    sudo apt-get install -y \
      python3 \
      python3-venv \
      python3-pip \
      python3-pygame \
      python3-pil \
            scrot \
      ffmpeg \
      mpv \
      libmpv2 \
      x11vnc

    python3 -m venv --system-site-packages "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
    "${VENV_DIR}/bin/pip" install \
      requests \
      "python-socketio[client]" \
      psutil \
      pillow \
      pygame \
      mss \
      python-mpv \
      qrcode
}

write_service() {
    cat > "/tmp/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=EverydayAdvertise TV Digital Signage Client
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
SupplementaryGroups=video render
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${TARGET_USER}/.Xauthority
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=${INSTALL_DIR}
ExecStartPre=/bin/sleep 10
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/complete_pi_client.py --server ${SERVER_URL}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

    sudo cp "/tmp/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
}

clear_runtime_state() {
    rm -f "${HOME}/.pizza_hut_tv_id"
    rm -f "${HOME}/.pizza_hut_tv_config.json"
    rm -f "${HOME}/pi_client_debug.log"
}

finalize_image() {
    sudo systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    clear_runtime_state
    echo
    echo "Golden image finalized."
    echo "The next boot will generate a new Pi ID and show the claim screen."
}

if [[ ${FINALIZE_ONLY} -eq 1 ]]; then
    finalize_image
    exit 0
fi

echo "== Prepare EverydayAdvertise TV Golden Image =="
echo "Server: ${SERVER_URL}"
echo "Install dir: ${INSTALL_DIR}"
echo "Run as user: ${TARGET_USER}"

copy_client_files
install_dependencies
write_service

if [[ ${START_NOW} -eq 1 ]]; then
    clear_runtime_state
    sudo systemctl restart "${SERVICE_NAME}"
    echo
    echo "Client started for live testing."
    echo "After testing, run this before cloning the SD card:"
    echo "  sudo bash ${SCRIPT_DIR}/prepare_golden_image.sh --finalize-image --service-name ${SERVICE_NAME}"
else
    sudo systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    clear_runtime_state
    echo
    echo "Golden image prepared."
    echo "You can now shut down this Pi and clone the SD card."
    echo "Each cloned Pi will boot straight into the claim screen on first start."
fi