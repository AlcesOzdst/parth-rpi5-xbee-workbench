#!/usr/bin/env python3
import asyncio
import os
import random
import sys
import json
import datetime
import paho.mqtt.client as mqtt
from colorama import Fore, Style, init

init(autoreset=True)

LOG_FILE = "/app/src/container_terminal.log"

# Global MQTT Client
mqtt_host = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
mqtt_client = None

def emit_terminal(target, text, color=""):
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    # 1. Print directly to container stdout (visible in docker logs)
    if color:
        print(f"{color}[{now_str}] {text}{Style.RESET_ALL}", flush=True)
    else:
        print(f"[{now_str}] {text}", flush=True)
    
    # 2. Append to shared log file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{now_str}] [{target.upper()}] {text}\n")
    except Exception:
        pass

    # 3. Publish over MQTT for live WebSocket terminal streaming
    if mqtt_client:
        try:
            payload = json.dumps({
                "target": target,
                "time": now_str,
                "text": text,
                "color": color
            })
            mqtt_client.publish(f"zigbee/terminal/{target}", payload)
            mqtt_client.publish("zigbee/terminal/all", payload)
        except Exception:
            pass

# Initialize log file
try:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Container wsl_zigbee_simulator logging started.\n")
except Exception:
    pass

def on_mqtt_connect(client, userdata, flags, rc, *args):
    if rc == 0:
        emit_terminal("system", f"[MQTT GATEWAY] Connected to broker at {mqtt_host}:1883", Fore.GREEN)
        client.subscribe("zigbee/custom/tx")
        emit_terminal("coordinator", "[COORDINATOR] Subscribed to custom message downlink channel (zigbee/custom/tx)", Fore.GREEN)

def on_mqtt_message(client, userdata, msg):
    if msg.topic == "zigbee/custom/tx":
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            target = data.get("target", "0xFFFF")
            custom_msg = data.get("message", "").strip()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            if not custom_msg:
                return

            # 1. Coordinator transmits the RF frame
            emit_terminal("coordinator", f"[COORDINATOR TX Frame] Target: {target} | Custom Payload: '{custom_msg}'", Fore.GREEN)

            # 2. Virtual nodes react to the message
            responses = []
            
            # Router reaction
            if target in ["0xFFFF", "0x2001", "Router"]:
                lqi = random.randint(245, 255)
                rssi = f"-{random.randint(42, 60)}dBm"
                resp = {
                    "src_node": "0x2001",
                    "type": "Router",
                    "target": target,
                    "original_msg": custom_msg,
                    "time": now_str,
                    "lqi": lqi,
                    "rssi": rssi,
                    "reply": f"Router 0x2001 ACK: '{custom_msg}' forwarded across mesh"
                }
                responses.append(resp)
                emit_terminal("router", f"[ROUTER 0x2001] Mesh RX from Coord: '{custom_msg}' -> ACK Sent (LQI={lqi})", Fore.MAGENTA)

            # Sensor 0x1001 reaction
            if target in ["0xFFFF", "0x1001", "Sensor_1"]:
                lqi = random.randint(235, 255)
                rssi = f"-{random.randint(48, 70)}dBm"
                resp = {
                    "src_node": "0x1001",
                    "type": "EndDevice",
                    "target": target,
                    "original_msg": custom_msg,
                    "time": now_str,
                    "lqi": lqi,
                    "rssi": rssi,
                    "reply": f"Sensor 0x1001 processed: '{custom_msg}' (battery=98%)"
                }
                responses.append(resp)
                emit_terminal("sensor", f"[NODE 0x1001] Downlink RX: '{custom_msg}' -> ACK Returned (RSSI={rssi})", Fore.CYAN)

            # Sensor 0x1002 reaction
            if target in ["0xFFFF", "0x1002", "Sensor_2"]:
                lqi = random.randint(230, 255)
                rssi = f"-{random.randint(52, 75)}dBm"
                resp = {
                    "src_node": "0x1002",
                    "type": "EndDevice",
                    "target": target,
                    "original_msg": custom_msg,
                    "time": now_str,
                    "lqi": lqi,
                    "rssi": rssi,
                    "reply": f"Sensor 0x1002 processed: '{custom_msg}' (battery=95%)"
                }
                responses.append(resp)
                emit_terminal("sensor", f"[NODE 0x1002] Downlink RX: '{custom_msg}' -> ACK Returned (RSSI={rssi})", Fore.CYAN)

            # 3. Publish ACKs back over MQTT for the custom message window
            for r in responses:
                if mqtt_client:
                    mqtt_client.publish("zigbee/custom/rx", json.dumps(r))

        except Exception as e:
            emit_terminal("system", f"[ERROR processing custom command]: {e}", Fore.RED)

