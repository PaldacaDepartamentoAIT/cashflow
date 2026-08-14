# Imagen de producción: Django + Gunicorn (VPS / Contabo)
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libxml2-dev \
        libxslt1-dev \
        libfreetype6-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv

WORKDIR /build
COPY requirements-docker.txt .
RUN pip install -r requirements-docker.txt


FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production \
    DEBUG=0 \
    DJANGO_SETTINGS_MODULE=CashFlow.settings \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gosu \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libxml2 \
        libxslt1.1 \
        libfreetype6 \
        libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --create-home --home-dir /home/appuser appuser \
    && mkdir -p /app/logs /app/staticfiles

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . /app
COPY docker/entrypoint.sh /entrypoint.sh

RUN sed -i 's/\r$//' /entrypoint.sh /app/docker/bcv-loop.sh \
    && chmod +x /entrypoint.sh /app/docker/bcv-loop.sh \
    && chown -R appuser:appuser /app/logs /app/staticfiles

EXPOSE 8081

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "CashFlow.wsgi:application", "--bind", "0.0.0.0:8081", "--workers", "3", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--capture-output"]
