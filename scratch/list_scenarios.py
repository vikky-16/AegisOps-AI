import sys
sys.path.insert(0, ".")
from backend.app.replica.controlled_environment import SCENARIO_DEFINITIONS

print(f"Total scenario definitions: {len(SCENARIO_DEFINITIONS)}")
for sid, sdata in SCENARIO_DEFINITIONS.items():
    print(f"- {sid}: {sdata.get('name')} (Target: {sdata.get('target_service')})")
    print(f"    Root Cause: {sdata.get('ground_truth_root_cause')}")
    print(f"    Available Actions: {[k for k in sdata.get('actions_model', {}).keys()]}")
