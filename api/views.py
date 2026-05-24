from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from datetime import datetime, timedelta, time
from .models import DoctorSchedule, TimeSlot, DoctorUnavailability, ScheduleException
from .serializers import (
    DoctorScheduleSerializer, TimeSlotSerializer,
    DoctorUnavailabilitySerializer, ScheduleExceptionSerializer
)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'healthy'}, status=status.HTTP_200_OK)


class DoctorScheduleViewSet(viewsets.ModelViewSet):
    queryset = DoctorSchedule.objects.all()
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['doctor_id', 'is_active']
    ordering = ['doctor_id', 'weekday', 'start_time']

    def get_queryset(self):
        doctor_id = self.request.query_params.get('doctor_id')
        if doctor_id:
            return DoctorSchedule.objects.filter(doctor_id=doctor_id, is_active=True)
        return DoctorSchedule.objects.filter(is_active=True)


class TimeSlotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['doctor_id', 'appointment_date', 'status']
    ordering = ['appointment_date', 'start_time']

    def get_queryset(self):
        doctor_id = self.request.query_params.get('doctor_id')
        date = self.request.query_params.get('date')
        status_filter = self.request.query_params.get('status')

        queryset = TimeSlot.objects.filter(status='available')

        if doctor_id:
            queryset = queryset.filter(schedule__doctor_id=doctor_id)
        if date:
            queryset = queryset.filter(appointment_date=date)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('appointment_date', 'start_time')

    @action(detail=False, methods=['get'])
    def available(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')

        if not doctor_id or not date_str:
            return Response({'error': 'doctor_id and date are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for exceptions
        exception = ScheduleException.objects.filter(
            doctor_id=doctor_id,
            exception_date=date
        ).exists()

        if exception:
            return Response({'slots': []}, status=status.HTTP_200_OK)

        # Get schedule for the day
        weekday = date.weekday()
        schedule = DoctorSchedule.objects.filter(
            doctor_id=doctor_id,
            weekday=weekday,
            is_active=True
        ).first()

        if not schedule:
            return Response({'slots': []}, status=status.HTTP_200_OK)

        # Check for unavailability
        unavailable = DoctorUnavailability.objects.filter(
            doctor_id=doctor_id,
            start_datetime__date=date,
            end_datetime__date=date
        ).exists()

        if unavailable:
            return Response({'slots': []}, status=status.HTTP_200_OK)

        # Get or create time slots for the day
        slots = TimeSlot.objects.filter(
            schedule=schedule,
            appointment_date=date,
            status='available'
        ).order_by('start_time')

        if not slots.exists():
            # Generate slots
            current_time = datetime.combine(date, schedule.start_time)
            end_time = datetime.combine(date, schedule.end_time)

            while current_time < end_time:
                slot_end = current_time + timedelta(minutes=schedule.slot_duration)
                if slot_end <= end_time:
                    TimeSlot.objects.get_or_create(
                        schedule=schedule,
                        appointment_date=date,
                        start_time=current_time.time(),
                        end_time=slot_end.time(),
                        defaults={'status': 'available'}
                    )
                current_time = slot_end

            slots = TimeSlot.objects.filter(
                schedule=schedule,
                appointment_date=date,
                status='available'
            ).order_by('start_time')

        serializer = TimeSlotSerializer(slots, many=True)
        return Response({'date': date, 'slots': serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        slot = self.get_object()
        if slot.status != 'available':
            return Response({'error': 'Slot is not available'}, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = request.data.get('appointment_id')
        if not appointment_id:
            return Response({'error': 'appointment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        slot.status = 'booked'
        slot.appointment_id = appointment_id
        slot.save()

        return Response(TimeSlotSerializer(slot).data, status=status.HTTP_200_OK)


class DoctorUnavailabilityViewSet(viewsets.ModelViewSet):
    queryset = DoctorUnavailability.objects.all()
    serializer_class = DoctorUnavailabilitySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['doctor_id']
    ordering = ['-start_datetime']

    def get_queryset(self):
        doctor_id = self.request.query_params.get('doctor_id')
        if doctor_id:
            return DoctorUnavailability.objects.filter(doctor_id=doctor_id)
        return DoctorUnavailability.objects.all()


class ScheduleExceptionViewSet(viewsets.ModelViewSet):
    queryset = ScheduleException.objects.all()
    serializer_class = ScheduleExceptionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['doctor_id', 'exception_type']
    ordering = ['-exception_date']

    def get_queryset(self):
        doctor_id = self.request.query_params.get('doctor_id')
        if doctor_id:
            return ScheduleException.objects.filter(doctor_id=doctor_id)
        return ScheduleException.objects.all()
