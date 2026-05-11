import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.scheduling.models import SlotStatus
from apps.scheduling.services import SchedulingService
from common.exceptions import InvalidTransition, SlotUnavailable

from .factories import make_slot


@pytest.mark.django_db
def test_reserve_happy_path():
    slot = make_slot()
    appointment_id = uuid.uuid4()

    reserved = SchedulingService.reserve(slot.id, appointment_id, ttl_minutes=5)

    assert reserved.status == SlotStatus.RESERVED
    assert reserved.appointment_id == appointment_id
    assert reserved.reservation_expires_at > timezone.now()


@pytest.mark.django_db
def test_reserve_rejects_already_reserved():
    slot = make_slot(status=SlotStatus.RESERVED, appointment_id=uuid.uuid4(),
                     reservation_expires_at=timezone.now() + timedelta(minutes=5))
    with pytest.raises(SlotUnavailable):
        SchedulingService.reserve(slot.id, uuid.uuid4())


@pytest.mark.django_db
def test_release_is_idempotent_for_available():
    slot = make_slot()
    released = SchedulingService.release(slot.id)
    assert released.status == SlotStatus.AVAILABLE


@pytest.mark.django_db
def test_release_returns_reserved_slot_to_available():
    slot = make_slot()
    SchedulingService.reserve(slot.id, uuid.uuid4(), ttl_minutes=5)
    released = SchedulingService.release(slot.id)
    assert released.status == SlotStatus.AVAILABLE
    assert released.appointment_id is None
    assert released.reservation_expires_at is None


@pytest.mark.django_db
def test_release_rejects_confirmed_slot():
    slot = make_slot()
    SchedulingService.reserve(slot.id, uuid.uuid4(), ttl_minutes=5)
    SchedulingService.confirm(slot.id)
    with pytest.raises(InvalidTransition):
        SchedulingService.release(slot.id)


@pytest.mark.django_db
def test_confirm_only_from_reserved():
    slot = make_slot()
    with pytest.raises(InvalidTransition):
        SchedulingService.confirm(slot.id)


@pytest.mark.django_db
def test_expire_reservations_releases_past_ttl():
    slot = make_slot()
    SchedulingService.reserve(slot.id, uuid.uuid4(), ttl_minutes=5)
    # Force expiration by rewriting the field.
    from apps.scheduling.models import Slot
    Slot.objects.filter(id=slot.id).update(reservation_expires_at=timezone.now() - timedelta(minutes=1))

    released = SchedulingService.expire_reservations()

    assert released == 1
    slot.refresh_from_db()
    assert slot.status == SlotStatus.AVAILABLE
