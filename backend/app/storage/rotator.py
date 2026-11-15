"""
Log Rotator for AegisOps AI
"""

import os
import shutil
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.core.config import settings


class LogRotator:
    @staticmethod
    def rotate_service_logs(service_name: Optional[str] = None, max_size_bytes: int = 5 * 1024 * 1024) -> List[Dict[str, Any]]:
        """
        Rotates active service logs exceeding threshold into timestamped rotation files.
        """
        rotated_files = []
        logs_dir = settings.LOGS_DIR
        
        if not os.path.exists(logs_dir):
            return []

        for filename in os.listdir(logs_dir):
            if not filename.endswith(".log"):
                continue
            if service_name and not filename.startswith(service_name):
                continue

            file_path = os.path.join(logs_dir, filename)
            try:
                size = os.path.getsize(file_path)
                if size >= max_size_bytes or service_name:
                    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    rotated_name = f"{filename}.{timestamp_str}.old"
                    rotated_path = os.path.join(logs_dir, rotated_name)
                    
                    shutil.copy2(file_path, rotated_path)
                    # Truncate active log
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.truncate(0)
                        
                    rotated_files.append({
                        "original_file": filename,
                        "rotated_file": rotated_name,
                        "size_bytes": size,
                        "rotated_path": rotated_path
                    })
            except Exception as e:
                pass

        return rotated_files
