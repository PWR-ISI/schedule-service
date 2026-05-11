import uuid

import pytest

from apps.scheduling.handlers import (
    handle_appointment_cancelled,
    handle_payment_failed,
    handle_payment_succeeded,
)
from apps.scheduling.models import SlotStatus
from apps.scheduling.services import SchedulingService

from .factories import make_slot


@pytest.mark.django_db
def test_appointment_cancelled_releases_reserved_slot():
    appointment_id = uuid.uuid4()
    slot = make_slot()
    SchedulingService.reserve(slot.id, appointment_id, ttl_minutes=5)

    handle_appointment_cancelled({"appointment_id": str(appointment_id)})

    slot.refresh_from_db()
    assert slot.status == SlotStatus.AVAILABLE


@pytest.mark.django_db
def test_payment_failed_releases_slot():
    appointment_id = uuid.uuid4()
    slot = make_slot()
    SchedulingService.reserve(slot.id, appointment_id, ttl_minutes=5)

    handle_payment_failed({"appointment_id": str(appointment_id)})

    slot.refresh_from_db()
    assert slot.status == SlotStatus.AVAILABLE


@pytest.mark.django_db
def test_payment_succeeded_confirms_slot():
    appointment_id = uuid.uuid4()
    slot = make_slot()
    SchedulingService.reserve(slot.id, appointment_id, ttl_minutes=5)

    handle_payment_succeeded({"appointment_id": str(appointment_id)})

    slot.refresh_from_db()
    assert slot.status == SlotStatus.CONFIRMED


@pytest.mark.django_db
def test_handler_safe_when_slot_missing():
    handle_appointment_cancelled({"appointment_id": str(uuid.uuid4())})
