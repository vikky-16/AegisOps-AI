"""
Unit Tests for High-Throughput Log Intelligence & Fingerprint Grouping
Verifies 10,000+ log batching, deduplication, and ring-buffer querying.
"""

import pytest
from backend.app.logs.processor import LogBatchProcessor, generate_simulated_logs


@pytest.mark.asyncio
async def test_generate_and_ingest_10000_logs():
    processor = LogBatchProcessor(buffer_size=10000)
    
    # 1. Generate 10,000 simulated logs under database_storm scenario
    logs = generate_simulated_logs(count=10000, scenario="database_storm")
    assert len(logs) == 10000

    # 2. Ingest batch
    res = await processor.ingest_batch(logs)
    assert res["ingested_count"] == 10000
    assert res["total_logs"] == 10000

    # 3. Verify deduplicated fingerprints
    fps = processor.get_fingerprints()
    assert len(fps) > 0
    # The 60% database timeouts (6000 total) are grouped by level (5400 ERROR + 600 CRITICAL)
    db_fps = [f for f in fps if f["event_type"] == "DATABASE_TIMEOUT"]
    assert len(db_fps) > 0
    assert sum(f["occurrences"] for f in db_fps) == 6000

    # 4. Verify pagination query
    query_res = processor.query_logs(page=1, page_size=50, level="CRITICAL")
    assert len(query_res["items"]) <= 50
    assert query_res["total"] > 0
    assert all(item["level"] == "CRITICAL" for item in query_res["items"])

    # 5. Verify search query
    search_res = processor.query_logs(page=1, page_size=25, search="pool exhausted")
    assert len(search_res["items"]) <= 25
    assert search_res["total"] == 6000


@pytest.mark.asyncio
async def test_fingerprint_grouping_prevents_log_storms():
    processor = LogBatchProcessor(buffer_size=5000)
    
    # Ingest 5,000 identical error logs
    identical_logs = [
        {
            "timestamp": "2026-08-18T12:00:00Z",
            "service": "service-b",
            "level": "ERROR",
            "event_type": "PAYMENT_GATEWAY_TIMEOUT",
            "message": "Gateway connection timed out after 3000ms",
            "trace_id": f"trace-{i}",
            "metadata": {"attempt": i}
        }
        for i in range(5000)
    ]

    await processor.ingest_batch(identical_logs)
    fps = processor.get_fingerprints()
    
    # 5,000 logs must produce exactly 1 grouped fingerprint
    assert len(fps) == 1
    assert fps[0]["occurrences"] == 5000
    assert fps[0]["event_type"] == "PAYMENT_GATEWAY_TIMEOUT"
    assert fps[0]["service"] == "service-b"
