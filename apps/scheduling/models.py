import uuid

from django.db import models


class SlotStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    CONFIRMED = "confirmed", "Confirmed"
    BLOCKED = "blocked", "Blocked"


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
