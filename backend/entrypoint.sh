#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 0.2
done
echo "PostgreSQL is up."

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${CREATE_DEMO_USERS:-}" = "true" ]; then
  python manage.py shell <<EOF
from accounts.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@askayurveda.com', 'admin123', role='admin')
    print("Admin created: admin / admin123")
if not User.objects.filter(username='operator1').exists():
    User.objects.create_user('operator1', 'op1@askayurveda.com', 'operator123', role='operator', first_name='Anna', last_name='Smith')
    print("Operator created: operator1 / operator123")
EOF
fi

WORKERS="${GUNICORN_WORKERS:-3}"
exec gunicorn crm.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "$WORKERS" \
  --timeout 300 \
  --access-logfile - \
  --error-logfile -