"""
Create slots for an explicit date range for one or more doctors.

Usage:
    python manage.py seed_range --doctor-id <UUID> [--doctor-id <UUID> ...] \
        --from 2026-06-10 --to 2026-06-30 [--all-days]

Weekdays only (Mon-Fri) by default, 09:00-17:00, 30-minute slots. Idempotent.
"""
from datetime import datetime, timedelta, time, date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.scheduling.models import Slot, SlotStatus

FACILITY_ID = "00000000-0000-0000-0000-000000000000"


class Command(BaseCommand):
    help = "Seed AVAILABLE slots for given doctors over an explicit date range."

    def add_arguments(self, parser):
        parser.add_argument("--doctor-id", action="append", dest="doctor_ids", required=True,
                            help="Doctor id (cognito_sub). Repeatable.")
        parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD (inclusive)")
        parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD (inclusive)")
        parser.add_argument("--start-hour", type=int, default=9)
        parser.add_argument("--end-hour", type=int, default=17)
        parser.add_argument("--slot-minutes", type=int, default=30)
        parser.add_argument("--all-days", action="store_true", help="Include weekends.")

    def handle(self, *args, **o):
        try:
            d_from = date.fromisoformat(o["date_from"])
            d_to = date.fromisoformat(o["date_to"])
        except ValueError as exc:
            raise CommandError(f"Bad date: {exc}")
        if d_to < d_from:
            raise CommandError("--to must be >= --from")

        grand_total = 0
        for did in o["doctor_ids"]:
            created = 0
            day = d_from
            while day <= d_to:
                if o["all_days"] or day.weekday() < 5:
                    t = timezone.make_aware(datetime.combine(day, time(o["start_hour"], 0)))
                    eod = timezone.make_aware(datetime.combine(day, time(o["end_hour"], 0)))
                    while t < eod:
                        end_t = t + timedelta(minutes=o["slot_minutes"])
                        if not Slot.objects.filter(doctor_id=did, start_time=t).exists():
                            Slot.objects.create(
                                doctor_id=did, facility_id=FACILITY_ID,
                                start_time=t, end_time=end_t, status=SlotStatus.AVAILABLE,
                            )
                            created += 1
                        t = end_t
                day += timedelta(days=1)
            grand_total += created
            self.stdout.write(f"doctor {did}: created {created} slots")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {grand_total} slots for {len(o['doctor_ids'])} doctor(s) "
            f"[{d_from} .. {d_to}]"
        ))
