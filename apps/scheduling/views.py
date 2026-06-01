import logging

from django.conf import settings
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from rest_framework.permissions import AllowAny
from common.auth import IsAdmin, IsAdminOrDoctor, IsAuthenticated, IsInternal
from common.events import publish

from .models import DoctorSchedule, Slot, SlotStatus, Appointment, AppointmentFile
from .serializers import (
    DoctorScheduleSerializer,
    SlotCreateSerializer,
    SlotReserveSerializer,
    SlotSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
)
from .services import SchedulingService
from .s3_utils import upload_appointment_file

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
        if slot_status:
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
        serializer = SlotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot = Slot.objects.create(**serializer.validated_data)
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
        patient_id = request.user_id
        qs = Appointment.objects.filter(patient_id=patient_id)
        return Response(AppointmentSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            appointment = Appointment.objects.get(pk=pk, patient_id=request.user_id)
        except Appointment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSerializer(appointment).data)

    def create(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        slot_id = serializer.validated_data["slot_id"]
        notes = serializer.validated_data.get("notes", "")
        file_obj = serializer.validated_data.get("file")

        try:
            slot = Slot.objects.get(id=slot_id)
        except Slot.DoesNotExist:
            return Response(
                {"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND
            )

        appointment = Appointment.objects.create(
            patient_id=request.user_id, slot=slot, notes=notes
        )

        SchedulingService.reserve(slot_id=slot_id, appointment_id=appointment.id)

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

        publish(
            settings.SCHEDULE_SNS_TOPIC_ARN,
            "appointment.created",
            {
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "slot_id": str(appointment.slot_id),
                "appointment_time": slot.start_time.isoformat(),
                "status": appointment.status,
            },
        )

        return Response(
            AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            appointment = Appointment.objects.get(pk=pk, patient_id=request.user_id)
        except Appointment.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if appointment.status != "scheduled":
            return Response(
                {"detail": "Can only cancel scheduled appointments."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment.status = "cancelled"
        appointment.save()

        SchedulingService.release(slot_id=appointment.slot_id)

        publish(
            settings.SCHEDULE_SNS_TOPIC_ARN,
            "appointment.cancelled",
            {
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "slot_id": str(appointment.slot_id),
            },
        )

        return Response(AppointmentSerializer(appointment).data)
