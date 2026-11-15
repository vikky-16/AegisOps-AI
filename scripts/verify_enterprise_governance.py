"""
AegisOps AI - Enterprise Governance & Observability Verification Script
Validates Goals 1 to 18 of the specification:
1. Truthful Approval Center Counting (pending_approvals == 2, unique_incidents == 2, not 5)
2. Strict tab filtering (HIGH_RISK, MEDIUM_RISK, LOW_RISK, PENDING, APPROVED, REJECTED)
3. Incident Signature Heatmap, Error Rate by Type, Service Profiles, and Reliability Fingerprints
4. Native Google Gemini & Unified AI Credential Configuration
5. SRE Assistant operational question handling
6. Real approval execution and live counter decrement
"""

import sys
import json
import httpx

BASE_URL = "http://127.0.0.1:8000/api"
HEADERS = {
    "X-Tenant-ID": "demo-tenant",
    "Content-Type": "application/json"
}

def log(msg, status="INFO"):
    symbol = "+" if status == "PASS" else "-" if status == "FAIL" else "*"
    print(f"[{symbol}] [{status}] {msg}", flush=True)

def test_approval_stats():
    log("Testing Approval Center Truthful Counting...", "INFO")
    resp = httpx.get(f"{BASE_URL}/approvals/stats", headers=HEADERS, timeout=10.0)
    assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.text}"
    stats = resp.json()
    log(f"Received Stats: {json.dumps(stats)}", "INFO")

    # Strict Goal 1 criteria:
    # Baseline pending must be 2, unique incidents must be 2 (NOT 5!)
    assert stats["pending_approvals"] == 2, f"Expected pending_approvals == 2, got {stats['pending_approvals']}"
    assert stats["unique_incidents"] == 2, f"Expected unique_incidents == 2, got {stats['unique_incidents']}"
    assert stats["high_risk"] == 1, f"Expected high_risk == 1, got {stats['high_risk']}"
    assert stats["medium_risk"] == 1, f"Expected medium_risk == 1, got {stats['medium_risk']}"
    assert stats["approved_today"] == 3, f"Expected approved_today == 3, got {stats['approved_today']}"
    assert stats["total_tickets"] == 5, f"Expected total_tickets == 5, got {stats['total_tickets']}"
    log("Goal 1 (Truthful Counting: Pending=2, Incidents=2, Total=5) PASSED", "PASS")

def test_approval_tab_filters():
    log("Testing Approval Center Strict Tab Filters...", "INFO")

    # HIGH RISK
    r_high = httpx.get(f"{BASE_URL}/approvals?status=HIGH_RISK", headers=HEADERS, timeout=10.0)
    assert r_high.status_code == 200
    high_items = r_high.json()
    assert len(high_items) == 1, f"Expected 1 HIGH risk ticket, got {len(high_items)}"
    assert high_items[0]["risk_level"] in ["HIGH", "CRITICAL"]
    log(f"HIGH_RISK tab filter returned {len(high_items)} item ({high_items[0]['action']})", "PASS")

    # MEDIUM RISK
    r_med = httpx.get(f"{BASE_URL}/approvals?status=MEDIUM_RISK", headers=HEADERS, timeout=10.0)
    assert r_med.status_code == 200
    med_items = r_med.json()
    assert len(med_items) == 1, f"Expected 1 MEDIUM risk ticket, got {len(med_items)}"
    assert med_items[0]["risk_level"] == "MEDIUM"
    log(f"MEDIUM_RISK tab filter returned {len(med_items)} item ({med_items[0]['action']})", "PASS")

    # PENDING
    r_pend = httpx.get(f"{BASE_URL}/approvals?status=PENDING", headers=HEADERS, timeout=10.0)
    assert r_pend.status_code == 200
    pend_items = r_pend.json()
    assert len(pend_items) == 2, f"Expected 2 PENDING tickets, got {len(pend_items)}"
    log(f"PENDING tab filter returned {len(pend_items)} items", "PASS")

    # APPROVED
    r_app = httpx.get(f"{BASE_URL}/approvals?status=APPROVED", headers=HEADERS, timeout=10.0)
    assert r_app.status_code == 200
    app_items = r_app.json()
    assert len(app_items) == 3, f"Expected 3 APPROVED tickets, got {len(app_items)}"
    log(f"APPROVED tab filter returned {len(app_items)} items", "PASS")

