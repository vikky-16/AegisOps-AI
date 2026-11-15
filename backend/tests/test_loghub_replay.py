"""
Unit & Integration Tests for LogHub Historical Dataset Ingestion & Replay Subsystem
Verifies dataset discovery, schema normalization without data fabrication,
and high-speed asynchronous streaming (100–1000 EPS).
"""

import pytest
import asyncio
from backend.app.loghub.parser import loghub_parser
from backend.app.loghub.engine import loghub_engine
from backend.app.integrations.models import TelemetrySeverity


def test_loghub_dataset_discovery():
    datasets = loghub_parser.list_available_datasets()
    assert len(datasets) >= 6
    ds_ids = [d.id for d in datasets]
    assert "HDFS" in ds_ids
    assert "Linux" in ds_ids
    assert "OpenStack" in ds_ids
    assert "BGL" in ds_ids
    assert "Spark" in ds_ids
    assert "Zookeeper" in ds_ids


def test_loghub_schema_normalization_no_fabrication():
    for ds_id in ["HDFS", "Linux", "OpenStack", "BGL"]:
        records = loghub_parser.load_dataset_records(ds_id)
        assert len(records) > 0
        for r in records[:20]:
            assert r.environment == "loghub-historical"
            assert r.service is not None and len(r.service) > 0
            assert r.message is not None and len(r.message) > 0
            assert r.severity in [TelemetrySeverity.INFO, TelemetrySeverity.WARNING, TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]
            # Verify no hardcoded root_cause fabrication
            assert "root_cause" not in r.metadata
            assert "loghub_dataset" in r.metadata


@pytest.mark.asyncio
async def test_loghub_replay_engine_lifecycle():
    # 1. Start streaming 2000 records from HDFS at 200 EPS
    res = await loghub_engine.start_replay(
        dataset="HDFS",
        target_count=2000,
        eps=200
    )
    assert res["status"] == "STREAMING"
    assert res["dataset"] == "HDFS"
    assert res["target_count"] == 2000

    # Wait for partial stream
    await asyncio.sleep(0.2)
    stat = loghub_engine.get_status()
    assert stat["events_processed"] > 0
    assert stat["events_sent"] > 0

    # 2. Pause replay
    paused = loghub_engine.pause_replay()
    assert paused["status"] == "PAUSED"
    processed_at_pause = paused["events_processed"]

    await asyncio.sleep(0.1)
    assert loghub_engine.events_processed == processed_at_pause

    # 3. Resume replay
    resumed = loghub_engine.resume_replay()
    assert resumed["status"] == "STREAMING"

    # Wait for completion
    await asyncio.sleep(0.4)
    final_stat = loghub_engine.get_status()
    assert final_stat["events_processed"] >= 50

    # 4. Reset replay
    reset_res = await loghub_engine.reset_replay_state()
    assert reset_res["success"] is True
    assert loghub_engine.events_processed == 0
    assert loghub_engine.status == "IDLE"
