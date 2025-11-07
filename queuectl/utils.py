import uuid
from datetime import datetime

def generate_id() -> str:
    """Generate a unique ID for jobs"""
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    """Get current UTC timestamp"""
    return datetime.utcnow()

def format_timestamp(dt: datetime) -> str:
    """Format datetime for display"""
    return dt.isoformat() + "Z"