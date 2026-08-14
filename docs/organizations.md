# Módulo organizations

Núcleo de negocio. Casi toda la lógica está en `organizations/views.py` (~2500 líneas) y `organizations/forms.py`.

Rutas en la **raíz** del sitio (`CashFlow/urls.py` incluye `organizations.urls` en `''`).

## Organización y sesión

| URL | Nombre | Vista | Notas |
|-----|--------|-------|--------|
| `/` | `dashboard` | Lista orgs del usuario (`OrganizationAccess`) | Sin org en sesión |
| `/home/` | `home_organizacion` | KPIs, gráficos, filtros día/semana/mes | Requiere `org_id` |
| `/configuracion/` | `configuracion` | Ajustes de la org activa | |
| `/nueva/` | `crear_organizacion` | Alta de org + acceso al creador | `@viewer_restricted` |
| `/seleccionar/<org_id>/` | `seleccionar_organizacion` | Escribe `org_id` / `org_name` | **Única** que valida `OrganizationAccess` |
| `/salir/` | `salir_organizacion` | Borra claves de sesión | |

Patrón del resto de vistas:

```python
org_id = request.session.get('org_id')
if not org_id:
    return redirect('dashboard')  # o home
org = get_object_or_404(Organization, id=org_id)
```

## Transacciones

| URL | Nombre | Mutación |
|-----|--------|----------|
| `/transacciones/` | `lista_transacciones` | Lectura, filtros, paginación |
| `/transacciones/guardar/` | `crear_transaccion` | POST `@viewer_restricted` |
| `/transacciones/guardar/<id>/` | `editar_transaccion` | idem |
| `/transacciones/eliminar/<id>/` | `eliminar_transaccion` | POST |
| `/transacciones/detalle/<id>/` | `detalle_transaccion` | Partial HTML (modal) |
| `/transacciones/exportar-pdf/` | `exportar_pdf_transacciones` | ReportLab |
| `/transacciones/exportar-xlsx/` | `exportar_xlsx_transacciones` | HTML/Excel |

`guardar_transaccion` admite transacciones de la org de sesión **o** de un proyecto compartido si el usuario tiene `ProjectUserAccess`. Cada alta/edición/baja llama a `log_transaction_audit`.

Helpers de listados y reportes: `_get_report_data`, `get_chart_data`, `get_filtered_totals_both`. Modo `view_mode=bcv|real`.

## Categorías

| URL | Nombre |
|-----|--------|
| `/categorias/` | `lista_categorias` |
| `/categorias/guardar/` | `crear_categoria` |
| `/categorias/guardar/<id>/` | `editar_categoria` |
| `/categorias/eliminar/<id>/` | `eliminar_categoria` |

Formulario: `CategoryForm` (`name`, `description`, `color`).

## Cuentas

| URL | Nombre |
|-----|--------|
| `/cuentas/` | `lista_cuentas` |
| `/cuentas/guardar/` | `crear_cuenta` |
| `/cuentas/guardar/<id>/` | `editar_cuenta` |
| `/cuentas/eliminar/<id>/` | `eliminar_cuenta` |
| `/cuentas/detalle/<id>/` | `detalle_cuenta` (movimientos de esa cuenta) |

Al crear con saldo inicial: `create_initial_balance_transaction` (`amounts.py`). Bancos: `banks.py` + JSON en `static/json/`. Validadores: `validators.py` (RIF, número, titular).

## Proyectos y valuaciones

| URL | Nombre |
|-----|--------|
| `/proyectos/` | `lista_proyectos` (propios + compartidos con `ProjectUserAccess`) |
| `/proyectos/guardar/` | `crear_proyecto` (solo org dueña) |
| `/proyectos/guardar/<id>/` | `editar_proyecto` |
| `/proyectos/eliminar/<id>/` | `eliminar_proyecto` |
| `/proyectos/detalle/<id>/` | `detalle_proyecto` (txs, valuaciones, gráficos, compartir) |
| `/valuaciones/guardar/<proj_id>/` | `crear_valuacion` |
| `/valuaciones/guardar/<proj_id>/<val_id>/` | `editar_valuacion` |
| `/valuaciones/eliminar/<val_id>/` | `eliminar_valuacion` |

## Compartir proyecto

| URL | Auth | Función |
|-----|------|---------|
| `/proyectos/<id>/compartir/` | Login | Genera token + `ProjectShareLink` (pide password de módulo) |
| `/proyectos/enlaces/listar/` | Login | JSON de enlaces |
| `/proyectos/enlaces/<id>/eliminar/` | Login | Revoca |
| `/proyectos/compartido/<token>/` | **Pública** | Vista de solo lectura |

Estas tres primeras **no** llevan `@viewer_restricted`. El token se firma con `django.core.signing` (salt de proyecto) y debe existir la fila para seguir vigente.

## Formularios (`forms.py`)

| Form | Modelo | Notas |
|------|--------|-------|
| `TransactionForm` | Transaction | Dual moneda según `account.currency`; filtra querysets por org o por proyecto compartido |
| `CategoryForm` | Category | |
| `AccountForm` | Account | Banco, RIF, número, titular |
| `ProjectForm` | Project | |
| `ValuationForm` | Valuation | Misma conversión dual que transacciones |

## Otros módulos Python

| Archivo | Responsabilidad |
|---------|-----------------|
| `amounts.py` | `apply_dual_currency_amounts`, saldo inicial |
| `audit.py` | Snapshot JSON + `TransactionAuditLog` |
| `banks.py` | Carga y valida catálogo de bancos |
| `validators.py` | RIF, cuenta, titular |
| `templatetags/intcomma.py` | Formato numérico VE |
| `admin.py` | Modelos de dominio (no registra audit ni share links) |

## Tasa BCV en este módulo

`get_bcv_rate(fecha)` usa `BCV.services.bcv_scrapper`. Si falla o no hay dato, **devuelve 1.0** (ver auditoría). Home, formularios y saldo inicial dependen de ella.

## Tests (`organizations/tests.py`)

Cubren acceso a txs de proyecto compartido, visibilidad para Viewer, saldo inicial BS/USD, banco inválido, filtros de `_get_report_data` y queryset de centros de costo.

No cubren revalidación de sesión, enlaces públicos ni exportaciones.
