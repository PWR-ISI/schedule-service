import logging

from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from common.auth import IsAdmin, IsAdminOrDoctor, IsAuthenticated, IsInternal

from .models import DoctorSchedule, Slot, SlotStatus
from .serializers import (
    DoctorScheduleSerializer,
    SlotCreateSerializer,
    SlotReserveSerializer,
    SlotSerializer,
)
from .services import SchedulingService

logger = logging.getLogger(__name__)


class SlotViewSet(ViewSet):
    """HTTP surface for slots. Business logic lives in SchedulingService."""

    def get_permissions(self):
        if self.action in {"reserve", "release", "confirm"}:
            return [IsInternal()]
        if self.action == "create":
            return [IsAdminOrDoctor()]
        return [IsAuthenticated()]

    def list(self, request):
        qs = Slot.objects.all()
        doctor_id = request.query_params.get("doctor_id")
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        slot_status = request.query_params.get("status")

        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        if date_from:
            qs = qs.filter(start_time__gte=parse_datetime(date_from))
        if date_to:
            qs = qs.filter(start_time__lt=parse_datetime(date_to))
        if slot_status:
            qs = qs.filter(status=slot_status)
        else:
            qs = qs.filter(status=SlotStatus.AVAILABLE)

        return Response(SlotSerializer(qs[:200], many=True).data)

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
