import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from .factories import make_slot


@pytest.mark.django_db
def test_unique_doctor_start_time():
    doctor_id = uuid.uuid4()
    start = timezone.now() + timedelta(days=1)
    make_slot(doctor_id=doctor_id, start_time=start)
    with pytest.raises(IntegrityError):
        make_slot(doctor_id=doctor_id, start_time=start)


@pytest.mark.django_db
def test_end_must_be_after_start():
    start = timezone.now() + timedelta(days=1)
    with pytest.raises(IntegrityError):
        make_slot(start_time=start, end_time=start - timedelta(minutes=1))
