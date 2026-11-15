import asyncio
import httpx
from unittest.mock import patch
from backend.app.monitoring.collector import collector

class MockResp:
    def __init__(self, code, data):
        self.status_code = code
        self._data = data
    def json(self):
        return self._data
    @property
    def text(self):
        return str(self._data)

async def mock_get(url, **kwargs):
    url_s = str(url)
    if "/work" in url_s:
        return MockResp(200, {"status": "SUCCESS"})
    if "/health" in url_s:
        return MockResp(200, {"status": "HEALTHY", "state": "HEALTHY"})
    if "/metrics" in url_s:
        return MockResp(200, {"error_rate": 0.0, "latency_p95_ms": 10.0, "cpu_percent": 15.0})
    return MockResp(200, {})

async def mock_post(url, **kwargs):
    return MockResp(200, {"success": True, "result": "Connection pool reset successfully"})

async def main():
    incident = {
        "incident_id": "INC-TEST-999",
        "severity": "CRITICAL",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "gateway"],
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.95,
        "timeline": []
    }
    rec_result = {
        "primary_action": "RESET_CONNECTION_POOL",
        "expected_outcome": "Restores pool"
    }
    collector.active_incidents = [incident]
    ticket = collector._create_approval_ticket(incident, rec_result)
    print("Ticket created:", ticket)

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        res = await collector.execute_approved_action(
            approval_id=ticket["approval_id"],
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="Testing"
        )
        print("execute_approved_action res:", res)

if __name__ == "__main__":
    asyncio.run(main())
