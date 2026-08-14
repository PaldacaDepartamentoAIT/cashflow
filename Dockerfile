FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production \
    DEBUG=0 \
    DJANGO_USE_SQLITE=0

WORKDIR /app

# Dependencias de sistema:
# - default-libmysqlclient-dev/pkg-config/build-essential: compilar mysqlclient
# - libjpeg62-turbo-dev/zlib1g-dev: Pillow
# - curl: healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/staticfiles

# collectstatic no requiere conexión a la BD, solo SECRET_KEY (usa el valor
# por defecto de settings.py si no se pasa uno en build-time).
RUN python manage.py collectstatic --noinput

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "CashFlow.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
