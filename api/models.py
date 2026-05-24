from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

class DoctorSchedule(models.Model):
    WEEKDAYS = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )

    doctor_id = models.IntegerField(db_index=True)
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration = models.IntegerField(default=30, help_text='Duration in minutes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'doctor_schedules'
        ordering = ['doctor_id', 'weekday', 'start_time']
        unique_together = ('doctor_id', 'weekday', 'start_time')

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError('Start time must be before end time')

    def __str__(self):
        return f"Doctor {self.doctor_id} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class TimeSlot(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('blocked', 'Blocked'),
    )

    schedule = models.ForeignKey(DoctorSchedule, on_delete=models.CASCADE, related_name='time_slots')
    appointment_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    appointment_id = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'time_slots'
        ordering = ['appointment_date', 'start_time']
        indexes = [
            models.Index(fields=['schedule', 'appointment_date', 'status']),
            models.Index(fields=['doctor_id', 'appointment_date']),
        ]

    def __str__(self):
        return f"{self.schedule.doctor_id} - {self.appointment_date} {self.start_time}-{self.end_time}"

    @property
    def doctor_id(self):
        return self.schedule.doctor_id


class DoctorUnavailability(models.Model):
    doctor_id = models.IntegerField(db_index=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctor_unavailability'
        ordering = ['-start_datetime']

    def clean(self):
        if self.start_datetime >= self.end_datetime:
            raise ValidationError('Start time must be before end time')

    def __str__(self):
        return f"Doctor {self.doctor_id} unavailable from {self.start_datetime} to {self.end_datetime}"


class ScheduleException(models.Model):
    EXCEPTION_TYPES = (
        ('holiday', 'Holiday'),
        ('leave', 'Medical Leave'),
        ('maintenance', 'System Maintenance'),
        ('special', 'Special Case'),
    )

    doctor_id = models.IntegerField(db_index=True)
    exception_date = models.DateField()
    exception_type = models.CharField(max_length=20, choices=EXCEPTION_TYPES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedule_exceptions'
        ordering = ['-exception_date']
        unique_together = ('doctor_id', 'exception_date')

    def __str__(self):
        return f"Exception for Doctor {self.doctor_id} on {self.exception_date}"
