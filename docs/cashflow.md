# Módulo CashFlow

Configuración del **proyecto** Django (no es una app de negocio). Paquete: `CashFlow/`.

## Archivos

| Archivo | Función |
|---------|---------|
| `settings.py` | Entorno, seguridad, apps, estáticos, logging |
| `db.py` | Elección de motor (URL / SQLite / MySQL) |
| `urls.py` | Rutas raíz + healthcheck |
| `wsgi.py` / `asgi.py` | Entrada WSGI; shim opcional PyMySQL |
| `debug.py` | `debug_event` y `first_form_error` |
| `__init__.py` | Instala PyMySQL como MySQLdb si está instalado |
| `test_db_url.py` | Tests de parseo `DATABASE_URL` y `/health/` |

`settings.py` y `db.py` están en `.gitattributes` con `merge=ours`: al fusionar `main` ↔ `dev` se conserva la versión de la rama destino.

## Entorno

Variable `DJANGO_ENV`: `development` (default) o `production`.

| | Desarrollo | Producción |
|--|------------|------------|
| `DEBUG` | 1 | 0 (salvo env) |
| BD | SQLite (`DJANGO_USE_SQLITE=1`) | `DATABASE_URL` o MySQL `DB_*` |
| `SECRET_KEY` | Default inseguro | Obligatoria y distinta del default |
| Cookies | No `Secure` | `Secure` por defecto |
| Estáticos | WhiteNoise + finders | `CompressedManifestStaticFilesStorage` |

Producción también lee `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DOMAIN`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`.

## Base de datos (`db.py`)

Orden:

1. Si existe `DATABASE_URL` → Postgres, MySQL o SQLite según el esquema (`postgres://`, `mysql://`, `sqlite://`).
2. Si `DJANGO_USE_SQLITE=1` → fichero SQLite (`SQLITE_DB_NAME` o `test_db.sqlite3`).
3. Si no → MySQL con `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

Postgres: `CONN_MAX_AGE` (default 60), `CONN_HEALTH_CHECKS`, `sslmode` desde la query o `DB_SSLMODE`.

## URLs raíz

```
/health/          → texto "ok" (sin auth, sin ping a BD)
/admin/           → Django admin
/accounts/        → accounts.urls
/bcv/             → BCV.urls
/superadmin/      → superadmin_panel.urls
/                 → organizations.urls
```

## Logging (`debug.py`)

```python
debug_event("transaccion.creada", user=..., trans_id=...)
```

- Redacta claves cuyo nombre contiene `password`, `csrf`, `token` o `secret`.
- Nivel ERROR si el evento contiene `.error`; WARNING si contiene `acceso_denegado`.
- En `DEBUG` también imprime a consola.

Handlers en `settings.py`: `app.log`, `server_errors.log`, `transactions.log`, `application_errors.log`, `cron_bcv.log` (rotativos). Directorio: `DJANGO_LOG_DIR` o `logs/`.

## Estáticos

- Origen: `static/`
- Destino collectstatic: `staticfiles/`
- WhiteNoise en el middleware, después de `SecurityMiddleware`

No hay `MEDIA_` ni `FileField` en el dominio actual.

## Tests

`conftest.py` sustituye `DATABASES` por SQLite `:memory:` durante pytest. `pytest.ini` apunta a `CashFlow.settings`.
