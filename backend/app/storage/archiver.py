"""
Log and Data Archiver
Compresses rotated logs into gzip archives and stores in data/archive.
"""

import os
import gzip
import shutil
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone
from backend.app.core.config import settings


class DataArchiver:
    @staticmethod
    def archive_old_logs() -> List[Dict[str, Any]]:
        """
        Scans for rotated log files (.old or large .log), compresses them into .gz archives,
        and moves them into settings.ARCHIVE_DIR.
        """
        logs_dir = settings.LOGS_DIR
        archive_dir = settings.ARCHIVE_DIR
        os.makedirs(archive_dir, exist_ok=True)
        
        archived_results = []
        
        if not os.path.exists(logs_dir):
            return []

        for filename in os.listdir(logs_dir):
            if filename.endswith(".old"):
                file_path = os.path.join(logs_dir, filename)
                orig_size = os.path.getsize(file_path)
                
                archive_name = f"{filename}.gz"
                archive_path = os.path.join(archive_dir, archive_name)
                
                # Compress with gzip
                with open(file_path, "rb") as f_in:
                    with gzip.open(archive_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                comp_size = os.path.getsize(archive_path)
                ratio = round((1 - (comp_size / max(1, orig_size))) * 100, 1)
                
                # Remove rotated old file
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                    
                archived_results.append({
                    "archive_id": f"ARC-{uuid.uuid4().hex[:6].upper()}",
                    "file_name": archive_name,
                    "source_service": filename.split(".")[0],
                    "original_size_bytes": orig_size,
                    "compressed_size_bytes": comp_size,
                    "compression_ratio": ratio,
                    "archive_path": archive_path,
                    "archived_at": datetime.now(timezone.utc).isoformat()
                })

        return archived_results
