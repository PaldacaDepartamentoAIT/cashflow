# Arquitectura

## Qué es

Sistema multi-organización de control de gastos. Un usuario puede pertenecer a varias organizaciones. Tras el login elige una; esa elección vive en la **sesión** (`org_id`, `org_name`), no en la URL.

Idioma de UI y dominio: español (Venezuela). Zona horaria: `America/Caracas`.

## Apps Django

| App | Prefijo URL | Rol |
|-----|-------------|-----|
| `CashFlow` | — | Proyecto: settings, `urls.py`, `db.py`, `debug.py` |
| `accounts` | `/accounts/` | Auth y perfil (rol) |
| `organizations` | `/` | Toda la operación diaria |
| `BCV` | `/bcv/` | API e histórico de tasas |
| `superadmin_panel` | `/superadmin/` | Administración global |

También existe `/admin/` (Django admin) y `/health/`.

## Flujo de un usuario normal

```
Login
  → dashboard (lista de orgs con OrganizationAccess)
  → seleccionar_organizacion  (única vista que valida el acceso)
  → home_organizacion
  → transacciones / cuentas / categorías / proyectos
  → salir_organizacion (limpia la sesión)
```

Un **superusuario** nunca entra a ese flujo: el login lo manda a `/superadmin/` y `SuperuserPanelMiddleware` redirige cualquier otra ruta (salvo logout, `/admin/`, `/health/` y estáticos).

## Permisos

Hay dos ejes independientes:

1. **Organización:** pertenencia vía `OrganizationAccess` (tabla puente user↔org).
2. **Rol de escritura:** `Profile.edit` = `Editor` o `Viewer`.
   - Decorador `viewer_restricted` en las vistas que mutan.
   - Context processor `user_permissions` para ocultar botones en plantillas.
   - Los superusers se tratan siempre como editores, pero no usan la app de orgs.

Proyectos compartidos añaden un tercer eje: `ProjectOrganizationAccess` (otra org ve el proyecto) y `ProjectUserAccess` (qué usuarios lo ven).

## Dual moneda

Cada transacción (y el saldo inicial de cuenta) guarda:

| Campo | Uso |
|-------|-----|
| `amount_bs`, `amount_usd`, `daily_rate` | Modo **BCV** (cuentas en bolívares) |
| `bank_fee_bs`, `bank_fee_usd` | Comisiones en modo BCV |
| `real_dollars`, `bank_fee_real_usd` | Modo **real** (cuentas en USD) |

La UI filtra con `view_mode=bcv|real`. La conversión del monto faltante está en `organizations/amounts.py` y se replica en `TransactionForm.clean()`.

## Logging de dominio

Usar `debug_event(event, **context)` (`CashFlow/debug.py`), no `print` ni loggers sueltos.

- Prefijo `transaccion.*` → `logs/transactions.log`
- Prefijo `cuenta.*` → logger de cuentas
- Resto → `logs/app.log`
- Eventos con `.error` o `acceso_denegado` suben de nivel

## Principios al añadir código

- Vista org-scoped: `@login_required`, leer `org_id` de sesión, y (recomendado) revalidar `OrganizationAccess`.
- Mutación: además `@viewer_restricted`.
- Misma regla de conversión en form y en `amounts.py`.
- No poner org en la URL salvo que se rediseñe el scoping.
