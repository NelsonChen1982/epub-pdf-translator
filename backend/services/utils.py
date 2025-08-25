import os
import tempfile
import shutil
import time
from pathlib import Path
from typing import Optional


def create_temp_dir() -> str:
    """Create a temporary directory for file processing."""
    temp_dir = os.getenv("TEMP_DIR", "./temp")
    os.makedirs(temp_dir, exist_ok=True)
    return tempfile.mkdtemp(dir=temp_dir)


def cleanup_old_files(temp_dir: str, ttl_hours: int = 24):
    """Clean up files older than TTL hours."""
    if not os.path.exists(temp_dir):
        return
    
    cutoff_time = time.time() - (ttl_hours * 3600)
    
    for item in os.listdir(temp_dir):
        item_path = os.path.join(temp_dir, item)
        if os.path.getmtime(item_path) < cutoff_time:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)


def normalize_zip_path(opf_base: str, href: str) -> str:
    """Normalize href path relative to OPF base directory."""
    if opf_base == ".":
        return href
    
    base_path = Path(opf_base).parent if opf_base != "." else Path(".")
    full_path = base_path / href
    return str(full_path).replace("\\", "/")


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)


def is_allowed_file_type(filename: str, allowed_extensions: list) -> bool:
    """Check if file extension is allowed."""
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)


def generate_job_id() -> str:
    """Generate unique job ID."""
    import uuid
    return str(uuid.uuid4())