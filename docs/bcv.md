# Módulo BCV

Obtiene y guarda las tasas oficiales USD/EUR (Banco Central de Venezuela), con respaldo en DolarAPI.

Prefijo URL: `/bcv/`.

## Modelo

`ExchangeRateHistory`: una fila por `(rate_date, source, currency)`.

- Fuentes: `bcv`, `dolarapi`
- Monedas: `USD`, `EUR`
- `rate` (hasta 8 decimales), `raw_label`, `fetched_at` (`auto_now=True`)

Admin: `BCV/admin.py` (listado, filtros, búsqueda).

## Servicio (`BCV/services/bcv_scrapper.py`)

| Función | Qué hace |
|---------|----------|
| `scrape_bcv_rates()` | GET `https://www.bcv.org.ve/` (timeout 30s, SSL con certifi). Parsea HTML con regex (fecha valor + USD/EUR). |
| `_fetch_dolarapi_rates()` | `ve.dolarapi.com` (oficial USD y EUR). Fecha = hoy. |
| `scrape_with_fallback()` | BCV; si lanza cualquier excepción, DolarAPI. |
| `_store_rates()` | `update_or_create` por moneda. |
| `get_bcv_rates_cached()` | Cache Django 3600s; `force_refresh` ignora cache. |
| `get_dolarapi_parallel_rates_cached()` | Paralelo USD/EUR, TTL 1800s. |
| `get_rate_for_date()` | Histórico (prioriza BCV). Si la fecha es **hoy**, refresca. |
| `as_dashboard_rates()` | Payload para home y API: BCV + paralelo. |

`BCV_SSL_VERIFY=0` desactiva la verificación SSL del scrape (solo diagnóstico).

No hay `CACHES` custom en settings: cada proceso Gunicorn tiene su LocMemCache.

## API HTTP

`GET /bcv/rates/` — `rates_api`, `@require_GET`, **sin login**.

| Query | Respuesta |
|-------|-----------|
| (ninguna) | `{ ok, rates }` = `as_dashboard_rates()` |
| `?date=YYYY-MM-DD&currency=USD` | `{ ok, rate, currency, date }` o 404 |
| Error interno | 502 + `"error": str(exc)` |

La app de organizaciones **no** depende de este endpoint para grabar txs: llama al servicio Python directo (`get_bcv_rate` en `organizations/views.py`).

## Comando de gestión

```bash
python manage.py bcv                 # scrape ya
python manage.py bcv --strict-window # solo si la hora local está en --window-hours (default 09,15)
```

Logger `cashflow.cron.bcv` → `logs/cron_bcv.log`.

Producción:

- Namecheap: crontab 09:00 y 15:00 (`logs/CRON.md`, `scripts/run_cron_bcv.sh`).
- Docker: `docker compose --profile cron` (`docker/bcv-loop.sh`).
- Coolify: Scheduled Task `python manage.py bcv --strict-window`.

## Tests

`BCV/tests.py`: integración con histórico y que `get_bcv_rate` prefiera BCV frente a DolarAPI. No hay tests del parser HTML ni del fallback.
