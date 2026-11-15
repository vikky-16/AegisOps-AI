import asyncio
import json
from backend.app.analytics.simulation_lab import simulation_lab
from backend.app.knowledge.incident_memory import incident_memory

async def run_live_demo():
    print("=== STARTING LIVE END-TO-END DEMONSTRATION ===")
    res = await simulation_lab.execute_scenario(
        scenario_id="DATABASE_CONNECTION_EXHAUSTION",
        service="database-service",
        severity="CRITICAL",
        tenant_id="shopsphere"
    )
    print(f"TEST RUN ID: {res['test_id']}")
    print(f"SCENARIO: {res['scenario_name']}")
    print(f"OVERALL STATUS: {res['status']}")
    print(f"DETECTION RESULT: {res['detection_result']}")
    print(f"RCA RESULT: {res['rca_result']}")
    print(f"RECOVERY RESULT: {res['recovery_result']}")
    print(f"VERIFICATION RESULT: {res['verification_result']}")
    print(f"ATTEMPTS: {res['attempts']}")
    print(f"DURATION: {res['duration_sec']}s")
    print("\n--- BEFORE / AFTER METRICS ---")
    for metric, vals in res["before_after_metrics"].items():
        status_str = vals.get('status', 'NORMAL' if vals['after'] <= vals['before'] else 'ELEVATED')
        print(f"  {metric:<20}: Before = {vals['before']:>8.2f} {vals.get('unit', ''):<4} | After = {vals['after']:>8.2f} {vals.get('unit', ''):<4} ({status_str})")
    
    print("\n--- LIVE BACKEND EVENT TIMELINE ---")
    for e in res["timeline"]:
        print(f"  [{e['timestamp']}] {e['event']:<28} -> {e['message']}")
    
    # Check historical CBR similarity matching for repeat failure
    matches = incident_memory.find_similar_incidents(
        service="database-service",
        category="DATABASE",
        failure_type="DATABASE_CONNECTION_EXHAUSTION",
        limit=2,
        tenant_id="shopsphere"
    )
    print(f"\n--- HISTORICAL CBR MEMORY RECALL ---")
    print(f"Matches found: {len(matches)}")
    if matches:
        print(f"Top match incident ID: {matches[0].get('incident_id')}")
        print(f"Remediation: {matches[0].get('remediation_action')}")
        print(f"Verification: {matches[0].get('verification_status')}")

if __name__ == "__main__":
    asyncio.run(run_live_demo())
