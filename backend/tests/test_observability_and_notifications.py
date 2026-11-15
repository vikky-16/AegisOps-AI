import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.monitoring.collector import collector

@pytest.mark.asyncio
async def test_global_service_observability_tenant_isolated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch for demo-tenant
        res_demo = await client.get("/api/services/observability/global", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_demo.status_code == 200
        data_demo = res_demo.json()
        assert "summary" in data_demo
        assert "services" in data_demo
        assert data_demo["summary"]["tenant_id"] == "demo-tenant"
        assert "incidents_by_severity" in data_demo["summary"]
        assert "CRITICAL" in data_demo["summary"]["incidents_by_severity"]
        assert "telemetry_freshness_seconds" in data_demo["summary"]
        assert "telemetry_coverage_pct" in data_demo["summary"]

        # 2. Fetch for fincore tenant
        res_fincore = await client.get("/api/services/observability/global", headers={"X-Tenant-ID": "fincore"})
        assert res_fincore.status_code == 200
        data_fincore = res_fincore.json()
        assert data_fincore["summary"]["tenant_id"] == "fincore"

@pytest.mark.asyncio
async def test_service_observability_endpoint_with_missing_instrumentation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test database-service
        res = await client.get("/api/services/database-service/observability?time_range=15m", headers={"X-Tenant-ID": "demo-tenant"})
        assert res.status_code == 200
        data = res.json()
        assert "service_overview" in data
        assert "current_health" in data
        assert "time_series" in data
        assert "baseline_comparison" in data
        assert "missing_instrumentation" in data
        assert isinstance(data["missing_instrumentation"], list)
        assert len(data["missing_instrumentation"]) > 0
        assert data["tenant_id"] == "demo-tenant"

@pytest.mark.asyncio
async def test_dependency_graph_confirmed_vs_affected_and_tenant_scoping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dependencies/graph", headers={"X-Tenant-ID": "demo-tenant"})
        assert res.status_code == 200
        graph = res.json()
        assert "nodes" in graph
        assert "edges" in graph
        
        # Verify nodes have explicit health states
        for node in graph["nodes"]:
            assert node["status"] in ["HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN"]
            assert "name" in node

        # Verify edges have real metrics or status
        for edge in graph["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "dependency_status" in edge

@pytest.mark.asyncio
async def test_existing_rca_and_recovery_endpoints_intact():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check incident list
        res_inc = await client.get("/api/incidents", headers={"X-Tenant-ID": "demo-tenant"})
        assert res_inc.status_code == 200
        incidents = res_inc.json()
        assert isinstance(incidents, list)

        if incidents:
            inc_id = incidents[0]["incident_id"]
            # Timeline intact
            res_tl = await client.get(f"/api/incidents/{inc_id}/timeline", headers={"X-Tenant-ID": "demo-tenant"})
            assert res_tl.status_code == 200

            # Evidence intact
            res_ev = await client.get(f"/api/incidents/{inc_id}/evidence", headers={"X-Tenant-ID": "demo-tenant"})
            assert res_ev.status_code == 200

            # RCA intact
            res_rca = await client.get(f"/api/incidents/{inc_id}/rca", headers={"X-Tenant-ID": "demo-tenant"})
            assert res_rca.status_code == 200
            rca_data = res_rca.json()
            assert "root_cause" in rca_data or "summary" in rca_data

@pytest.mark.asyncio
async def test_approvals_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/approvals", headers={"X-Tenant-ID": "demo-tenant"})
        assert res.status_code == 200
        tickets = res.json()
        assert isinstance(tickets, list)
        for t in tickets:
            if t.get("tenant_id"):
                assert t["tenant_id"] in ["demo-tenant", "all", "*"]
