from rest_framework import serializers
from .models import DoctorSchedule, TimeSlot, DoctorUnavailability, ScheduleException


class DoctorScheduleSerializer(serializers.ModelSerializer):
    weekday_name = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = DoctorSchedule
        fields = ('id', 'doctor_id', 'weekday', 'weekday_name', 'start_time', 'end_time', 'slot_duration', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class TimeSlotSerializer(serializers.ModelSerializer):
    doctor_id = serializers.SerializerMethodField()

    class Meta:
        model = TimeSlot
        fields = ('id', 'doctor_id', 'appointment_date', 'start_time', 'end_time', 'status', 'appointment_id', 'notes', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_doctor_id(self, obj):
        return obj.schedule.doctor_id


class DoctorUnavailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorUnavailability
        fields = ('id', 'doctor_id', 'start_datetime', 'end_datetime', 'reason', 'created_at')
        read_only_fields = ('id', 'created_at')


class ScheduleExceptionSerializer(serializers.ModelSerializer):
    exception_type_display = serializers.CharField(source='get_exception_type_display', read_only=True)

    class Meta:
        model = ScheduleException
        fields = ('id', 'doctor_id', 'exception_date', 'exception_type', 'exception_type_display', 'description', 'created_at')
        read_only_fields = ('id', 'created_at')


class AvailableSlotsSerializer(serializers.Serializer):
    date = serializers.DateField()
    slots = TimeSlotSerializer(many=True)
