import sys
sys.path.insert(0, ".")
import asyncio
from backend.app.replica.controlled_environment import replica_environment, SCENARIO_DEFINITIONS
from backend.app.healing.solution_generator import solution_generator
from backend.app.validation.validator import recovery_validator
from backend.app.healing.closed_loop_engine import closed_loop_engine

async def evaluate_scenario(sid):
    scen = SCENARIO_DEFINITIONS[sid]
    print(f"\n=======================================================")
    print(f"SCENARIO: {sid} ({scen['name']})")
    
    # 1. Candidate solutions generated for this scenario
    hyp = {"hypothesis": scen["ground_truth_root_cause"], "confidence": 0.95}
    candidates = solution_generator.generate_candidate_solutions(hyp, sid, "demo-tenant")
    print(f"Generated {len(candidates)} candidates:")
    for idx, c in enumerate(candidates):
        print(f"  {idx+1}. {c['action']} (risk={c.get('risk')}, confidence={c.get('confidence')})")

    # 2. Closed-Loop execution
    res = await closed_loop_engine.execute_closed_loop(scenario_id=sid, tenant_id="demo-tenant")
    print(f"Closed-Loop Final State: {res.get('lifecycle_state')}")
    print(f"Iteration Count: {res.get('iteration_count')}")
    history = res.get("execution_history", [])
    for h in history:
        print(f"  Attempt {h['iteration']}: Action={h['action']} -> Validated={h['solution_validated']} (ErrorResolved={h['original_error_resolved']}, SideEffects={len(h.get('side_effects', []))})")

async def main():
    for sid in sorted(SCENARIO_DEFINITIONS.keys()):
        await evaluate_scenario(sid)

if __name__ == "__main__":
    asyncio.run(main())
