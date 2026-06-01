from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DoctorAvailabilityViewSet,
    DoctorScheduleViewSet,
    SlotViewSet,
    AppointmentViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("slots", SlotViewSet, basename="slot")
router.register("doctor-schedules", DoctorScheduleViewSet, basename="doctor-schedule")
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = router.urls + [
    path(
        "doctors/<uuid:doctor_id>/availability",
        DoctorAvailabilityViewSet.as_view({"get": "availability"}),
        name="doctor-availability",
    ),
]
