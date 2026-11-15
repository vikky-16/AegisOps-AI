"""
Service Dependency Graph Representation
Backed by the dynamic telemetry-inferred graph engine with full backward compatibility.
"""

from typing import Dict, List, Set, Optional
from backend.app.rca.dynamic_graph import dynamic_graph


class DependencyGraph:
    def __init__(self):
        self.dynamic = dynamic_graph

    @property
    def adj_list(self) -> Dict[str, List[str]]:
        return {s: [edge["target_service"] for edge in self.dynamic.get_dependencies(s)] for s in self.dynamic.services}

    @property
    def reverse_adj(self) -> Dict[str, List[str]]:
        res: Dict[str, List[str]] = {s: [] for s in self.dynamic.services}
        for s in self.dynamic.services:
            for up in self.dynamic.get_dependents(s):
                if up in res:
                    res[s].append(up)
        return res

    def get_dependencies(self, service_name: str) -> List[str]:
        edges = self.dynamic.get_dependencies(service_name)
        return [e["target_service"] for e in edges]

    def get_dependents(self, service_name: str) -> List[str]:
        """Returns services that depend on this service directly or indirectly."""
        return self.dynamic.get_dependents(service_name)

    def get_downstream_dependents(self, service_name: str) -> List[str]:
        """Alias for get_dependents."""
        return self.dynamic.get_dependents(service_name)

    def get_root_dependencies(self, service_name: str) -> List[str]:
        """Finds downstream leaf dependencies for a given service."""
        visited: Set[str] = set()
        queue = [service_name]
        leaves = []
        
        while queue:
            curr = queue.pop(0)
            deps = self.get_dependencies(curr)
            if not deps:
                if curr != service_name:
                    leaves.append(curr)
            for d in deps:
                if d not in visited:
                    visited.add(d)
                    queue.append(d)
        return leaves or [service_name]

    def get_topological_depth(self, service_name: str) -> int:
        """
        Depth from root ingress (Gateway = 0, Service A = 1, Service B = 2, Database = 3).
        Deepest dependencies often hold the originating root cause in cascade failures.
        """
        return self.dynamic.get_topological_depth(service_name)

