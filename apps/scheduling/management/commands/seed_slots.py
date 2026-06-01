from datetime import datetime, timedelta, time
import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scheduling.models import Slot, SlotStatus


class Command(BaseCommand):
    help = "Seed sample slots for testing"

    def add_arguments(self, parser):
        parser.add_argument("--doctor-id", type=str, default="00000000-0000-0000-0000-000000000001")
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--slot-duration", type=int, default=30)

    def handle(self, *args, **options):
        doctor_id = options["doctor_id"]
        days = options["days"]
        slot_duration = options["slot_duration"]
        facility_id = "00000000-0000-0000-0000-000000000000"

        # Working hours: 9 AM to 5 PM
        start_hour = 9
        end_hour = 17

        slots_created = 0
        today = timezone.now().date()

        for day_offset in range(days):
            current_date = today + timedelta(days=day_offset)

            # Skip weekends (5=Saturday, 6=Sunday)
            if current_date.weekday() >= 5:
                continue

            # Create slots for this day
            current_time = timezone.make_aware(datetime.combine(current_date, time(start_hour, 0)))
            end_time_of_day = timezone.make_aware(datetime.combine(current_date, time(end_hour, 0)))

            while current_time < end_time_of_day:
                slot_end = current_time + timedelta(minutes=slot_duration)

                # Check if slot already exists
                if not Slot.objects.filter(
                    doctor_id=doctor_id,
                    start_time=current_time,
                ).exists():
                    Slot.objects.create(
                        doctor_id=doctor_id,
                        facility_id=facility_id,
                        start_time=current_time,
                        end_time=slot_end,
                        status=SlotStatus.AVAILABLE,
                    )
                    slots_created += 1

                current_time = slot_end

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Created {slots_created} slots for doctor {doctor_id}"
            )
        )
