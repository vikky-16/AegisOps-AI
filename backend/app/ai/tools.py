"""
AegisOps AI - Internal Tool Execution Engine for AI Assistant
Provides controlled, read-only tools to retrieve real-time context without hallucination.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.kafka.health import kafka_health_tracker
from backend.app.rca.dynamic_graph import dynamic_graph
from backend.app.storage.manager import storage_manager
from backend.app.ai.baselines import baseline_manager
from backend.app.knowledge.incident_memory import incident_memory


class AssistantToolRegistry:
    def __init__(self):
        self.tool_call_logs: List[Dict[str, Any]] = []

    def log_call(self, tool_name: str, arguments: Dict[str, Any], result_summary: str):
        self.tool_call_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": result_summary
        })
        if len(self.tool_call_logs) > 100:
            self.tool_call_logs.pop()

    def get_active_incidents(self, active_incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.log_call("get_active_incidents", {}, f"Retrieved {len(active_incidents)} active incidents")
        return [
            {
                "incident_id": i.get("incident_id"),
                "title": i.get("title"),
                "severity": i.get("severity"),
                "status": i.get("status"),
                "root_cause_service": i.get("root_cause_service"),
                "affected_services": i.get("affected_services"),
                "recommended_action": i.get("recommended_action")
            }
            for i in active_incidents
        ]

    def get_incident(self, incident_id: str, incidents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        match = next((i for i in incidents if i.get("incident_id") == incident_id), None)
        self.log_call("get_incident", {"incident_id": incident_id}, "Found" if match else "Not found")
        return match

    def get_service_health(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        topo = dynamic_graph.get_topology_graph()
        self.log_call("get_service_health", {"service_name": service_name}, f"Returned {len(topo.get('nodes', []))} nodes")
        return topo

    def get_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        deps = dynamic_graph.get_dependencies(service_name)
        dependents = dynamic_graph.get_dependents(service_name)
        self.log_call("get_service_dependencies", {"service_name": service_name}, f"{len(deps)} deps, {len(dependents)} callers")
        return {
            "service": service_name,
            "dependencies": deps,
            "dependents": dependents
        }

    def get_kafka_health(self) -> Dict[str, Any]:
        metrics = kafka_health_tracker.get_metrics_summary()
        self.log_call("get_kafka_health", {}, f"Status: {metrics.get('status')}")
        return metrics

    def get_baselines(self) -> List[Dict[str, Any]]:
        bls = baseline_manager.get_all_baselines()
        self.log_call("get_baselines", {}, f"Retrieved {len(bls)} baselines")
        return bls

    def get_historical_remedies(self, service: str, category: str) -> List[Dict[str, Any]]:
        remedies = incident_memory.get_proven_remedies(service, category)
        self.log_call("get_historical_remedies", {"service": service, "category": category}, f"Found {len(remedies)} remedies")
        return remedies


tool_registry = AssistantToolRegistry()
