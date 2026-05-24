from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DoctorScheduleViewSet, TimeSlotViewSet,
    DoctorUnavailabilityViewSet, ScheduleExceptionViewSet, health_check
)

router = DefaultRouter()
router.register(r'schedule', DoctorScheduleViewSet, basename='schedule')
router.register(r'slots', TimeSlotViewSet, basename='slots')
router.register(r'unavailability', DoctorUnavailabilityViewSet, basename='unavailability')
router.register(r'exceptions', ScheduleExceptionViewSet, basename='exceptions')

urlpatterns = [
    path('health/', health_check, name='health'),
    path('', include(router.urls)),
]
