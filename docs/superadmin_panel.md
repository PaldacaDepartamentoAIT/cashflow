# Módulo superadmin_panel

Área **solo para `is_superuser`**. No define modelos propios: administra `User`, `Profile`, `Organization`, accesos, tasas BCV y `TransactionAuditLog`.

Prefijo: `/superadmin/`.

## Por qué existe

Los superusers no deben mezclarse con el flujo de una organización (ni elegir org ni cargar txs). El panel es el único sitio de gobierno: usuarios, orgs, tasas y auditoría global.

## Barreras

1. **`@superadmin_required`** (`decorators.py`): no autenticado → login; no superuser → 403; superuser → `clear_org_session` y sigue.
2. **`SuperuserPanelMiddleware`**: si hay superuser autenticado y el path no está permitido, redirect a `superadmin_dashboard`.

Prefijos permitidos:

- `/superadmin/`
- `/accounts/logout/`
- `/admin/`
- `/health/`
- `/static/`, `/media/`

3. **Login** (`accounts.LoginView`): éxito de superuser → este panel.

## Rutas

| URL | Nombre | Acción |
|-----|--------|--------|
| `/superadmin/` | `superadmin_dashboard` | Conteos globales |
| `/superadmin/usuarios/` | `superadmin_usuarios` | Listado |
| `/superadmin/usuarios/guardar/` | `superadmin_crear_usuario` | Alta |
| `/superadmin/usuarios/guardar/<id>/` | `superadmin_editar_usuario` | Edición (rol, staff, superuser, clave) |
| `/superadmin/usuarios/eliminar/<id>/` | `superadmin_eliminar_usuario` | Baja; no puede borrarse a sí mismo |
| `/superadmin/organizaciones/` | `superadmin_organizaciones` | Listado + métricas |
| `/superadmin/organizaciones/crear/` | `superadmin_crear_organizacion_wizard` | Wizard: org, usuarios, cuentas + saldo inicial |
| `/superadmin/organizaciones/guardar/<id>/` | `superadmin_editar_organizacion` | Nombre |
| `/superadmin/organizaciones/eliminar/<id>/` | `superadmin_eliminar_organizacion` | Cascade |
| `/superadmin/organizaciones/<id>/accesos/` | `superadmin_accesos_organizacion` | Sync `OrganizationAccess` |
| `/superadmin/tasas-bcv/` | `superadmin_tasas_bcv` | Calendario / listado |
| `/superadmin/tasas-bcv/api/` | `superadmin_tasas_bcv_api` | JSON (esta sí autenticada) |
| `/superadmin/tasas-bcv/guardar/` | `superadmin_guardar_tasa_bcv` | Alta/edición manual |
| `/superadmin/tasas-bcv/eliminar/<id>/` | `superadmin_eliminar_tasa_bcv` | |
| `/superadmin/auditoria/` | `superadmin_auditoria` | `TransactionAuditLog` |
| `/superadmin/auditoria/<id>/instantanea/` | `superadmin_auditoria_snapshot` | Partial del JSON |

## Formularios (`forms.py`)

- `SuperadminUserCreateForm` / `SuperadminUserEditForm`: username, email, password, `edit` (Profile), `is_active`, `is_staff`, `is_superuser`. Al autoeditarse se fuerza `is_superuser` e `is_active`.
- `SuperadminOrganizationForm`, `SuperadminOrganizationWizardForm`: el wizard no permite asignar superusers como miembros.
- `OrganizationAccessForm`: M2M de usuarios (no superuser).
- `BcvRateForm`: sobre `ExchangeRateHistory`.

## Wizard de organización

POST (también AJAX):

1. Crea `Organization`.
2. Crea `OrganizationAccess` para los usuarios elegidos.
3. Crea una o más `Account` (BS y/o USD) con datos bancarios.
4. Si hay saldo, `create_initial_balance_transaction` (misma lógica que la app de orgs).

## Context processor

`superadmin_panel`: pone `is_superadmin_panel` si el `url_name` empieza por `superadmin`, para el layout.

## Utilidad

`utils.clear_org_session`: borra `org_id` y `org_name`.

## Tests

`superadmin_panel/tests.py`: login → panel, middleware bloquea dashboard org, 403 de usuario normal, listado usuarios, no auto-borrado, wizard BS y wizard USD. No cubre tasas ni auditoría.
