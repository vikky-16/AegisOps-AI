import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from scripts.test_all_18_error_types import run_scenario, ALL_18_SCENARIOS

async def test():
    for sc_id, name, tenant, svc, downstreams in ALL_18_SCENARIOS:
        if sc_id in (3, 15, 16, 17):
            res = await run_scenario(sc_id, name, tenant, svc, downstreams)
            print(f"SCENARIO {sc_id}: {name}")
            print(f"  Detected: {res['detected']}")
            print(f"  Incident Created: {res['incident_created']}")
            print(f"  Primary RCA: {res['primary_rca']} (Correct: {res['correct_primary_rca']})")
            print(f"  Status: {res['final_status']}")
            if not res['detected'] or not res['correct_primary_rca']:
                print(f"  DEBUG RES: {res}")

if __name__ == "__main__":
    asyncio.run(test())
