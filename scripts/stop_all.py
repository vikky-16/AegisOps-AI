"""
AegisOps AI System Stopper
Terminates running microservices, backend, and frontend processes on ports 8000-8004 and 5173.
"""

import subprocess
import sys

# All AegisOps platform, frontend, and company microservice ports
PORTS = (
    [8000, 5173]
    + list(range(8100, 8105))  # ShopSphere: 8100-8104
    + list(range(8200, 8206))  # FinCore: 8200-8205
    + list(range(8300, 8306))  # CloudDesk: 8300-8305
    + list(range(8001, 8007))  # Demo/legacy services: 8001-8006
)


def kill_ports():
    print("[AegisOps] Cleaning up all system and company ports...")
    for port in PORTS:
        try:
            cmd = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"
            res = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            pids = res.stdout.strip().split()
            for pid in pids:
                if pid and pid.isdigit():
                    print(f"Stopping process {pid} on port {port}...")
                    subprocess.run(["powershell", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"])
        except Exception as e:
            pass
    print("[AegisOps] All ports cleaned up successfully.")


if __name__ == "__main__":
    kill_ports()
