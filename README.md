# schedule-service

Django microservice that owns doctor schedules and time slots for the ISI medical system.

## Responsibilities

- Manage doctor working-hours templates and the slots generated from them.
- Reserve, release, and confirm slots — atomic, row-level locked, with a short TTL during payment.
- Expose availability search.
- Publish `slot.reserved`, `slot.released`, `slot.confirmed` events to SNS.
- Consume `appointment.cancelled`, `payment.failed`, `payment.succeeded` events from SQS.

## Local run (standalone)

```powershell
Copy-Item .env.example .env
docker compose up --build
# http://localhost:8008/health/
# http://localhost:8008/api/docs/
```

## Local run (integrated)

```powershell
cd ..\prod-config
docker compose up --build
# schedule-service published on http://localhost:8004
```

## Tests

```powershell
docker compose run --rm app pip install -r requirements-dev.txt
docker compose run --rm app pytest
```

## Background work

`python manage.py expire_reservations` releases any slots whose `reservation_expires_at` is in the past. Run it on a schedule (cron, EventBridge, ECS scheduled task).

## Environment variables

See `.env.example`. `SCHEDULE_SNS_TOPIC_ARN`, `EVENTS_SQS_QUEUE_URL`, and `AWS_ENDPOINT_URL` are the AWS-facing knobs.

## AWS deployment

See `prod-config/terraform/modules/schedule-service/` for the Terraform module.
