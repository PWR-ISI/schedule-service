from rest_framework import serializers

from .models import DoctorSchedule, Slot, SlotStatus


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = (
            "id",
            "doctor_id",
            "facility_id",
            "start_time",
            "end_time",
            "status",
            "appointment_id",
            "reservation_expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "appointment_id", "reservation_expires_at", "created_at", "updated_at")


class SlotCreateSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    facility_id = serializers.UUIDField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("end_time must be after start_time.")
        return attrs


class SlotReserveSerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    ttl_minutes = serializers.IntegerField(required=False, min_value=1, max_value=120)


class DoctorScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSchedule
        fields = (
            "id",
            "doctor_id",
            "facility_id",
            "weekday",
            "start_time",
            "end_time",
            "slot_duration_minutes",
            "valid_from",
            "valid_until",
        )
        read_only_fields = ("id",)
