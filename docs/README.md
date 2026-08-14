# Documentación de Control de Gastos

Aplicación Django para el control de gastos y flujo de caja de varias organizaciones, con montos en bolívares y dólares (tasa BCV y dólares reales).

Auditoría de seguridad y calidad: [`../AUDITORIA.md`](../AUDITORIA.md).  
Despliegue en Coolify: [`../DESPLIEGUE-COOLIFY.md`](../DESPLIEGUE-COOLIFY.md).

## Módulos

| Documento | App / capa | Responsabilidad |
|-----------|------------|-----------------|
| [Arquitectura](arquitectura.md) | Todo el sistema | Apps, sesión, permisos, moneda dual |
| [Modelo de datos](modelo-datos.md) | ORM | Entidades y relaciones |
| [CashFlow](cashflow.md) | `CashFlow/` | Settings, BD, URLs, logging, WSGI |
| [Accounts](accounts.md) | `accounts/` | Login, registro, roles Editor/Viewer |
| [Organizations](organizations.md) | `organizations/` | Dominio: orgs, cuentas, txs, proyectos |
| [BCV](bcv.md) | `BCV/` | Tasas de cambio oficiales |
| [Superadmin](superadmin_panel.md) | `superadmin_panel/` | Panel exclusivo de superusuarios |
| [Frontend](frontend.md) | `templates/`, `static/` | UI, JS y CSS |
| [Operaciones](operaciones.md) | Repo / infra | Tests, cron, logs, Docker |

## Arranque local

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

En desarrollo la BD por defecto es SQLite (`DJANGO_ENV=development`, `DJANGO_USE_SQLITE=1`).
