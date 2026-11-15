"""
Tests for Phase 2 Service Dependency Discovery, Dynamic Graph, Confidence Scoring, and Blast Radius Analysis
"""

import pytest
from backend.app.rca.dynamic_graph import DynamicDependencyGraph, dynamic_graph


def test_service_dependency_creation_and_discovery():
    """Verify dynamic service dependency creation and baseline topology."""
    graph = DynamicDependencyGraph()
    assert len(graph.services) >= 5
    assert "gateway" in graph.services
    assert "service-a" in graph.services
    assert "service-b" in graph.services
    assert "database-service" in graph.services

    # Check dependency edge
    deps = graph.get_dependencies("gateway")
    target_names = [d["target_service"] for d in deps]
    assert "service-a" in target_names


def test_dependency_confidence_calculation_and_updates():
    """Verify confidence score increases with observed request volume and failure correlation."""
    graph = DynamicDependencyGraph()
    
    # Add new inferred dependency with low observation count
    edge = graph.add_or_update_dependency(
        source="custom-service",
        target="cache",
        relationship_type="CACHE_ACCESS",
        observation_count=5,
        correlated_failures_count=0,
        status="INFERRED"
    )
    assert edge["confidence"] >= 0.80
    assert edge["status"] == "INFERRED"
    assert len(edge["evidence"]) >= 2

    # Simulate 150 observed requests and 4 cascade failures
    updated_edge = graph.add_or_update_dependency(
        source="custom-service",
        target="cache",
        observation_count=150,
        correlated_failures_count=4
    )
    assert updated_edge["confidence"] >= 0.95
    assert updated_edge["status"] == "VALIDATED"
    assert "155 observed service-to-service requests" in updated_edge["evidence"][0]


def test_graph_downstream_dependents_and_traversal():
    """Verify recursive traversal of upstream callers that depend on a failing service."""
    graph = DynamicDependencyGraph()
    
    # Who breaks if database-service fails?
    dependents = graph.get_dependents("database-service")
    assert "service-b" in dependents
    assert "service-a" in dependents
    assert "gateway" in dependents

    # Ingress gateway has no upstream dependents
    gw_dependents = graph.get_dependents("gateway")
    assert len(gw_dependents) == 0


def test_blast_radius_calculation_and_score():
    """Verify direct impact, downstream cascade impact, and blast radius scoring."""
    graph = DynamicDependencyGraph()

    blast = graph.calculate_blast_radius(
        failing_service="database-service",
        error_rate=0.90,
        request_count=150
    )

    assert blast["failing_service"] == "database-service"
    assert blast["direct_impact"] == ["database-service"]
    assert "service-b" in blast["downstream_impact"]
    assert "gateway" in blast["downstream_impact"]
    assert blast["affected_services_count"] >= 3
    assert blast["impact_level"] == "CRITICAL"
    assert blast["blast_radius_score"] >= 80.0
    assert blast["affected_requests"] > 0
    assert blast["customer_facing"] is True


def test_live_service_health_status_updates():
    """Verify live status transitions between HEALTHY, DEGRADED, FAILED, and UNKNOWN."""
    graph = DynamicDependencyGraph()
    
    graph.update_service_health("database-service", "CRASHED")
    assert graph.services["database-service"]["status"] == "FAILED"

    graph.update_service_health("database-service", "DEGRADED")
    assert graph.services["database-service"]["status"] == "DEGRADED"

    graph.update_service_health("database-service", "HEALTHY")
    assert graph.services["database-service"]["status"] == "HEALTHY"
