from django.contrib import admin

from .models import DoctorSchedule, Slot


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ("doctor_id", "facility_id", "weekday", "start_time", "end_time", "valid_from")
    list_filter = ("weekday", "facility_id")
    search_fields = ("doctor_id",)


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("id", "doctor_id", "start_time", "end_time", "status", "reservation_expires_at")
    list_filter = ("status",)
    search_fields = ("doctor_id", "appointment_id")
    readonly_fields = ("id", "created_at", "updated_at")