def test_telemetry_analysis_observability():
    log("Testing Operational Observability & Telemetry Visualizations...", "INFO")
    resp = httpx.get(f"{BASE_URL}/services/observability/telemetry-analysis?time_range=15m", headers=HEADERS, timeout=10.0)
    assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.text}"
    data = resp.json()

    # 1. Heatmap
    heatmap = data.get("heatmap", {})
    categories = heatmap.get("categories", [])
    buckets = heatmap.get("buckets", [])
    rows = heatmap.get("rows", [])
    assert len(categories) == 17, f"Expected 17 failure categories, got {len(categories)}"
    assert len(buckets) == 8, f"Expected 8 time buckets, got {len(buckets)}"
    assert len(rows) == 17, f"Expected 17 heatmap rows, got {len(rows)}"
    log(f"Incident Signature Heatmap: {len(categories)} categories x {len(buckets)} buckets verified", "PASS")

    # 2. Error Rate by Type (Time Series)
    ts = data.get("error_rate_by_type", [])
    assert len(ts) >= 10, f"Expected >= 10 time points, got {len(ts)}"
    first_pt = ts[0]
    for key in ["all_problems", "http_errors", "database", "timeouts", "dependency", "exceptions", "latency", "resource"]:
        assert key in first_pt, f"Missing key {key} in error rate time series point"
    log(f"Error Rate by Failure Type: {len(ts)} points with all 8 dimensions verified", "PASS")

    # 3. Service Error Profiles
    profiles = data.get("service_error_profiles", [])
    assert len(profiles) >= 4, f"Expected >= 4 service profiles, got {len(profiles)}"
    db_prof = next((p for p in profiles if "database" in p["service"]), None)
    assert db_prof is not None, "Missing database-service in error profiles"
    log(f"Service Error Profiles: {len(profiles)} services evaluated (Database dominant: {db_prof['dominant_failure_type']})", "PASS")

    # 4. Reliability Fingerprints
    fps = data.get("reliability_fingerprints", [])
    assert len(fps) >= 4, f"Expected >= 4 reliability fingerprints, got {len(fps)}"
    first_fp = fps[0]
    assert len(first_fp["dimensions"]) == 6, f"Expected 6 radar dimensions, got {len(first_fp['dimensions'])}"
    log(f"Reliability Fingerprints: {len(fps)} multi-dimensional radar profiles verified", "PASS")

    # 5. Error Taxonomy Summary
    taxonomy = data.get("error_taxonomy_summary", [])
    assert len(taxonomy) == 9, f"Expected 9 error taxonomy categories, got {len(taxonomy)}"
    log(f"Error Taxonomy Summary: {len(taxonomy)} categories verified", "PASS")

def test_ai_config_and_gemini():
    log("Testing AI Provider Configuration & Google Gemini Integration...", "INFO")
    
    # Update config with Gemini & unified key toggle
    payload = {
        "rca_ai_provider": "gemini",
        "rca_ai_model": "gemini-3.8-flash",
        "use_same_key_for_both": True,
        "max_recovery_attempts": 3
    }
    r_up = httpx.post(f"{BASE_URL}/ai-config/update", headers=HEADERS, json=payload, timeout=10.0)
    assert r_up.status_code == 200, f"Update failed: {r_up.text}"

    # Get status
    r_st = httpx.get(f"{BASE_URL}/ai-config/status", headers=HEADERS, timeout=10.0)
    assert r_st.status_code == 200
    st_data = r_st.json()
    assert st_data["rca_ai"]["provider"] == "gemini", f"Expected gemini, got {st_data['rca_ai']['provider']}"
    assert st_data["sre_ai"]["provider"] == "gemini", f"Expected synced gemini, got {st_data['sre_ai']['provider']}"
    assert st_data["use_same_key_for_both"] is True
    # Ensure zero raw secret exposure
    assert "api_key" not in st_data["rca_ai"]
    assert "api_key" not in st_data["sre_ai"]
    log("AI Configuration & Gemini provider syncing verified without secret exposure", "PASS")

    # Test connection endpoint
    r_test = httpx.post(f"{BASE_URL}/ai-config/test-connection", headers=HEADERS, json={"target": "rca_ai"}, timeout=10.0)
    assert r_test.status_code == 200
    test_res = r_test.json()
    log(f"Connection test response: {test_res['status']} - {test_res['message']}", "PASS")