try:
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="zigbee_sim_daemon")
    except AttributeError:
        mqtt_client = mqtt.Client(client_id="zigbee_sim_daemon")
    
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.connect(mqtt_host, 1883, keepalive=60)
    mqtt_client.loop_start()
except Exception as e:
    emit_terminal("system", f"[MQTT GATEWAY ERROR] Could not connect to MQTT broker: {e}", Fore.RED)


class VirtualZigbeeCoordinator:
    def __init__(self, port_name="/tmp/zigbee_coord_pipe"):
        self.port_name = port_name

    async def start_listener(self):
        emit_terminal("coordinator", f"[COORDINATOR] Initialized virtual ZCL coordinator stack on {self.port_name}", Fore.GREEN)
        while True:
            await asyncio.sleep(5)
            emit_terminal("coordinator", f"[COORDINATOR] PAN 0x1234 active. Channel 15. Listening on {self.port_name}...", Fore.GREEN)


class VirtualZigbeeNode:
    def __init__(self, node_id: int, node_type: str):
        self.node_id = node_id
        self.ieee = f"00:15:8d:00:02:{node_id:02x}:ef:44"
        self.node_type = node_type
        self.target_name = "router" if node_type == "Router" else "sensor"
        self.metrics = {"temperature": 22.0, "battery": 98, "state": False}

    async def run_node_loop(self):
        emit_terminal(
            self.target_name,
            f"[NODE 0x{self.node_id:04X} ({self.node_type})] Joined network PAN 0x1234. Telemetry reporting active.",
            Fore.CYAN
        )
        while True:
            await asyncio.sleep(random.uniform(2.5, 4.5))
            if self.node_type == "EndDevice":
                self.metrics["temperature"] = round(self.metrics["temperature"] + random.uniform(-0.35, 0.35), 2)
                payload = {
                    "src_ieee": self.ieee,
                    "endpoint": 1,
                    "cluster": "TemperatureMeasurement",
                    "attribute": "measured_value",
                    "value": self.metrics["temperature"]
                }
                raw_frame = f"[RF RX Frame 0x{self.node_id:04X}] -> {json.dumps(payload)}"
                emit_terminal(self.target_name, raw_frame, Fore.YELLOW)
                if mqtt_client:
                    mqtt_client.publish(f"zigbee/sensor/{self.node_id:04X}", json.dumps(payload))
            else:
                self.metrics["state"] = not self.metrics["state"]
                payload = {
                    "src_ieee": self.ieee,
                    "cluster": "OnOffRelay",
                    "relay_state": self.metrics["state"]
                }
                raw_frame = f"[ROUTER 0x{self.node_id:04X}] Mesh heartbeat forwarded. Relay state: {self.metrics['state']}"
                emit_terminal(self.target_name, raw_frame, Fore.MAGENTA)
                if mqtt_client:
                    mqtt_client.publish(f"zigbee/router/{self.node_id:04X}", json.dumps(payload))


async def main():
    emit_terminal("system", "==================================================", Fore.BLUE)
    emit_terminal("system", "   Dockerized Headless Zigbee Simulation Engine", Fore.BLUE)
    emit_terminal("system", "==================================================", Fore.BLUE)
    
    coordinator = VirtualZigbeeCoordinator()
    
    nodes = [
        VirtualZigbeeNode(0x1001, "EndDevice"),
        VirtualZigbeeNode(0x1002, "EndDevice"),
        VirtualZigbeeNode(0x2001, "Router")
    ]

    await asyncio.gather(
        coordinator.start_listener(),
        *[node.run_node_loop() for node in nodes]
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        emit_terminal("system", "Simulation stopped by user.", Fore.RED)
        sys.exit(0)
