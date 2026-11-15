"""
AegisOps AI - Anomaly Deduplication Engine (Phase 8)
Groups repeated, continuous anomaly occurrences into coherent Anomaly Episodes.
Prevents alert storms and incident flooding when thousands of errors occur during a single failure.
Tracks:
- episode_id
- tenant_id
- service
- feature / anomaly_type
- first_seen
- last_seen
- peak_score
- event_count
- status: ACTIVE, EXPIRED, RESOLVED
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import threading


class AnomalyEpisode:
    """
    A single continuous episode representing multiple consecutive anomaly events
    for the same (tenant, service, feature/failure_type).
    """
    def __init__(
        self,
        episode_id: str,
        tenant_id: str,
        service: str,
        feature: str,
        initial_score: float,
        severity: str,
        initial_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.episode_id = episode_id
        self.tenant_id = tenant_id
        self.service = service
        self.feature = feature
        self.first_seen = initial_time
        self.last_seen = initial_time
        self.peak_score = initial_score
        self.current_score = initial_score
        self.severity = severity
        self.event_count = 1
        self.status = "ACTIVE"  # ACTIVE, EXPIRED, RESOLVED
        self.incident_id: Optional[str] = None
        self.metadata = metadata or {}

    def record_occurrence(self, score: float, severity: str, timestamp: float, metadata: Optional[Dict[str, Any]] = None):
        self.event_count += 1
        self.last_seen = timestamp
        self.current_score = score
        if score > self.peak_score:
            self.peak_score = score
            self.severity = severity
        if metadata:
            self.metadata.update(metadata)

    def is_active(self, current_time: float, timeout_window_sec: float = 45.0) -> bool:
        """Episode remains active if an event occurred within the timeout window."""
        return (self.status == "ACTIVE") and ((current_time - self.last_seen) <= timeout_window_sec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "tenant_id": self.tenant_id,
            "company": self.tenant_id,
            "service": self.service,
            "feature": self.feature,
            "severity": self.severity,
            "first_seen": datetime.fromtimestamp(self.first_seen, tz=timezone.utc).isoformat(),
            "last_seen": datetime.fromtimestamp(self.last_seen, tz=timezone.utc).isoformat(),
            "duration_seconds": round(max(0.0, self.last_seen - self.first_seen), 1),
            "peak_score": round(self.peak_score, 3),
            "current_score": round(self.current_score, 3),
            "event_count": self.event_count,
            "status": self.status,
            "incident_id": self.incident_id,
            "metadata": self.metadata
        }


class AnomalyDeduplicator:
    """
    Deduplicates incoming anomaly events into active AnomalyEpisodes.
    """
    def __init__(self, episode_inactivity_timeout_sec: float = 45.0):
        self.timeout_sec = episode_inactivity_timeout_sec
        # (tenant_id, service, feature_category) -> AnomalyEpisode
        self._active_episodes: Dict[Tuple[str, str, str], AnomalyEpisode] = {}
        self._history: List[AnomalyEpisode] = []
        self.lock = threading.Lock()

    def process_anomaly(
        self,
        tenant_id: str,
        service: str,
        feature: str,
        score: float,
        severity: str,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[AnomalyEpisode, bool]:
        """
        Deduplicates an anomaly.
        Returns: (episode, is_new_episode)
        """
        now = timestamp or time.time()
        tenant = tenant_id.lower()
        key = (tenant, service, feature)

        with self.lock:
            # Check if active episode exists
            existing = self._active_episodes.get(key)
            if existing and existing.is_active(now, self.timeout_sec):
                existing.record_occurrence(score, severity, now, metadata)
                return existing, False

            # If existing episode timed out, archive it
            if existing:
                existing.status = "EXPIRED"
                self._history.append(existing)

            # Create new episode
            ep_id = f"EP-{uuid.uuid4().hex[:8].upper()}"
            new_ep = AnomalyEpisode(
                episode_id=ep_id,
                tenant_id=tenant,
                service=service,
                feature=feature,
                initial_score=score,
                severity=severity,
                initial_time=now,
                metadata=metadata
            )
            self._active_episodes[key] = new_ep
            return new_ep, True

    def get_active_episodes(self, tenant_id: Optional[str] = None) -> List[AnomalyEpisode]:
        now = time.time()
        with self.lock:
            active = []
            for k, ep in list(self._active_episodes.items()):
                if ep.is_active(now, self.timeout_sec):
                    if not tenant_id or ep.tenant_id == tenant_id.lower():
                        active.append(ep)
                else:
                    ep.status = "EXPIRED"
                    self._history.append(ep)
                    self._active_episodes.pop(k, None)
            return active

    def associate_incident(self, episode_id: str, incident_id: str):
        with self.lock:
            for ep in self._active_episodes.values():
                if ep.episode_id == episode_id:
                    ep.incident_id = incident_id
                    return


anomaly_deduplicator = AnomalyDeduplicator()
