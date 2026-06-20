#!/usr/bin/env sh
set -e

DB_HOST="${DJANGO_DB_HOST:-db}"
DB_PORT="${DJANGO_DB_PORT:-5432}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done
echo "Database is up."

python manage.py makemigrations scheduling --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput || true

# Seed sample slots if not already present
python manage.py seed_slots --doctor-id "00000000-0000-0000-0000-000000000001" --days 30 || true

# Start SQS event consumer in background to handle payment/appointment events
python manage.py consume_events &

exec "$@"
