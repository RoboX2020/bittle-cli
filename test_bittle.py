#!/usr/bin/env python3
"""Automated end-to-end test suite for Bittle custom commands and combos.

Tests:
1. CLI offline commands ('list', 'scan')
2. Mock Bittle WebSocket communication (raw, combos, chains, onboard queues)
3. Mock Bittle Virtual Serial (PTY) communication
4. Custom sequence definition and execution
"""

import asyncio
import os
import subprocess
import sys
import time

BITTLE_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_PY = os.path.join(BITTLE_DIR, "bittle_cli.py")
MOCK_PY = os.path.join(BITTLE_DIR, "mock_bittle.py")
SERIAL_LINK = "/tmp/ttyBittle_test"
WS_PORT = 8089

PASSED = "\033[32m[PASS]\033[0m"
FAILED = "\033[31m[FAIL]\033[0m"

total_tests = 0
passed_tests = 0


def run_cmd(args, timeout=15):
    global total_tests, passed_tests
    total_tests += 1
    desc = " ".join(args)
    print(f"\n--- Testing: {desc} ---")
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=BITTLE_DIR
        )
        if proc.returncode == 0:
            print(f"{PASSED} {desc}")
            if proc.stdout.strip():
                for line in proc.stdout.strip().splitlines()[:6]:
                    print(f"    {line}")
                if len(proc.stdout.strip().splitlines()) > 6:
                    print(f"    ... ({len(proc.stdout.strip().splitlines()) - 6} more lines)")
            passed_tests += 1
            return True, proc.stdout
        else:
            print(f"{FAILED} {desc} (Exit code {proc.returncode})")
            print("STDERR:", proc.stderr)
            print("STDOUT:", proc.stdout)
            return False, proc.stderr
    except subprocess.TimeoutExpired:
        print(f"{FAILED} {desc} (Timed out after {timeout}s)")
        return False, "Timeout"


def main():
    global total_tests, passed_tests
    print("=" * 60)
    print(" BITTLE CUSTOM COMMAND TEST SUITE ")
    print("=" * 60)

    # 1. Offline tests
    run_cmd([sys.executable, CLI_PY, "list"])
    run_cmd([sys.executable, CLI_PY, "scan"], timeout=10)

    # 2. Launch Mock Server in background
    print("\nStarting Mock Bittle server...")
    mock_proc = subprocess.Popen(
        [sys.executable, MOCK_PY, "--ws-port", str(WS_PORT), "--serial-link", SERIAL_LINK, "--quiet"],
        cwd=BITTLE_DIR
    )
    time.sleep(1.5)  # allow socket and pty setup

    try:
        # WebSocket tests
        ws_target = f"ws://127.0.0.1:{WS_PORT}"

        # Raw skill
        run_cmd([sys.executable, CLI_PY, "--wifi", ws_target, "ksit"])

        # Fused combo (tests 'K' token generation, base64 packing, gyro protection)
        run_cmd([sys.executable, CLI_PY, "--wifi", ws_target, "play", "flipShow"])

        # Step-by-step chain
        run_cmd([sys.executable, CLI_PY, "--wifi", ws_target, "chain", "moonwalkBow"])

        # On-board task queue ('q' token)
        run_cmd([sys.executable, CLI_PY, "--wifi", ws_target, "chain", "partyTrick", "--onboard"])

        # Rest/stop
        run_cmd([sys.executable, CLI_PY, "--wifi", ws_target, "stop"])

        # Virtual Serial tests
        if os.path.exists(SERIAL_LINK):
            # Raw skill over serial
            run_cmd([sys.executable, CLI_PY, "--serial", SERIAL_LINK, "ksit"])

            # Fused combo over serial (binary wire format with '~' terminator)
            run_cmd([sys.executable, CLI_PY, "--serial", SERIAL_LINK, "play", "boxerCombo"])

            # Chain over serial
            run_cmd([sys.executable, CLI_PY, "--serial", SERIAL_LINK, "chain", "moonwalkBow"])
        else:
            print(f"{FAILED} Virtual serial device {SERIAL_LINK} not found!")

    finally:
        print("\nStopping Mock Bittle server...")
        mock_proc.terminate()
        try:
            mock_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            mock_proc.kill()
        if os.path.islink(SERIAL_LINK) or os.path.exists(SERIAL_LINK):
            try:
                os.remove(SERIAL_LINK)
            except OSError:
                pass

    print("\n" + "=" * 60)
    print(f" TEST SUMMARY: {passed_tests}/{total_tests} passed ")
    print("=" * 60)
    if passed_tests == total_tests:
        print("\033[32mAll Bittle custom command tests PASSED successfully!\033[0m")
        return 0
    else:
        print("\033[31mSome tests failed.\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(main())
