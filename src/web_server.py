#!/usr/bin/env python3
import http.server
import socketserver
import os
import json
import urllib.parse
import paho.mqtt.publish as publish

PORT = 8080
DIRECTORY = "/app/src/static"
SOURCE_FILE = "/app/src/simulation_daemon.py"
LOG_FILE = "/app/src/container_terminal.log"
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/send":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                publish.single("zigbee/custom/tx", json.dumps(data), hostname=MQTT_HOST, port=1883)
                resp = json.dumps({"status": "success", "sent": data}).encode('utf-8')
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode('utf-8')
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err)
            return
        self.send_error(404, "Endpoint not found")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: Exact Source Code Endpoint
        if parsed.path == "/api/source":
            target = query.get("target", ["full"])[0].lower()
            try:
                with open(SOURCE_FILE, "r", encoding="utf-8") as f:
                    full_code = f.read()

                snippet = full_code
                if target == "coordinator":
                    lines = full_code.splitlines()
                    start = None
                    end = None
                    for i, l in enumerate(lines):
                        if "class VirtualZigbeeCoordinator" in l:
                            start = i
                        elif start is not None and i > start and l.startswith("class "):
                            end = i
                            break
                    if start is not None:
                        snippet = "\n".join(lines[start:end if end else len(lines)])
                elif target == "sensor":
                    lines = full_code.splitlines()
                    snippet_lines = []
                    capture = False
                    for l in lines:
                        if "class VirtualZigbeeNode" in l:
                            capture = True
                        if capture:
                            if 'target_name = "router"' in l:
                                continue
                            if 'else:' in l and snippet_lines:
                                snippet_lines.append("            # (Router branch handled separately...)")
                                break
                            snippet_lines.append(l)
                    snippet = "\n".join(snippet_lines) if snippet_lines else full_code
                elif target == "router":
                    lines = full_code.splitlines()
                    snippet_lines = [
                        "# VirtualZigbeeNode - Mesh Router Relay Loop",
                        "async def run_node_loop(self):",
                        '    emit_terminal("router", f"[NODE 0x{self.node_id:04X} ({self.node_type})] Mesh active...", Fore.CYAN)',
                        "    while True:",
                        "        await asyncio.sleep(random.uniform(2.5, 4.5))",
                        "        self.metrics['state'] = not self.metrics['state']",
                        "        payload = {",
                        '            "src_ieee": self.ieee,',
                        '            "cluster": "OnOffRelay",',
                        '            "relay_state": self.metrics["state"]',
                        "        }",
                        '        raw_frame = f"[ROUTER 0x{self.node_id:04X}] Mesh heartbeat forwarded. Relay state: {self.metrics[\'state\']}"',
                        '        emit_terminal("router", raw_frame, Fore.MAGENTA)',
                        "        if mqtt_client:",
                        '            mqtt_client.publish(f"zigbee/router/{self.node_id:04X}", json.dumps(payload))'
                    ]
                    snippet = "\n".join(snippet_lines)

                resp = json.dumps({
                    "target": target,
                    "filename": "simulation_daemon.py",
                    "path": "/app/src/simulation_daemon.py",
                    "code": snippet,
                    "full_code": full_code
                }).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err_resp = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err_resp)
                return

        # 2. API: Real Container Terminal Logs Endpoint
        elif parsed.path == "/api/logs":
            target = query.get("target", ["all"])[0].lower()
            tail_count = int(query.get("tail", ["50"])[0])
            logs = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        all_lines = f.readlines()
                    
                    if target != "all":
                        tag = f"[{target.upper()}]"
                        filtered = [l.strip() for l in all_lines if tag in l or "[SYSTEM]" in l]
                    else:
                        filtered = [l.strip() for l in all_lines]
                    
                    logs = filtered[-tail_count:]
                except Exception as e:
                    logs = [f"[Error reading log file: {e}]"]
            else:
                logs = ["[Waiting for container logs to be written...]"]

            resp = json.dumps({
                "target": target,
                "container": "wsl_zigbee_simulator",
                "logs": logs
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        # Default static file serving
        super().do_GET()

with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
    print(f"Dashboard web server running at http://0.0.0.0:{PORT}")
    httpd.serve_forever()
