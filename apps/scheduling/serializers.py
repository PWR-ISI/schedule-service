from rest_framework import serializers

from .models import DoctorSchedule, Slot, SlotStatus, Appointment, AppointmentFile
from .s3_utils import presigned_url


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


class AppointmentFileSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentFile
        fields = (
            "id",
            "original_name",
            "content_type",
            "size_bytes",
            "created_at",
            "download_url",
        )
        read_only_fields = ("id", "created_at")

    def get_download_url(self, obj):
        if obj.s3_key:
            return presigned_url(obj.s3_key)
        return None


class AppointmentSerializer(serializers.ModelSerializer):
    files = AppointmentFileSerializer(many=True, read_only=True)
    appointment_date = serializers.SerializerMethodField()
    doctor_id = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    appointment_type = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patient_id",
            "doctor_id",
            "doctor_name",
            "patient_name",
            "appointment_date",
            "appointment_type",
            "status",
            "notes",
            "visit_summary",
            "cancellation_reason",
            "payment_order_id",
            "completed_at",
            "cancelled_at",
            "files",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_appointment_date(self, obj):
        return obj.slot.start_time.isoformat()

    def get_doctor_id(self, obj):
        return str(obj.slot.doctor_id)

    def get_doctor_name(self, obj):
        return f"Dr. {obj.slot.doctor_id}"  # Placeholder; real data would come from doctor service

    def get_patient_name(self, obj):
        return f"Patient {obj.patient_id}"  # Placeholder; real data would come from user service

    def get_appointment_type(self, obj):
        return "Regular"  # Placeholder; could be extended with actual types


class AppointmentCreateSerializer(serializers.Serializer):
    slot_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField(required=False, allow_null=True)
    # Set by a receptionist/admin booking on behalf of a patient. Ignored for patients
    # (they always book for themselves).
    patient_id = serializers.UUIDField(required=False, allow_null=True)


class AppointmentCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AppointmentCompleteSerializer(serializers.Serializer):
    visit_summary = serializers.CharField(required=False, allow_blank=True, default="")
