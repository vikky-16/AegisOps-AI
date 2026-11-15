import sys, os
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import socket
import uvicorn
from backend.app.main import app

if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 8000))
    sock.listen(128)
    print("[AegisOps Server] Bound cleanly to 127.0.0.1:8000 with SO_REUSEADDR", flush=True)

    config = uvicorn.Config(app=app, log_level="info")
    server = uvicorn.Server(config)
    server.run(sockets=[sock])
