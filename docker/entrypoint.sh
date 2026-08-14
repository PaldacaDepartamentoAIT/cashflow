#!/bin/sh
set -e

mkdir -p /app/logs /app/staticfiles
chown -R appuser:appuser /app/logs /app/staticfiles 2>/dev/null || true

if [ "$(id -u)" = "0" ]; then
  exec gosu appuser "$0" "$@"
fi

python - <<'PY'
import os
import sys
import time

url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    sys.exit(0)

attempts = int(os.environ.get("DB_WAIT_ATTEMPTS", "30"))
delay = float(os.environ.get("DB_WAIT_SECONDS", "2"))

try:
    import psycopg
except ImportError:
    print("psycopg no está instalado; se omite la espera de PostgreSQL.", file=sys.stderr)
    sys.exit(0)

last_error = None
for attempt in range(1, attempts + 1):
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print(f"PostgreSQL disponible (intento {attempt}).")
        sys.exit(0)
    except Exception as exc:
        last_error = exc
        print(f"Esperando PostgreSQL ({attempt}/{attempts}): {exc}", file=sys.stderr)
        time.sleep(delay)

print(f"No se pudo conectar a PostgreSQL: {last_error}", file=sys.stderr)
sys.exit(1)
PY

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
