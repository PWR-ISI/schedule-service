import logging

import requests
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from rest_framework.permissions import AllowAny
from common.auth import IsAdmin, IsAdminOrDoctor, IsAuthenticated, IsInternal
from common.events import publish
from common import payments
from common.exceptions import InvalidTransition

from .models import DoctorSchedule, Slot, SlotStatus, Appointment, AppointmentFile, AppointmentStatus
from .serializers import (
    DoctorScheduleSerializer,
    SlotCreateSerializer,
    SlotReserveSerializer,
    SlotSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentCancelSerializer,
    AppointmentCompleteSerializer,
)
from .services import SchedulingService
from .s3_utils import upload_appointment_file

STAFF_ROLES = ("admin", "staff", "receptionist")
ACTIVE_STATUSES = (
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.PAID,
    AppointmentStatus.PENDING_PAYMENT,
)

logger = logging.getLogger(__name__)


class SlotViewSet(ViewSet):
    """HTTP surface for slots. Business logic lives in SchedulingService."""

    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in {"reserve", "release", "confirm"}:
            return [IsInternal()]
        if self.action == "create":
            return [IsAdminOrDoctor()]
        return [AllowAny()]

    def list(self, request):
        qs = Slot.objects.all()
        doctor_id = request.query_params.get("doctor_id")
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        slot_status = request.query_params.get("status")

        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        if date_from:
            qs = qs.filter(start_time__date__gte=parse_date(date_from) or date_from)
        if date_to:
            qs = qs.filter(start_time__date__lte=parse_date(date_to) or date_to)
        if slot_status == "all":
            pass  # every status (used by the doctor's slot-creation view)
        elif slot_status:
            qs = qs.filter(status=slot_status)
        else:
            qs = qs.filter(status=SlotStatus.AVAILABLE)

        return Response(SlotSerializer(qs[:500], many=True).data)

    def retrieve(self, request, pk=None):
        try:
            slot = Slot.objects.get(pk=pk)
        except Slot.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SlotSerializer(slot).data)

    def create(self, request):
        # A doctor may only create slots for themselves; admins may create for any doctor.
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if getattr(request, "user_role", None) == "doctor" and request.user_id:
            data["doctor_id"] = request.user_id
        serializer = SlotCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            slot = Slot.objects.create(**serializer.validated_data)
        except IntegrityError:
            return Response(
                {"detail": "Slot w tym terminie już istnieje."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(SlotSerializer(slot).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="reserve")
    def reserve(self, request, pk=None):
        serializer = SlotReserveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot = SchedulingService.reserve(
            slot_id=pk,
            appointment_id=serializer.validated_data["appointment_id"],
            ttl_minutes=serializer.validated_data.get("ttl_minutes"),
        )
        return Response(SlotSerializer(slot).data)

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        slot = SchedulingService.release(slot_id=pk)
        return Response(SlotSerializer(slot).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        slot = SchedulingService.confirm(slot_id=pk)
        return Response(SlotSerializer(slot).data)


class DoctorAvailabilityViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "doctor_id"

    @action(detail=True, methods=["get"], url_path="availability")
    def availability(self, request, doctor_id=None):
        qs = Slot.objects.filter(doctor_id=doctor_id, status=SlotStatus.AVAILABLE)
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        if date_from:
            qs = qs.filter(start_time__gte=parse_datetime(date_from))
        if date_to:
            qs = qs.filter(start_time__lt=parse_datetime(date_to))
        return Response(SlotSerializer(qs[:500], many=True).data)


class DoctorScheduleViewSet(ViewSet):
    def get_permissions(self):
        return [IsAdmin()]

    def list(self, request):
        qs = DoctorSchedule.objects.all()
        doctor_id = request.query_params.get("doctor_id")
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        return Response(DoctorScheduleSerializer(qs, many=True).data)

    def create(self, request):
        serializer = DoctorScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = DoctorSchedule.objects.create(**serializer.validated_data)
        return Response(DoctorScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)


class AppointmentViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Role-aware listing:
        - doctor  -> appointments on the doctor's own slots (slot.doctor_id)
        - admin / receptionist / staff -> all (optionally filtered by ?doctor_id / ?patient_id)
        - patient (default) -> own appointments
        """
        role = getattr(request, "user_role", None)
        uid = request.user_id
        qp_doctor = request.query_params.get("doctor_id")
        qp_patient = request.query_params.get("patient_id")

        qs = Appointment.objects.all()
        if role == "doctor":
            qs = qs.filter(slot__doctor_id=uid)
        elif role in ("admin", "receptionist", "staff"):
            if qp_doctor:
                qs = qs.filter(slot__doctor_id=qp_doctor)
            if qp_patient:
                qs = qs.filter(patient_id=qp_patient)
        else:
            qs = qs.filter(patient_id=uid)

        qs = qs.select_related("slot").order_by("-slot__start_time")
        return Response(AppointmentSerializer(qs, many=True).data)

    def _get_for_manage(self, request, pk):
        """Fetch an appointment the caller may cancel/complete, or (None, error_response).
        patient -> own; doctor -> own slot; admin/staff/receptionist -> any."""
        role = getattr(request, "user_role", None)
        uid = str(request.user_id)
        try:
            appointment = Appointment.objects.select_related("slot").get(pk=pk)
        except Appointment.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if role in STAFF_ROLES:
            return appointment, None
        if role == "doctor":
            if str(appointment.slot.doctor_id) != uid:
                return None, Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
            return appointment, None
        # patient (default)
        if str(appointment.patient_id) != uid:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return appointment, None

    def _publish_appointment(self, event_type, appointment, extra=None):
        payload = {
            "appointment_id": str(appointment.id),
            "patient_id": str(appointment.patient_id),
            "doctor_id": str(appointment.slot.doctor_id),
            "slot_id": str(appointment.slot_id),
            "scheduled_start": appointment.slot.start_time.isoformat(),
            "status": appointment.status,
        }
        if extra:
            payload.update(extra)
        publish(settings.SCHEDULE_SNS_TOPIC_ARN, event_type, payload)
        self._notify(event_type, payload)

    @staticmethod
    def _notify(event_type, payload):
        """Best-effort: push the event to notification-service so a notification is created
        immediately (does not block, never raises)."""
        url = getattr(settings, "NOTIFICATION_SERVICE_URL", "")
        if not url:
            return
        try:
            requests.post(
                f"{url}/api/v2/events/",
                json={"event_type": event_type, "payload": payload},
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Token": settings.INTERNAL_SHARED_TOKEN,
                },
                timeout=5,
            )
        except Exception as exc:  # noqa: BLE001 - notifications are best-effort
            logger.warning("Notify %s failed: %s", event_type, exc)

    def retrieve(self, request, pk=None):
        appointment, err = self._get_for_manage(request, pk)
        if err:
            return err
        return Response(AppointmentSerializer(appointment).data)

    def create(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = getattr(request, "user_role", None)
        slot_id = serializer.validated_data["slot_id"]
        notes = serializer.validated_data.get("notes", "")
        file_obj = serializer.validated_data.get("file")

        # A receptionist/admin may book on behalf of a patient; everyone else books for self.
        patient_id = str(request.user_id)
        on_behalf = serializer.validated_data.get("patient_id")
        if on_behalf and role in STAFF_ROLES:
            patient_id = str(on_behalf)

        try:
            slot = Slot.objects.get(id=slot_id)
        except Slot.DoesNotExist:
            return Response({"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND)

        payments_on = settings.PAYMENTS_ENABLED
        initial_status = (
            AppointmentStatus.PENDING_PAYMENT if payments_on else AppointmentStatus.SCHEDULED
        )
        appointment = Appointment.objects.create(
            patient_id=patient_id, slot=slot, notes=notes, status=initial_status
        )

        try:
            SchedulingService.reserve(slot_id=slot_id, appointment_id=appointment.id)
        except Exception as exc:
            appointment.delete()
            return Response({"detail": f"Termin niedostępny: {exc}"}, status=status.HTTP_409_CONFLICT)

        if file_obj:
            try:
                s3_key = upload_appointment_file(file_obj, str(appointment.id))
                AppointmentFile.objects.create(
                    appointment=appointment,
                    original_name=file_obj.name,
                    s3_key=s3_key,
                    content_type=getattr(file_obj, "content_type", "application/octet-stream"),
                    size_bytes=file_obj.size,
                    uploaded_by=request.user_id,
                )
            except Exception as exc:
                logger.error("Failed to upload file for appointment %s: %s", appointment.id, exc)

        redirect_uri = None
        if payments_on:
            # Open a PayU order; the visit stays pending_payment until payment.succeeded.
            try:
                order = payments.create_order(
                    appointment_id=appointment.id,
                    patient_id=patient_id,
                    description=f"Wizyta lekarska {slot.start_time.date().isoformat()}",
                )
                appointment.payment_order_id = str(order.get("id") or order.get("order_id") or "")
                appointment.save(update_fields=["payment_order_id", "updated_at"])
                redirect_uri = (
                    order.get("redirect_url") or order.get("redirect_uri") or order.get("redirectUri")
                )
            except Exception as exc:
                logger.error("Payment order failed for appointment %s: %s", appointment.id, exc)
                SchedulingService.release(slot_id=slot_id, force=True)
                appointment.status = AppointmentStatus.FAILED
                appointment.save(update_fields=["status", "updated_at"])
                return Response(
                    {"detail": "Nie udało się rozpocząć płatności.", "error": str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        else:
            # No online payment: the slot is booked immediately.
            try:
                SchedulingService.confirm(slot_id=slot_id)
            except InvalidTransition:
                pass

        self._publish_appointment("appointment.created", appointment,
                                  extra={"patient_email": getattr(request, "user_email", "")})

        data = AppointmentSerializer(appointment).data
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        ser = AppointmentCancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = ser.validated_data.get("reason", "")

        appointment, err = self._get_for_manage(request, pk)
        if err:
            return err
        if appointment.status not in ACTIVE_STATUSES:
            return Response(
                {"detail": "Można odwołać tylko aktywną wizytę."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        was_paid = appointment.status == AppointmentStatus.PAID
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = reason
        appointment.cancelled_at = timezone.now()
        appointment.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])

        try:
            SchedulingService.release(slot_id=appointment.slot_id, force=True)
        except InvalidTransition:
            logger.info("Slot %s already released.", appointment.slot_id)

        # Refund a paid visit (best-effort; never blocks the cancellation).
        if was_paid and settings.PAYMENTS_ENABLED:
            payments.refund_for_appointment(appointment.id)

        self._publish_appointment("appointment.cancelled", appointment, extra={"reason": reason})
        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        ser = AppointmentCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        summary = ser.validated_data.get("visit_summary", "")

        role = getattr(request, "user_role", None)
        if role not in STAFF_ROLES + ("doctor",):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        appointment, err = self._get_for_manage(request, pk)
        if err:
            return err
        if appointment.status not in (AppointmentStatus.SCHEDULED, AppointmentStatus.PAID):
            return Response(
                {"detail": "Można zakończyć tylko aktywną wizytę."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment.status = AppointmentStatus.COMPLETED
        appointment.visit_summary = summary
        appointment.completed_at = timezone.now()
        appointment.save(update_fields=["status", "visit_summary", "completed_at", "updated_at"])

        self._publish_appointment("appointment.completed", appointment, extra={"visit_summary": summary})
        return Response(AppointmentSerializer(appointment).data)
