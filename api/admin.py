from django.contrib import admin
from .models import DoctorSchedule, TimeSlot, DoctorUnavailability, ScheduleException


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'get_weekday_display', 'start_time', 'end_time', 'slot_duration', 'is_active')
    list_filter = ('is_active', 'weekday')
    search_fields = ('doctor_id',)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'appointment_date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'appointment_date')
    search_fields = ('schedule__doctor_id',)


@admin.register(DoctorUnavailability)
class DoctorUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'start_datetime', 'end_datetime', 'reason')
    list_filter = ('start_datetime',)
    search_fields = ('doctor_id', 'reason')


@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'exception_date', 'exception_type')
    list_filter = ('exception_type', 'exception_date')
    search_fields = ('doctor_id',)
