import urllib.request
import json
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

API_BASE = 'http://127.0.0.1:8000/api'

# 1. Fetch Incidents
req = urllib.request.urlopen(f'{API_BASE}/incidents')
incidents = json.loads(req.read().decode())
print(f'1. Incidents fetched: {len(incidents)} incidents found.')
inc_id = incidents[0]['incident_id'] if incidents else 'INC-20261008-001'

# 2. Fetch RCA for active incident
req = urllib.request.urlopen(f'{API_BASE}/incidents/{inc_id}/rca')
rca = json.loads(req.read().decode())
print(f'2. RCA data loaded for {inc_id}:')
print(f'   - Root Cause Service: {rca.get("root_cause_service")}')
print(f'   - Confidence: {rca.get("confidence")} ({rca.get("confidence_tier")})')
lineage_steps = rca.get('evidence_lineage', {}).get('lineage_steps', [])
print(f'   - Evidence Lineage Steps: {len(lineage_steps)} nodes')
for s in lineage_steps:
    print(f'     [{s.get("type")}] {s.get("node_id")}: {s.get("title")}')
dec_scores = rca.get('decision_scores', [])
print(f'   - Recovery Decision Scores: {len(dec_scores)} candidates evaluated')
for ds in dec_scores[:3]:
    print(f'     * {ds.get("action")}: Match={ds.get("root_cause_match_pct")}% | Composite={ds.get("composite_score")} | Decision={ds.get("decision")}')

# 3. Verified Recovery Patterns
req = urllib.request.urlopen(f'{API_BASE}/incidents/recovery/verified-patterns')
pats = json.loads(req.read().decode())
print(f'3. Verified Recovery Knowledge:')
print(f'   - Total persistent patterns in store: {len(pats.get("patterns", []))}')
for p in pats.get('patterns', [])[:2]:
    print(f'     * Pattern {p.get("pattern_id")}: {p.get("verified_recovery_action")} ({p.get("previous_validation")})')

# 4. Run Isolated Sandbox Cycle
print(f'4. Initializing & Running Sandbox Cycle for {inc_id}...')
post_data = json.dumps({'action': 'RESET_CONNECTION_POOL'}).encode('utf-8')
req = urllib.request.Request(f'{API_BASE}/incidents/{inc_id}/sandbox/run-cycle', data=post_data, headers={'Content-Type': 'application/json'})
res = urllib.request.urlopen(req)
sbx_res = json.loads(res.read().decode())
sbx = sbx_res.get('sandbox', {})
print(f'   - Sandbox ID: {sbx.get("sandbox_id")}')
print(f'   - Final Outcome: {sbx.get("final_outcome")}')
print(f'   - Verified Pattern ID: {sbx.get("verified_pattern_id")}')

# 5. Fetch Recovery Proof
req = urllib.request.urlopen(f'{API_BASE}/incidents/{inc_id}/sandbox/proof')
proof_res = json.loads(req.read().decode())
proof = proof_res.get('proof') if isinstance(proof_res.get('proof'), dict) else proof_res
print(f'5. Recovery Proof Report:')
print(f'   - Proof ID: {proof.get("proof_id")}')
print(f'   - Status: {proof.get("final_status")}')
print(f'   - Validation Criteria: {len(proof.get("validation_criteria", []))} criteria evaluated')

# 6. Chat with SRE Assistant
print(f'6. SRE Assistant Operational Queries:')
for query in ['Why did recovery attempt 1 fail?', 'Compare attempt 1 and attempt 2.', 'Has this happened before?']:
    post_chat = json.dumps({'message': query, 'incident_id': inc_id}).encode('utf-8')
    req = urllib.request.Request(f'{API_BASE}/sre-assistant/chat', data=post_chat, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    chat_res = json.loads(res.read().decode())
    print(f'   [Q]: {query}')
    print(f'   [Mode]: {chat_res.get("mode")}')
    print(f'   [A]: {chat_res.get("answer")[:140]}...')

print('\nALL RUNTIME HTTP VERIFICATIONS CONFIRMED OPERATIONAL!')
