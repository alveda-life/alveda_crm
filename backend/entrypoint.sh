#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 0.2
done
echo "PostgreSQL is up."

python manage.py makemigrations accounts partners contacts reports producers tasks --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput

python manage.py shell <<'EOF'
from accounts.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        'admin',
        'admin@askayurveda.com',
        'admin123',
        role='admin'
    )
    print("Admin created: admin / admin123")

if not User.objects.filter(username='operator1').exists():
    User.objects.create_user(
        'operator1',
        'op1@askayurveda.com',
        'operator123',
        role='operator',
        first_name='Anna',
        last_name='Smith'
    )
    print("Operator created: operator1 / operator123")
EOF

python manage.py seed_data

exec python manage.py runserver 0.0.0.0:8000