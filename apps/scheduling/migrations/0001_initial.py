import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DoctorSchedule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("doctor_id", models.UUIDField(db_index=True)),
                ("facility_id", models.UUIDField()),
                ("weekday", models.IntegerField(help_text="0=Monday..6=Sunday")),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("slot_duration_minutes", models.PositiveIntegerField(default=30)),
                ("valid_from", models.DateField()),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["doctor_id", "weekday", "start_time"],
            },
        ),
        migrations.CreateModel(
            name="Slot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("doctor_id", models.UUIDField(db_index=True)),
                ("facility_id", models.UUIDField()),
                ("start_time", models.DateTimeField(db_index=True)),
                ("end_time", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("reserved", "Reserved"),
                            ("confirmed", "Confirmed"),
                            ("blocked", "Blocked"),
                        ],
                        db_index=True,
                        default="available",
                        max_length=16,
                    ),
                ),
                ("appointment_id", models.UUIDField(blank=True, null=True)),
                ("reservation_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["start_time"],
            },
        ),
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("patient_id", models.UUIDField(db_index=True)),
                (
                    "slot",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointment",
                        to="scheduling.slot",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_payment", "Pending payment"),
                            ("paid", "Paid"),
                            ("scheduled", "Scheduled"),
                            ("cancelled", "Cancelled"),
                            ("completed", "Completed"),
                            ("expired", "Expired"),
                            ("failed", "Failed"),
                        ],
                        default="scheduled",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True, default="")),
                ("visit_summary", models.TextField(blank=True, default="")),
                ("cancellation_reason", models.TextField(blank=True, default="")),
                ("payment_order_id", models.CharField(blank=True, default="", max_length=64)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AppointmentFile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="scheduling.appointment",
                    ),
                ),
                ("original_name", models.CharField(max_length=255)),
                ("s3_key", models.CharField(max_length=512)),
                ("content_type", models.CharField(default="application/octet-stream", max_length=100)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("uploaded_by", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="slot",
            constraint=models.UniqueConstraint(fields=["doctor_id", "start_time"], name="uniq_doctor_start_time"),
        ),
        migrations.AddConstraint(
            model_name="slot",
            constraint=models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="slot_end_after_start",
            ),
        ),
        migrations.AddIndex(
            model_name="slot",
            index=models.Index(fields=["doctor_id", "status", "start_time"], name="scheduling_doctor__1b7498_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="doctorschedule",
            unique_together={("doctor_id", "weekday", "start_time", "valid_from")},
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["patient_id", "-created_at"], name="scheduling_patient_44d7d5_idx"),
        ),
    ]