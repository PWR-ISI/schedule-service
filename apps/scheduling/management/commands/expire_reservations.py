from django.core.management.base import BaseCommand

from apps.scheduling.services import SchedulingService


class Command(BaseCommand):
    help = "Release any slots whose reservation TTL has passed."

    def handle(self, *args, **opts):
        released = SchedulingService.expire_reservations()
        self.stdout.write(f"Released {released} expired reservation(s).")
