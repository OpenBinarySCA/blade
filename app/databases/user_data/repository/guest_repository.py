"""
Guest Repository - CRUD operations for GuestUsage model
"""
from typing import Optional
from datetime import datetime

from ..models import GuestUsage
from ..database import session_generator


def get_or_create_guest(ip_address: str, device_fingerprint: str) -> GuestUsage:
    """Get existing guest record or create a new one"""
    with session_generator() as db:
        guest = db.query(GuestUsage).filter(
            GuestUsage.ip_address == ip_address,
            GuestUsage.device_fingerprint == device_fingerprint
        ).first()

        if not guest:
            guest = GuestUsage(
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                usage_count=0,
                last_used_at=datetime.now()
            )
            db.add(guest)
            db.commit()
            db.refresh(guest)

        return guest


def get_usage_count(ip_address: str, device_fingerprint: str) -> int:
    """Get the current usage count for a guest"""
    with session_generator() as db:
        guest = db.query(GuestUsage).filter(
            GuestUsage.ip_address == ip_address,
            GuestUsage.device_fingerprint == device_fingerprint
        ).first()

        return guest.usage_count if guest else 0


def increment_usage(ip_address: str, device_fingerprint: str) -> int:
    """Increment usage count and return the new count"""
    with session_generator() as db:
        guest = db.query(GuestUsage).filter(
            GuestUsage.ip_address == ip_address,
            GuestUsage.device_fingerprint == device_fingerprint
        ).first()

        if not guest:
            guest = GuestUsage(
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                usage_count=1,
                last_used_at=datetime.now()
            )
            db.add(guest)
        else:
            guest.usage_count += 1
            guest.last_used_at = datetime.now()

        db.commit()
        db.refresh(guest)
        return guest.usage_count


def can_use(ip_address: str, device_fingerprint: str, limit: int = 3) -> bool:
    """Check if the guest can still use the service (under limit)"""
    count = get_usage_count(ip_address, device_fingerprint)
    return count < limit


def reset_usage(ip_address: str, device_fingerprint: str) -> bool:
    """Reset usage count for a guest (admin operation)"""
    with session_generator() as db:
        guest = db.query(GuestUsage).filter(
            GuestUsage.ip_address == ip_address,
            GuestUsage.device_fingerprint == device_fingerprint
        ).first()

        if guest:
            guest.usage_count = 0
            db.commit()
            return True
        return False
