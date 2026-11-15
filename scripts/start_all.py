"""
AegisOps AI - Enterprise System Launcher
Starts all core components:
1. AegisOps Central Backend Orchestrator (Port 8000)
2. ShopSphere Microservices Mesh (Ports 8100-8104)
3. FinCore Microservices Mesh (Ports 8200-8205)
4. CloudDesk Microservices Mesh (Ports 8300-8305)
5. React 19 Frontend Dashboard (Port 5173)
6. Continuous Real Multi-Company Traffic Generator (~2.5 RPS per company)
"""

import sys
import os
import time
import argparse
import subprocess
import signal

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_PYTHON = os.path.join(ROOT_DIR, "venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

PROCESSES = []


def start_service(name: str, cmd: list, cwd: str):
    print(f"  [+] Launching {name}...", flush=True)
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=(sys.platform == "win32")
    )
    PROCESSES.append((name, p))
    return p


def cleanup():
    print("\n[AegisOps] Shutting down all spawned processes...", flush=True)
    for name, p in PROCESSES:
        try:
            p.terminate()
        except Exception:
            pass
    # Invoke stop_all to ensure all ports are freed
    try:
        from scripts.stop_all import kill_ports
        kill_ports()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="AegisOps AI Unified System Launcher")
    parser.add_argument("--no-traffic", action="store_true", help="Do not start the background traffic generator")
    parser.add_argument("--no-frontend", action="store_true", help="Do not start the React frontend")
    parser.add_argument("--daemon", action="store_true", help="Launch all services in background and return immediately")
    args = parser.parse_args()

    print("=" * 78)
    print("      AEGISOPS AI - AUTONOMOUS SRE PLATFORM FULL STACK LAUNCHER")
    print("=" * 78)
    print(f"Root Directory: {ROOT_DIR}")
    print(f"Python Runtime: {VENV_PYTHON}\n")

    # 1. Start AegisOps Central Backend (Port 8000)
    start_service("AegisOps Backend (8000)", [VENV_PYTHON, "-m", "backend.app.main"], ROOT_DIR)
    time.sleep(1.0)

    # 2. Start ShopSphere Microservices (Ports 8100-8104)
    start_service("ShopSphere Services (8100-8104)", [VENV_PYTHON, "-m", "shopsphere.run_services"], ROOT_DIR)
    time.sleep(0.5)

    # 3. Start FinCore Microservices (Ports 8200-8205)
    start_service("FinCore Services (8200-8205)", [VENV_PYTHON, "-m", "fincore.run_services"], ROOT_DIR)
    time.sleep(0.5)

    # 4. Start CloudDesk Microservices (Ports 8300-8305)
    start_service("CloudDesk Services (8300-8305)", [VENV_PYTHON, "-m", "clouddesk.run_services"], ROOT_DIR)
    time.sleep(0.5)

    # 5. Start Controlled Microservices Mesh (Ports 8001-8005)
    start_service("Controlled Services Mesh (8001-8005)", [VENV_PYTHON, "-m", "services.run_controlled_services"], ROOT_DIR)
    time.sleep(0.5)

    # 6. Start React Frontend (Port 5173)
    if not args.no_frontend:
        frontend_dir = os.path.join(ROOT_DIR, "frontend")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        start_service("React Frontend (5173)", [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], frontend_dir)
        time.sleep(0.5)

    # 7. Start Multi-Company Real Traffic Generator
    if not args.no_traffic:
        start_service("Real Traffic Generator (2.5 RPS/co)", [VENV_PYTHON, "scripts/run_all_traffic.py"], ROOT_DIR)

    print("\n" + "=" * 78)
    print("   ALL AEGIS OPS SYSTEM COMPONENTS ARE NOW RUNNING!")
    print("=" * 78)
    print("   Frontend Dashboard:      http://127.0.0.1:5173")
    print("   Backend Orchestrator:    http://127.0.0.1:8000")
    print("   System Health Endpoint:  http://127.0.0.1:8000/api/health")
    print("   Telemetry Health:        http://127.0.0.1:8000/api/telemetry/health")
    print("   Live Telemetry Feed:     http://127.0.0.1:8000/api/telemetry/live")
    print("   WebSocket Stream:        ws://127.0.0.1:8000/ws/telemetry")
    print("   --------------------------------------------------------------")
    print("   Company Gateways:")
    print("   - Controlled Ingress Gateway: http://127.0.0.1:8001")
    print("   - ShopSphere (E-Commerce):    http://127.0.0.1:8100")
    print("   - FinCore (Financial):        http://127.0.0.1:8200")
    print("   - CloudDesk (Cloud/SaaS):     http://127.0.0.1:8300")
    print("=" * 78)
    if args.daemon:
        print("   [+] All AegisOps services launched successfully in daemon background mode.\n", flush=True)
        return

    print("Press Ctrl+C to terminate all services safely.\n", flush=True)

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
