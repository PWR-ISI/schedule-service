import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scheduling.models import SlotStatus

from .factories import jwt_for, make_slot


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
def test_list_slots_returns_available_by_default(api):
    available = make_slot()
    make_slot(status=SlotStatus.BLOCKED)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for(uuid.uuid4(), 'patient')}")
    resp = api.get("/api/v1/slots/")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(available.id) in ids


@pytest.mark.django_db
def test_create_slot_requires_admin_or_doctor(api):
    payload = {
        "doctor_id": str(uuid.uuid4()),
        "facility_id": str(uuid.uuid4()),
        "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
        "end_time": (timezone.now() + timedelta(days=1, minutes=30)).isoformat(),
    }
    # patient role → 403
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for(uuid.uuid4(), 'patient')}")
    resp = api.post("/api/v1/slots/", payload, format="json")
    assert resp.status_code == 403

    # admin → 201
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for(uuid.uuid4(), 'admin')}")
    resp = api.post("/api/v1/slots/", payload, format="json")
    assert resp.status_code == 201, resp.content


@pytest.mark.django_db
def test_reserve_requires_internal_token(api, settings):
    slot = make_slot()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for(uuid.uuid4(), 'patient')}")
    resp = api.post(f"/api/v1/slots/{slot.id}/reserve/", {"appointment_id": str(uuid.uuid4())}, format="json")
    assert resp.status_code == 403

    api.credentials(HTTP_X_INTERNAL_TOKEN=settings.INTERNAL_SHARED_TOKEN)
    resp = api.post(f"/api/v1/slots/{slot.id}/reserve/", {"appointment_id": str(uuid.uuid4())}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == SlotStatus.RESERVED


@pytest.mark.django_db
def test_reserve_already_reserved_returns_409(api, settings):
    slot = make_slot()
    api.credentials(HTTP_X_INTERNAL_TOKEN=settings.INTERNAL_SHARED_TOKEN)
    api.post(f"/api/v1/slots/{slot.id}/reserve/", {"appointment_id": str(uuid.uuid4())}, format="json")
    resp = api.post(f"/api/v1/slots/{slot.id}/reserve/", {"appointment_id": str(uuid.uuid4())}, format="json")
    assert resp.status_code == 409


@pytest.mark.django_db
def test_doctor_availability(api):
    doctor_id = uuid.uuid4()
    mine = make_slot(doctor_id=doctor_id)
    other = make_slot()  # different doctor
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for(uuid.uuid4(), 'patient')}")
    resp = api.get(f"/api/v1/doctors/{doctor_id}/availability/")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(mine.id) in ids
    assert str(other.id) not in ids


@pytest.mark.django_db
def test_health(api):
    resp = api.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
