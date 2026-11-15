# Raspberry Pi 5 & XBee 802.15.4 Mesh Simulator Workbench
> An asynchronous, containerized IoT mesh simulation engine and real-time telemetry workbench.

---

## ⚡ 60-Second Quickstart (Zero-to-Running)

### Prerequisites
1. **Docker Desktop** (or Docker Engine on Linux/WSL) running.
2. Port **8080** (HTTP) and **9001** (WebSockets) free.

### Step 1: Open Terminal in Project Directory
```bash
cd ~/zigbee_wsl_sim
```

### Step 2: Run the Automated Startup Script
```bash
./run.sh
```
*(This script automatically checks Docker status, builds directories, configures Mosquitto permissions, boots all 3 containers, and runs a healthcheck.)*

### Step 3: Open Workbench
Visit in your web browser:
```text
http://localhost:8080/
```
The status pill in the top-right corner will turn from `CONNECTING` to **`CONNECTED` (Emerald Green)**, and real-time Zigbee 802.15.4 telemetry frames will begin streaming immediately.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Web Browser Client              |
                      |       http://localhost:8080/          |
                      +-------------------+-------------------+
                                          |
                +-------------------------+-------------------------+
                | HTTP Port 8080 (REST)                             | WS Port 9001 (MQTT)
                v                                                   v
+-------------------------------+               +---------------------------------------+
|     zigbee_dashboard_ui       |               |          zigbee_mqtt_broker           |
| Python 3.11 SimpleHTTP Server |               |        Eclipse Mosquitto 2.0          |
|  - /api/source (Live Code)    |               |  - Port 1883: TCP MQTT (Internal)     |
|  - /api/logs   (Real Stdout)  |               |  - Port 9001: WebSockets (Browser)    |
|  - /api/send   (Downlink HTTP)|               +-------------------+-------------------+
+-------------------------------+                                   |
                                                                    | Port 1883
                                                                    v
                                                +---------------------------------------+
                                                |         wsl_zigbee_simulator          |
                                                |  - Virtual Coordinator (/dev/ttyAMA0) |
                                                |  - XBee Router 0x2001 (Relay)         |
                                                |  - XBee Sensor 0x1001 & 0x1002 (Temp) |
                                                +---------------------------------------+
```

---

## Features

- **Decoupled 3-Container Stack**: Mosquitto 2.0 MQTT Broker, Python async Zigbee simulation daemon, and zero-cache web server.
- **Bi-directional IEEE 802.15.4 Emulation**:
  - **Raspberry Pi 5 Hub**: Coordinator on `/dev/ttyAMA0`, PAN `0x1234`, channel 15.
  - **XBee Router (0x2001)**: Mesh forwarder and On/Off relay actuator.
  - **XBee Sensors (0x1001 & 0x1002)**: Telemetry nodes publishing simulated ZCL Temperature cluster readings.
- **Dynamic Downlink Messages**:
  - Dispatch custom text messages and control frames (`PING`, `POLL_TEMP`, `TOGGLE_RELAY`, `ALERT:ON`) directly down into the mesh via the **Custom TX** tab inside the inspection modal.
  - Nodes calculate simulated RSSI / LQI signal metrics and return uplink acknowledgments.
- **Direct Live Code & Real Terminal Inspection**:
  - Inspect the exact running Python code dynamically extracted from `simulation_daemon.py`.
  - Stream real stdout output directly from `docker logs -f wsl_zigbee_simulator`.

---

## Manual Startup (Alternative)

If you prefer running commands manually without `run.sh`:

```bash
# 1. Ensure directory structure & permissions
mkdir -p mosquitto/data mosquitto/log mosquitto/config
chmod -R 777 mosquitto/data mosquitto/log

# 2. Launch Docker compose
docker compose down --remove-orphans
docker compose up -d --build

# 3. Access Dashboard
# Open http://localhost:8080/
```

---

## MQTT Topic Reference

| Topic | Direction | Description |
| :--- | :--- | :--- |
| `zigbee/sensor/1001` | Node &rarr; Broker | Temperature frames from Sensor 0x1001 |
| `zigbee/sensor/1002` | Node &rarr; Broker | Temperature frames from Sensor 0x1002 |
| `zigbee/router/2001` | Router &rarr; Broker | Heartbeat & relay state toggle frames |
| `zigbee/custom/tx` | Dashboard &rarr; Nodes | Outgoing custom downlink command frames |
| `zigbee/custom/rx` | Nodes &rarr; Dashboard | Uplink acknowledgments with RSSI and LQI |
| `zigbee/terminal/#` | Container &rarr; Modal | Live container stdout log events |

---

## REST API Reference

- `GET /api/source?target=<coordinator|sensor|router|full>`: Dynamically extracts live Python class definitions from `simulation_daemon.py`.
- `GET /api/logs?target=<coordinator|sensor|router|all>&tail=50`: Returns recent container stdout lines.
- `POST /api/send`: Accepts JSON payload `{"target": "0x1001", "message": "PING"}` and forwards it into the MQTT broker.

---

## Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Permission denied: mosquitto.log`** | Mosquitto container UID 1883 lacks write permissions to host directory. | Run `chmod -R 777 mosquitto/data mosquitto/log` or execute `./run.sh`. |
| **`MQTT WebSocket: Connecting...`** | Port 9001 blocked or Mosquitto container stopped. | Run `docker logs zigbee_mqtt_broker` and ensure port 9001 is listening. |
| **`docker: command not found`** | Docker is not installed or not exposed in WSL. | Enable Docker Desktop -> Settings -> Resources -> WSL Integration -> enable Ubuntu. |
| **Stale Web UI** | Browser cached old JavaScript. | Force refresh with `Ctrl + F5` (anti-cache headers are also enabled by default). |
