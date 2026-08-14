# Operaciones

Comandos de desarrollo, tests, logs, cron y despliegue.

## Comandos

```bash
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python create_superuser.py          # script legacy con clave fija: no usar en producción
python generate_dbml.py
python manage.py bcv
python manage.py bcv --strict-window
pytest
pytest organizations/tests.py
python manage.py test
```

No hay ruff/black/flake8 configurados.

## Tests

| Pieza | Rol |
|-------|-----|
| `pytest.ini` | `DJANGO_SETTINGS_MODULE = CashFlow.settings` |
| `conftest.py` | SQLite `:memory:` para toda la sesión |
| `requirements.txt` | Incluye `pytest` y `pytest-django` (sin pin) |
| `requirements-docker.txt` | Sin pytest |

## Logs

Directorio `logs/` (o `DJANGO_LOG_DIR`):

| Fichero | Contenido |
|---------|-----------|
| `app.log` | App general |
| `transactions.log` | Eventos `transaccion.*` |
| `application_errors.log` | WARNING+ de dominio |
| `server_errors.log` | Django request/server + `cashflow.errors` |
| `cron_bcv.log` | Comando `bcv` |

Guía cron Namecheap: `logs/CRON.md`.

## Docker (VPS)

- `Dockerfile`: Python 3.12, Gunicorn en **8081**, usuario no-root, entrypoint con espera de Postgres + migrate + collectstatic.
- `docker-compose.yml`: `web` + Postgres + Caddy + profile `cron` (BCV).
- `docker-compose.coolify.yml`: solo `web` (el proxy y la BD los pone Coolify).
- `docker/entrypoint.sh`, `docker/Caddyfile`, `docker/bcv-loop.sh`.
- Variables: `.env.example` (no commitear `.env`).

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose --profile cron up -d
```

## Coolify

Paso a paso: [`../DESPLIEGUE-COOLIFY.md`](../DESPLIEGUE-COOLIFY.md).

Resumen: recurso PostgreSQL + aplicación Dockerfile, puerto **8081**, `DATABASE_URL` internal, Scheduled Task para BCV. No desplegar el compose que incluye Caddy.

## Namecheap (histórico)

- `passenger_wsgi.py`, `.cpanel.yml`, `build.sh`
- `.github/workflows/deploy.yml`: push a `main` → SSH, `requirements.txt`, migrate, collectstatic, `tmp/restart.txt`
- MySQL vía `DB_*`, no Postgres

`manage.py` está en la **raíz** del repo, no dentro de `CashFlow/`.

## Dependencias

| Fichero | Destino |
|---------|---------|
| `requirements.txt` | Dev + Namecheap (Django, MySQL, pytest, reportlab, …) |
| `requirements-docker.txt` | Imagen: mismo set de app + gunicorn + psycopg, sin MySQL ni pytest |
