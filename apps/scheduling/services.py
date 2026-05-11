"""Business logic for the Slot aggregate."""
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.events import publish
from common.exceptions import InvalidTransition, SlotUnavailable

from .models import Slot, SlotStatus

logger = logging.getLogger(__name__)


class SchedulingService:
    @staticmethod
    def _publish(event_type: str, slot: Slot, extra: Optional[dict] = None):
        payload = {
            "slot_id": str(slot.id),
            "doctor_id": str(slot.doctor_id),
            "facility_id": str(slot.facility_id),
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "status": slot.status,
            "appointment_id": str(slot.appointment_id) if slot.appointment_id else None,
            "reservation_expires_at": (
                slot.reservation_expires_at.isoformat() if slot.reservation_expires_at else None
            ),
        }
        if extra:
            payload.update(extra)
        publish(settings.SCHEDULE_SNS_TOPIC_ARN, event_type, payload)

    @staticmethod
    @transaction.atomic
    def reserve(slot_id: UUID, appointment_id: UUID, ttl_minutes: Optional[int] = None) -> Slot:
        slot = Slot.objects.select_for_update().get(id=slot_id)
        if slot.status != SlotStatus.AVAILABLE:
            raise SlotUnavailable(f"Slot {slot.id} is in status {slot.status}.")
        slot.status = SlotStatus.RESERVED
        slot.appointment_id = appointment_id
        ttl = ttl_minutes if ttl_minutes is not None else settings.SLOT_RESERVATION_TTL_MINUTES
        slot.reservation_expires_at = timezone.now() + timedelta(minutes=ttl)
        slot.save(update_fields=["status", "appointment_id", "reservation_expires_at", "updated_at"])
        SchedulingService._publish("slot.reserved", slot)
        return slot

    @staticmethod
    @transaction.atomic
    def release(slot_id: UUID) -> Slot:
        slot = Slot.objects.select_for_update().get(id=slot_id)
        if slot.status == SlotStatus.AVAILABLE:
            return slot  # idempotent no-op
        if slot.status == SlotStatus.CONFIRMED:
            raise InvalidTransition("Cannot release a confirmed slot. Cancel the appointment first.")
        previous_appointment = slot.appointment_id
        slot.status = SlotStatus.AVAILABLE
        slot.appointment_id = None
        slot.reservation_expires_at = None
        slot.save(update_fields=["status", "appointment_id", "reservation_expires_at", "updated_at"])
        SchedulingService._publish(
            "slot.released",
            slot,
            extra={"appointment_id": str(previous_appointment) if previous_appointment else None},
        )
        return slot

    @staticmethod
    @transaction.atomic
    def confirm(slot_id: UUID) -> Slot:
        slot = Slot.objects.select_for_update().get(id=slot_id)
        if slot.status == SlotStatus.CONFIRMED:
            return slot  # idempotent no-op
        if slot.status != SlotStatus.RESERVED:
            raise InvalidTransition(
                f"Slot {slot.id} cannot be confirmed from status {slot.status}."
            )
        slot.status = SlotStatus.CONFIRMED
        slot.reservation_expires_at = None
        slot.save(update_fields=["status", "reservation_expires_at", "updated_at"])
        SchedulingService._publish("slot.confirmed", slot)
        return slot

    @staticmethod
    def expire_reservations() -> int:
        """Release every slot whose reservation_expires_at is in the past. Returns count released."""
        expired_ids = list(
            Slot.objects.filter(
                status=SlotStatus.RESERVED,
                reservation_expires_at__lt=timezone.now(),
            ).values_list("id", flat=True)
        )
        for slot_id in expired_ids:
            try:
                SchedulingService.release(slot_id)
            except InvalidTransition:
                logger.warning("Slot %s could not be released during expiry sweep.", slot_id)
        return len(expired_ids)
