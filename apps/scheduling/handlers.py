"""
SQS event handlers for schedule-service.

Subscribes to appointment + payment events to keep slot state in sync with
the appointment lifecycle owned by appointment-service.
"""
import logging

from common.exceptions import InvalidTransition

from .models import Slot, SlotStatus
from .services import SchedulingService

logger = logging.getLogger(__name__)


def _slot_for_appointment(appointment_id):
    if not appointment_id:
        return None
    try:
        return Slot.objects.get(appointment_id=appointment_id)
    except Slot.DoesNotExist:
        logger.warning("No slot for appointment_id=%s; ignoring.", appointment_id)
        return None


def handle_appointment_cancelled(payload: dict, envelope: dict = None):
    slot = _slot_for_appointment(payload.get("appointment_id"))
    if slot and slot.status in (SlotStatus.RESERVED,):
        try:
            SchedulingService.release(slot.id)
        except InvalidTransition:
            logger.info("Slot %s already released or in non-releasable state.", slot.id)


def handle_payment_failed(payload: dict, envelope: dict = None):
    slot = _slot_for_appointment(payload.get("appointment_id"))
    if slot and slot.status == SlotStatus.RESERVED:
        try:
            SchedulingService.release(slot.id)
        except InvalidTransition:
            pass


def handle_payment_succeeded(payload: dict, envelope: dict = None):
    slot = _slot_for_appointment(payload.get("appointment_id"))
    if slot and slot.status == SlotStatus.RESERVED:
        try:
            SchedulingService.confirm(slot.id)
        except InvalidTransition:
            pass


HANDLERS = {
    "appointment.cancelled": handle_appointment_cancelled,
    "payment.failed": handle_payment_failed,
    "payment.succeeded": handle_payment_succeeded,
}
