#!/usr/bin/env bash
set -e

# ==============================================================================
# Raspberry Pi 5 & XBee Mesh Simulator - 1-Click Startup Script
# ==============================================================================

echo -e "\033[1;36m==> [1/4] Checking environment prerequisites...\033[0m"
if ! command -v docker &> /dev/null; then
    echo -e "\033[1;31m[ERROR] Docker is not installed or not in PATH.\033[0m"
    echo "Please install Docker Desktop or Docker Engine before proceeding."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "\033[1;31m[ERROR] Docker daemon is not running.\033[0m"
    echo "Please start Docker Desktop (or run 'sudo service docker start') and re-run."
    exit 1
fi

echo -e "\033[1;36m==> [2/4] Preparing directories and Mosquitto permissions...\033[0m"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure data and log directories exist
mkdir -p mosquitto/data mosquitto/log mosquitto/config

# Create stub database and log files if not present
if [ ! -f mosquitto/data/mosquitto.db ]; then
    touch mosquitto/data/mosquitto.db 2>/dev/null || true
fi
if [ ! -f mosquitto/log/mosquitto.log ]; then
    touch mosquitto/log/mosquitto.log 2>/dev/null || true
fi

# Ensure container UID 1883 and host can read and write without root password prompts
chmod 777 mosquitto/data mosquitto/log 2>/dev/null || true
chmod 666 mosquitto/data/mosquitto.db mosquitto/log/mosquitto.log 2>/dev/null || true

echo -e "\033[1;36m==> [3/4] Building and launching Docker container stack...\033[0m"
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d --build

echo -e "\033[1;36m==> [4/4] Verifying container services...\033[0m"
sleep 2

ALL_UP=true
for container in zigbee_mqtt_broker wsl_zigbee_simulator zigbee_dashboard_ui; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "  \033[1;32m✓\033[0m Container [${container}] is running."
    else
        echo -e "  \033[1;31m✗\033[0m Container [${container}] FAILED to start."
        ALL_UP=false
    fi
done

if [ "$ALL_UP" = true ]; then
    echo -e "\n\033[1;32m=======================================================================\033[0m"
    echo -e "\033[1;32m SUCCESS! The Zigbee Mesh Simulator is now running. \033[0m"
    echo -e " Open your browser to: \033[1;34mhttp://localhost:8080/\033[0m"
    echo -e " WebSockets broker:     \033[1;34mws://localhost:9001\033[0m"
    echo -e "\033[1;32m=======================================================================\033[0m\n"
else
    echo -e "\n\033[1;31mOne or more containers failed. Check logs using: docker compose logs\033[0m\n"
    exit 1
fi
