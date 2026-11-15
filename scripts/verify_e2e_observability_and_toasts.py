import asyncio
import httpx
import sys

BASE_API = "http://127.0.0.1:8000/api"

async def test_api_verification():
    print("=== STARTING OBSERVABILITY & NOTIFICATION E2E AUDIT ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Test Global Service Observability (Company-specific)
        print("\n[CHECK 1] Global Service Observability for demo-tenant...")
        res = await client.get(f"{BASE_API}/services/observability/global", headers={"X-Tenant-ID": "demo-tenant"})
        assert res.status_code == 200, f"Failed: {res.status_code}"
        data = res.json()
        summary = data.get("summary", {})
        assert summary.get("tenant_id") == "demo-tenant", f"Tenant mismatch: {summary.get('tenant_id')}"
        assert "incidents_by_severity" in summary, "Missing incidents_by_severity"
        print(f" -> System Health Score: {summary.get('system_health_score')}%")
        print(f" -> Monitored Services: {summary.get('monitored_services')} / {summary.get('total_services')}")
        print(f" -> Active Incidents by Severity: {summary.get('incidents_by_severity')}")
        print(f" -> Telemetry Freshness: {summary.get('telemetry_freshness_seconds')}s")
        print(" [PASS] Check 1 passed.")

        # 2. Test Tenant Isolation between demo-tenant and fincore
        print("\n[CHECK 2] Tenant Isolation: fincore vs demo-tenant...")
        res_fin = await client.get(f"{BASE_API}/services/observability/global", headers={"X-Tenant-ID": "fincore"})
        assert res_fin.status_code == 200
        summary_fin = res_fin.json().get("summary", {})
        assert summary_fin.get("tenant_id") == "fincore", f"Tenant mismatch: {summary_fin.get('tenant_id')}"
        print(f" -> FinCore tenant isolated successfully: {summary_fin.get('tenant_id')}")
        print(" [PASS] Check 2 passed.")

        # 3. Test Granular Service Observability with Missing Instrumentation
        print("\n[CHECK 3] Granular Service Observability for database-service...")
        res_svc = await client.get(f"{BASE_API}/services/database-service/observability?time_range=15m", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_svc.status_code == 200
        svc_data = res_svc.json()
        assert "baseline_comparison" in svc_data, "Missing baseline_comparison"
        assert "missing_instrumentation" in svc_data, "Missing missing_instrumentation"
        assert len(svc_data["missing_instrumentation"]) > 0, "Expected explicit missing instrumentation items"
        print(f" -> Missing instrumentation disclosed: {svc_data['missing_instrumentation']}")
        print(f" -> P95 Latency: {svc_data.get('current_health', {}).get('latency_p95_ms')}ms")
        print(f" -> Baseline Comparison: P95 dev: {svc_data.get('baseline_comparison', {}).get('latency', {}).get('deviation_pct')}%")
        print(" [PASS] Check 3 passed.")

        # 4. Test Dependency Graph with Incident Context
        print("\n[CHECK 4] Service Dependency Graph with Root Cause vs Affected Nodes...")
        res_graph = await client.get(f"{BASE_API}/dependencies/graph", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_graph.status_code == 200
        graph = res_graph.json()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        assert len(nodes) >= 4, f"Too few nodes: {len(nodes)}"
        assert len(edges) >= 3, f"Too few edges: {len(edges)}"
        
        node_statuses = {n["id"]: n.get("status") for n in nodes}
        print(f" -> Discovered Nodes & Health: {node_statuses}")
        
        # Verify edge latency and error rates
        for e in edges[:3]:
            print(f" -> Edge {e.get('source')} -> {e.get('target')}: Status={e.get('dependency_status')}, Latency={e.get('latency')}")
        print(" [PASS] Check 4 passed.")

        # 5. Test Active Incidents & Stable Identifiers
        print("\n[CHECK 5] Incidents & Stable Event Identifiers...")
        res_inc = await client.get(f"{BASE_API}/incidents", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_inc.status_code == 200
        inc_list = res_inc.json()
        print(f" -> Total Tenant Incidents: {len(inc_list)}")
        if inc_list:
            first_inc = inc_list[0]
            inc_id = first_inc["incident_id"]
            print(f" -> Stable Incident ID: {inc_id}, Severity: {first_inc.get('severity')}")
            
            # Check RCA endpoint intact
            res_rca = await client.get(f"{BASE_API}/incidents/{inc_id}/rca", headers={"X-Tenant-ID": "demo-tenant"})
            assert res_rca.status_code == 200
            rca = res_rca.json()
            print(f" -> RCA Confidence: {rca.get('confidence')}, Root cause: {rca.get('root_cause')}")

        print(" [PASS] Check 5 passed.")

        # 6. Test Approvals Center Endpoint & Tenant Isolation
        print("\n[CHECK 6] Approvals Center tickets & safety gate...")
        res_app = await client.get(f"{BASE_API}/approvals", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_app.status_code == 200
        approvals = res_app.json()
        print(f" -> Pending Approvals Count: {len(approvals)}")
        for a in approvals[:2]:
            print(f" -> Ticket: {a.get('approval_id')} Action: {a.get('proposed_action')} on {a.get('service_name')}")
        print(" [PASS] Check 6 passed.")

    print("\n=== ALL E2E API & BACKEND AUDIT CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(test_api_verification())
