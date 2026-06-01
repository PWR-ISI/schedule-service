import uuid

from django.db import models


class SlotStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    CONFIRMED = "confirmed", "Confirmed"
    BLOCKED = "blocked", "Blocked"


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class DoctorSchedule(models.Model):
    """Recurring working-hours template; Slots are generated from it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField()
    weekday = models.IntegerField(help_text="0=Monday..6=Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(default=30)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("doctor_id", "weekday", "start_time", "valid_from")]
        ordering = ["doctor_id", "weekday", "start_time"]

    def __str__(self) -> str:
        return f"DoctorSchedule {self.doctor_id} weekday={self.weekday}"


class Slot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField()
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=SlotStatus.choices,
        default=SlotStatus.AVAILABLE,
        db_index=True,
    )
    appointment_id = models.UUIDField(null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor_id", "start_time"],
                name="uniq_doctor_start_time",
            ),
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="slot_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["doctor_id", "status", "start_time"]),
        ]
        ordering = ["start_time"]

    def __str__(self) -> str:
        return f"Slot {self.id} doctor={self.doctor_id} {self.start_time}->{self.end_time} {self.status}"


class Appointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient_id = models.UUIDField(db_index=True)
    slot = models.OneToOneField(Slot, on_delete=models.PROTECT, related_name="appointment")
    status = models.CharField(
        max_length=16,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient_id", "-created_at"])]

    def __str__(self) -> str:
        return f"Appointment {self.id} patient={self.patient_id} status={self.status}"


class AppointmentFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="files"
    )
    original_name = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=512)
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"AppointmentFile {self.id} appointment={self.appointment_id}"
