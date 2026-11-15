"""
Storage Intelligence Manager
Coordinates disk monitoring, table sizes, log consumers, prediction, and automated archival.
"""

import os
import psutil
from typing import Dict, Any, List
from datetime import datetime, timezone
from backend.app.core.config import settings
from backend.app.storage.rotator import LogRotator
from backend.app.storage.archiver import DataArchiver
from backend.app.ai.predictor import TrendPredictor


class StorageManager:
    def __init__(self):
        self.simulated_total_gb = 100.0
        self.simulated_used_gb = 82.4
        self.simulated_growth_rate_gb_h = 1.8

    def get_storage_status(self) -> Dict[str, Any]:
        """
        Gathers current storage breakdown, top consumers, and predictive growth.
        """
        logs_dir = settings.LOGS_DIR
        archive_dir = settings.ARCHIVE_DIR
        
        # Calculate real log directory size
        log_files = []
        total_log_bytes = 0
        if os.path.exists(logs_dir):
            for f in os.listdir(logs_dir):
                fp = os.path.join(logs_dir, f)
                if os.path.isfile(fp):
                    sz = os.path.getsize(fp)
                    total_log_bytes += sz
                    log_files.append({"name": f, "size_mb": round(sz / (1024 * 1024), 2)})

        total_archive_bytes = 0
        if os.path.exists(archive_dir):
            for f in os.listdir(archive_dir):
                fp = os.path.join(archive_dir, f)
                if os.path.isfile(fp):
                    total_archive_bytes += os.path.getsize(fp)

        # Top consumers
        top_consumers = [
            {"name": "Database Tablespace (aegis_core_ledger)", "category": "Database", "size_gb": 48.5, "percentage": 48.5},
            {"name": "Application Access Logs (service-b.log)", "category": "Logs", "size_gb": 18.2, "percentage": 18.2},
            {"name": "Audit & Transaction Journal", "category": "Audit", "size_gb": 10.4, "percentage": 10.4},
            {"name": "Telemetry Time-Series Snapshots", "category": "Metrics", "size_gb": 5.3, "percentage": 5.3},
        ]

        used_pct = round((self.simulated_used_gb / self.simulated_total_gb) * 100, 1)
        remaining_gb = max(0.0, (self.simulated_total_gb * 0.95) - self.simulated_used_gb)
        crit_hours = round(remaining_gb / self.simulated_growth_rate_gb_h, 1) if self.simulated_growth_rate_gb_h > 0 else 99.0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_gb": self.simulated_total_gb,
            "used_gb": round(self.simulated_used_gb, 2),
            "free_gb": round(self.simulated_total_gb - self.simulated_used_gb, 2),
            "used_percentage": used_pct,
            "growth_rate_gb_per_hour": self.simulated_growth_rate_gb_h,
            "predicted_critical_hours": crit_hours,
            "log_files_count": len(log_files),
            "total_log_size_mb": round(total_log_bytes / (1024 * 1024), 2),
            "archive_size_mb": round(total_archive_bytes / (1024 * 1024), 2),
            "top_consumers": top_consumers,
            "recommendation": "Archive application logs older than 14 days to reclaim ~18.2 GB." if used_pct > 75 else "Storage levels are currently optimal."
        }

    def execute_storage_optimization(self) -> Dict[str, Any]:
        """
        Performs log rotation, gzip compression, and storage reclamation.
        """
        # 1. Rotate logs
        rotated = LogRotator.rotate_service_logs(max_size_bytes=1024)
        
        # 2. Archive rotated logs into gzip
        archived = DataArchiver.archive_old_logs()
        
        # 3. Simulate reclaimed space
        reclaimed_gb = 18.2
        self.simulated_used_gb = max(45.0, self.simulated_used_gb - reclaimed_gb)
        self.simulated_growth_rate_gb_h = 0.35

        return {
            "success": True,
            "reclaimed_gb": reclaimed_gb,
            "rotated_count": len(rotated),
            "archived_count": len(archived),
            "new_used_gb": round(self.simulated_used_gb, 2),
            "new_used_percentage": round((self.simulated_used_gb / self.simulated_total_gb) * 100, 1),
            "message": f"Storage optimization complete. Reclaimed {reclaimed_gb} GB. Logs compressed to archive."
        }


storage_manager = StorageManager()
