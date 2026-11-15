"""
Standalone CLI Log Seed & Traffic Simulator Runner
Usage:
  python scripts/seed_logs.py --rate 8 --failures 5 --max 0
"""

import sys
import os
import argparse
import asyncio
import signal
import httpx

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def run_via_api(host: str, rate: float, failures: float, max_logs: int):
    url = f"{host.rstrip('/')}/dev/logs/simulate/start"
    payload = {
        "log_rate_per_sec": rate,
        "failure_rate_per_min": failures,
        "max_logs": max_logs if max_logs > 0 else None
    }
    print(f"[*] Sending start command to {url} (Rate: {rate}/s, Failures: {failures}/min, Max: {max_logs or 'Unlimited'})...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                print(f"[✓] Simulator active on server! Check dashboard at {host}/admin/logs")
                print("[*] Press Ctrl+C to stop simulation on server...")
                # Poll status every 3 seconds
                status_url = f"{host.rstrip('/')}/dev/logs/simulate/status"
                while True:
                    await asyncio.sleep(3.0)
                    s_res = await client.get(status_url)
                    if s_res.status_code == 200:
                        st = s_res.json()
                        print(f"    -> Emitted: {st.get('total_emitted', 0):,} logs | Errors: {st.get('total_errors', 0)} | Healed: {st.get('total_healed', 0)} | Buffer: {st.get('current_buffer_size', 0)}/300")
            else:
                print(f"[!] Server returned HTTP {res.status_code}: {res.text}")
        except httpx.ConnectError:
            print(f"[!] Could not connect to backend server at {host}. Running in local standalone mode instead...")
            await run_standalone(rate, failures, max_logs)


async def run_standalone(rate: float, failures: float, max_logs: int):
    from backend.app.dev_tools.log_simulator import log_simulator
    from backend.app.logger import realtime_logger

    log_simulator.update_config(
        log_rate_per_sec=rate,
        failure_rate_per_min=failures,
        max_logs=max_logs if max_logs > 0 else None
    )

    print(f"[*] Starting local standalone generator: {rate} logs/sec, ~{failures} failures/min, Max: {max_logs or 'Unlimited'}")
    await log_simulator.start()

    stop_event = asyncio.Event()

    def signal_handler():
        print("\n[*] Stopping generator...")
        log_simulator.stop()
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Windows signal handling fallback
        pass

    try:
        while not stop_event.is_set() and log_simulator.is_running:
            await asyncio.sleep(2.0)
            st = log_simulator.get_status()
            print(f"    -> Emitted: {st['total_emitted']:,} logs | Infos: {st['total_infos']} | Warns: {st['total_warns']} | Errors: {st['total_errors']} | Resolved: {st['total_healed']}")
    except (KeyboardInterrupt, asyncio.CancelledError):
        log_simulator.stop()


def main():
    parser = argparse.ArgumentParser(description="Continuous Real-Time Log Traffic & Failure Simulator")
    parser.add_argument("--rate", type=float, default=8.0, help="Log emission rate per second (default: 8.0)")
    parser.add_argument("--failures", type=float, default=5.0, help="Failure rate per minute (default: 5.0)")
    parser.add_argument("--max", type=int, default=0, help="Max total logs to generate (0 for unlimited)")
    parser.add_argument("--host", type=str, default="http://127.0.0.1:8000", help="Backend server URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--standalone", action="store_true", help="Force standalone mode without sending HTTP requests")

    args = parser.parse_args()

    print("=" * 65)
    print("  ⚡ AegisOps AI - Continuous Real-Time Log Simulator")
    print("=" * 65)

    if args.standalone:
        asyncio.run(run_standalone(args.rate, args.failures, args.max))
    else:
        try:
            asyncio.run(run_via_api(args.host, args.rate, args.failures, args.max))
        except KeyboardInterrupt:
            # Send stop command to API
            print("\n[*] Stopping simulator on server...")
            try:
                httpx.post(f"{args.host.rstrip('/')}/dev/logs/simulate/stop", timeout=3.0)
                print("[✓] Server simulator stopped.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
