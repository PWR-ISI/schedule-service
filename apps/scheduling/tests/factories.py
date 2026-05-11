import uuid
from datetime import timedelta

from django.utils import timezone

from apps.scheduling.models import Slot, SlotStatus


def make_slot(**overrides) -> Slot:
    start = overrides.pop("start_time", timezone.now() + timedelta(days=1))
    end = overrides.pop("end_time", start + timedelta(minutes=30))
    defaults = {
        "doctor_id": uuid.uuid4(),
        "facility_id": uuid.uuid4(),
        "start_time": start,
        "end_time": end,
        "status": SlotStatus.AVAILABLE,
    }
    defaults.update(overrides)
    return Slot.objects.create(**defaults)


def jwt_for(user_id: str, role: str) -> str:
    """Build an unsigned JWT (header.payload.) for testing the stub middleware."""
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    body = json.dumps({"sub": str(user_id), "role": role}).encode()
    payload = base64.urlsafe_b64encode(body).rstrip(b"=").decode()
    return f"{header}.{payload}."
