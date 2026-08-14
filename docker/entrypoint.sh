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
from urllib.parse import unquote, urlparse

url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    sys.exit(0)

attempts = int(os.environ.get("DB_WAIT_ATTEMPTS", "30"))
delay = float(os.environ.get("DB_WAIT_SECONDS", "2"))

try:
    import pymysql
except ImportError:
    print("PyMySQL no está instalado; se omite la espera de MySQL.", file=sys.stderr)
    sys.exit(0)

parsed = urlparse(url)
scheme = (parsed.scheme or "").split("+")[0].lower()
if scheme not in {"mysql", "mysql2"}:
    print(
        f"DATABASE_URL debe ser mysql:// (recibido: {parsed.scheme!r}).",
        file=sys.stderr,
    )
    sys.exit(1)

host = parsed.hostname or "127.0.0.1"
port = parsed.port or 3306
user = unquote(parsed.username) if parsed.username else ""
password = unquote(parsed.password) if parsed.password else ""
database = unquote(parsed.path.lstrip("/"))

last_error = None
for attempt in range(1, attempts + 1):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database or None,
            connect_timeout=5,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        print(f"MySQL disponible (intento {attempt}).")
        sys.exit(0)
    except Exception as exc:
        last_error = exc
        print(f"Esperando MySQL ({attempt}/{attempts}): {exc}", file=sys.stderr)
        time.sleep(delay)

print(f"No se pudo conectar a MySQL: {last_error}", file=sys.stderr)
sys.exit(1)
PY

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