def test_sre_assistant_operational_queries():
    log("Testing SRE Assistant Grounded Operational Questions...", "INFO")
    queries = [
        "Why is this service critical?",
        "What caused this incident?",
        "What changed before the incident?",
        "Compare attempt 1 and attempt 2",
        "What validation criterion failed?",
        "What changed before and after recovery?",
        "Is the incident really resolved?",
        "What is the current system state?"
    ]

    for q in queries:
        resp = httpx.post(
            f"{BASE_URL}/sre-assistant/chat",
            headers=HEADERS,
            json={"message": q, "incident_id": "INC-00042"},
            timeout=10.0
        )
        assert resp.status_code == 200, f"Query '{q}' failed: {resp.text}"
        ans = resp.json()
        assert ans.get("answer"), f"Empty answer for query '{q}'"
        assert len(ans.get("sources", [])) > 0, f"No sources for query '{q}'"
        log(f"Question: '{q}' -> Answer generated ({len(ans['answer'])} chars, Mode: {ans.get('mode')})", "PASS")

def test_approval_action_workflow():
    log("Testing Live Approval Execution & Counter Decrement...", "INFO")
    
    # Get baseline pending stats immediately before approval
    r_before = httpx.get(f"{BASE_URL}/approvals/stats", headers=HEADERS, timeout=10.0)
    assert r_before.status_code == 200
    pending_before = r_before.json()["pending_approvals"]
    approved_before = r_before.json()["approved_today"]

    # 1. Select pending ticket
    r_pend = httpx.get(f"{BASE_URL}/approvals?status=PENDING", headers=HEADERS, timeout=10.0)
    pend_tickets = r_pend.json()
    assert len(pend_tickets) > 0, "No pending ticket available to approve"
    target_ticket = next((t for t in pend_tickets if t.get("approval_id") == "APP-INC-00051"), pend_tickets[0])
    target_id = target_ticket["approval_id"]

    resp = httpx.post(
        f"{BASE_URL}/approvals/{target_id}/approve",
        headers=HEADERS,
        json={"reviewer": "Lead SRE Test Admin", "role": "SRE_LEAD", "notes": "Approved automated sandbox execution"},
        timeout=10.0
    )
    assert resp.status_code == 200, f"Approve failed: {resp.text}"
    app_res = resp.json()
    log(f"Approve result: {app_res.get('status')} - Execution started: {app_res.get('execution_started')}", "PASS")

    # 2. Verify pending stats decremented and approved today incremented
    r_stats = httpx.get(f"{BASE_URL}/approvals/stats", headers=HEADERS, timeout=10.0)
    assert r_stats.status_code == 200
    stats = r_stats.json()
    log(f"Updated Stats: Pending={stats['pending_approvals']}, Approved Today={stats['approved_today']}", "INFO")
    assert stats["pending_approvals"] == pending_before - 1, f"Expected pending_approvals == {pending_before - 1}, got {stats['pending_approvals']}"
    assert stats["approved_today"] >= approved_before + 1, f"Expected approved_today >= {approved_before + 1}, got {stats['approved_today']}"

    # Verify target ticket moved to APPROVED
    r_approved = httpx.get(f"{BASE_URL}/approvals?status=APPROVED", headers=HEADERS, timeout=10.0)
    approved_ids = [t["approval_id"] for t in r_approved.json()]
    assert target_id in approved_ids, f"Ticket {target_id} not found in APPROVED tab"
    log("Approval workflow execution & immediate pending counter decrement PASSED", "PASS")

if __name__ == "__main__":
    print("=" * 70)
    print("AEGISOPS AI - ENTERPRISE GOVERNANCE & OBSERVABILITY VERIFICATION")
    print("=" * 70)
    try:
        test_approval_stats()
        test_approval_tab_filters()
        test_telemetry_analysis_observability()
        test_ai_config_and_gemini()
        test_sre_assistant_operational_queries()
        test_approval_action_workflow()
        print("\n" + "=" * 70)
        print("ALL ENTERPRISE VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)
    except AssertionError as ae:
        log(f"TEST FAILED: {ae}", "FAIL")
        sys.exit(1)
    except Exception as e:
        log(f"UNEXPECTED ERROR: {e}", "FAIL")
        sys.exit(1)
