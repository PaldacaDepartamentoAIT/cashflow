#!/bin/sh
set -e

if [ "$DJANGO_USE_SQLITE" != "1" ]; then
  echo "Esperando conexión a MySQL en ${DB_HOST:-mysql}:${DB_PORT:-3306}..."
  python <<'PY'
import os
import socket
import time

host = os.environ.get("DB_HOST", "mysql")
port = int(os.environ.get("DB_PORT", "3306"))

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(2)
else:
    raise SystemExit(f"No se pudo conectar a MySQL en {host}:{port} tras 120s")
PY
  echo "MySQL disponible."
fi

echo "Aplicando migraciones..."
python manage.py migrate --noinput

exec "$@"
