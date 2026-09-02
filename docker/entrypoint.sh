#!/bin/sh
set -e

# Las fotos de las transacciones viven en MEDIA_ROOT. Si esa ruta no es un punto
# de montaje, está en la capa de escritura del contenedor y desaparece en el
# próximo despliegue (Coolify reconstruye la imagen y crea un contenedor nuevo).
# Mejor abortar el arranque que aceptar subidas que se van a borrar en silencio.
# Un punto de montaje tiene distinto número de dispositivo que su directorio
# padre; se compara con stat para no depender de `mountpoint` (util-linux).
MEDIA_DIR="${DJANGO_MEDIA_ROOT:-/app/media}"
mkdir -p "$MEDIA_DIR"
if [ "$DJANGO_ALLOW_EPHEMERAL_MEDIA" != "1" ] \
   && [ "$(stat -c %d "$MEDIA_DIR")" = "$(stat -c %d "$MEDIA_DIR/..")" ]; then
  echo "ERROR: $MEDIA_DIR no es un volumen persistente; las fotos de las" >&2
  echo "transacciones se perderían en el próximo despliegue. Declararlo en" >&2
  echo "Coolify: recurso Application -> Storages -> Volume en $MEDIA_DIR." >&2
  echo "Si el entorno es desechable a propósito: DJANGO_ALLOW_EPHEMERAL_MEDIA=1" >&2
  exit 1
fi

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
