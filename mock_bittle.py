#!/usr/bin/env python3
"""Mock Petoi Bittle X robot simulator.

Simulates both:
1. WebSocket server (compatible with OpenCatEsp32 web server protocol)
2. Virtual Serial PTY port (echoing confirmation tokens like real firmware)

Enables testing Bittle custom commands, combos, and chains without hardware.
"""

import argparse
import asyncio
import base64
import json
import os
import pty
import sys
import time

class MockBittle:
    def __init__(self, ws_port=8081, serial_link="/tmp/ttyBittle", quiet=False):
        self.ws_port = ws_port
        self.serial_link = serial_link
        self.quiet = quiet
        self.gyro_enabled = True
        self.current_state = "neutral"
        self.command_history = []
        self.running = True

    def log(self, msg):
        if not self.quiet:
            ts = time.strftime("%H:%M:%S")
            print(f"[\033[36mMOCK-BITTLE {ts}\033[0m] {msg}")

    def handle_command_str(self, cmd_text):
        cmd = cmd_text.strip()
        self.command_history.append(cmd)
        result_token = "k"

        if cmd.startswith("k"):
            skill = cmd[1:]
            self.current_state = skill
            self.log(f"Skill executed: \033[32m{skill}\033[0m (raw: {cmd})")
            result_token = "k"
        elif cmd.startswith("q"):
            self.log(f"Task queue (on-board chain): \033[33m{cmd}\033[0m")
            result_token = "q"
        elif cmd == "gb":
            self.gyro_enabled = False
            self.log("Gyro balancing: \033[31mOFF\033[0m")
            result_token = "g"
        elif cmd == "gB":
            self.gyro_enabled = True
            self.log("Gyro balancing: \033[32mON\033[0m")
            result_token = "g"
        elif cmd == "d":
            self.current_state = "rest"
            self.log("Servos relaxed / rest: \033[34mrest\033[0m")
            result_token = "d"
        elif cmd.startswith("b64:"):
            # Base64 binary payload (fused combo 'K')
            raw = base64.b64decode(cmd[4:])
            token = chr(raw[0])
            result_token = token.lower()
            if token == "K" and len(raw) >= 8:
                frames = 256 - raw[1] if raw[1] > 127 else raw[1]
                ratio = raw[4]
                self.log(f"Fused Combo uploaded (\033[35mK\033[0m token): {frames} frames, ratio={ratio}, {len(raw)} bytes")
            else:
                self.log(f"Binary command '{token}', {len(raw)} bytes")
        elif cmd.startswith("w%"):
            self.log(f"WiFi setup received: {cmd}")
            result_token = "w"
        else:
            token = cmd[0] if cmd else "k"
            result_token = token.lower()
            self.log(f"Raw command: '{cmd}', echoing '{result_token}'")

        return result_token

    async def run_ws_server(self):
        import websockets

        async def handler(websocket):
            peer = websocket.remote_address
            self.log(f"Client connected from {peer}")
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get("type")
                    if msg_type == "heartbeat":
                        continue

                    if msg_type == "command":
                        task_id = data.get("taskId", "0")
                        commands = data.get("commands", [])
                        results = []
                        for c in commands:
                            tok = self.handle_command_str(c)
                            results.append(tok)

                        resp = {
                            "type": "response",
                            "taskId": task_id,
                            "status": "completed",
                            "results": results
                        }
                        await websocket.send(json.dumps(resp))
            except Exception as e:
                self.log(f"Client disconnected ({e})")

        server = await websockets.serve(handler, "0.0.0.0", self.ws_port)
        self.log(f"WebSocket mock server listening on \033[32mws://127.0.0.1:{self.ws_port}\033[0m")
        return server

    def setup_serial_pty(self):
        master, slave = pty.openpty()
        slave_name = os.ttyname(slave)
        
        # Link to desired serial path
        if os.path.exists(self.serial_link) or os.path.islink(self.serial_link):
            os.remove(self.serial_link)
        os.symlink(slave_name, self.serial_link)
        self.log(f"Virtual serial port created at \033[32m{self.serial_link}\033[0m -> {slave_name}")
        return master, slave

    async def run_serial_loop(self, master):
        loop = asyncio.get_running_loop()
        buf = b""

        while self.running:
            try:
                chunk = await loop.run_in_executor(None, os.read, master, 128)
            except (OSError, EOFError):
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf or b"~" in buf:
                # Find delimiter
                nl_idx = buf.find(b"\n")
                tl_idx = buf.find(b"~")
                
                if nl_idx != -1 and (tl_idx == -1 or nl_idx < tl_idx):
                    line, buf = buf[:nl_idx], buf[nl_idx + 1:]
                    cmd_str = line.decode(errors="replace").strip()
                    if cmd_str:
                        token = self.handle_command_str(cmd_str)
                        os.write(master, (token + "\n").encode())
                elif tl_idx != -1:
                    raw_cmd, buf = buf[:tl_idx], buf[tl_idx + 1:]
                    if raw_cmd:
                        token_char = chr(raw_cmd[0])
                        if token_char == "K":
                            frames = 256 - raw_cmd[1] if raw_cmd[1] > 127 else raw_cmd[1]
                            self.log(f"Serial Fused Combo (K): {frames} frames ({len(raw_cmd)} bytes)")
                        else:
                            self.log(f"Serial binary command '{token_char}', {len(raw_cmd)} bytes")
                        os.write(master, (token_char.lower() + "\n").encode())

    async def start(self):
        ws_server = await self.run_ws_server()
        master, slave = self.setup_serial_pty()
        serial_task = asyncio.create_task(self.run_serial_loop(master))

        try:
            await asyncio.gather(
                ws_server.wait_closed(),
                serial_task
            )
        except asyncio.CancelledError:
            pass
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            try:
                os.close(master)
                os.close(slave)
            except OSError:
                pass
            if os.path.islink(self.serial_link):
                os.remove(self.serial_link)
            self.log("Mock Bittle stopped.")


def main():
    parser = argparse.ArgumentParser(description="Mock Bittle X Simulator Server")
    parser.add_argument("--ws-port", type=int, default=8081, help="WebSocket port (default: 8081)")
    parser.add_argument("--serial-link", default="/tmp/ttyBittle", help="Symlink path for virtual serial PTY")
    parser.add_argument("--quiet", action="store_true", help="Suppress log output")
    args = parser.parse_args()

    mock = MockBittle(ws_port=args.ws_port, serial_link=args.serial_link, quiet=args.quiet)
    try:
        asyncio.run(mock.start())
    except KeyboardInterrupt:
        print("\nExiting mock Bittle.")


if __name__ == "__main__":
    main()
