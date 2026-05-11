from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DoctorAvailabilityViewSet, DoctorScheduleViewSet, SlotViewSet

router = DefaultRouter()
router.register("slots", SlotViewSet, basename="slot")
router.register("doctor-schedules", DoctorScheduleViewSet, basename="doctor-schedule")

urlpatterns = router.urls + [
    path(
        "doctors/<uuid:doctor_id>/availability/",
        DoctorAvailabilityViewSet.as_view({"get": "availability"}),
        name="doctor-availability",
    ),
]
