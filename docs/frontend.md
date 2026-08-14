# Frontend

Plantillas Django + CSS/JS estáticos. No hay SPA ni framework JS.

## Capas

| Capa | Ruta |
|------|------|
| Layout | `templates/base.html` |
| Auth | `templates/accounts/` |
| App org | `templates/organizations/` |
| Superadmin | `templates/superadmin_panel/` |
| CSS base | `static/css/base/` |
| CSS por pantalla | `static/css/organizations/`, `accounts/`, `superadmin_panel/` |
| JS compartido | `static/js/Base/` |
| JS por pantalla | `static/js/organizations/`, `superadmin_panel/` |
| Catálogo bancos | `static/json/bancos.json`, `bancos_usd.json` |

`base.html` incluye navbar, sidebar, alertas, rol (`user_is_viewer` / `user_is_editor`) y variables JS globales.

## Plantillas de organizations

| Plantilla | Pantalla |
|-----------|----------|
| `dashboard.html` | Selector de organizaciones |
| `home.html` | Home / KPIs / gráficos |
| `configuracion.html` | Configuración |
| `crear.html` | Nueva organización |
| `transacciones.html` | Listado + modal alta/edición |
| `partials/detalle_transaccion.html` | Detalle en modal |
| `categorias.html` | CRUD categorías |
| `cuentas.html` | Listado de cuentas |
| `detalle_cuenta.html` | Movimientos de una cuenta |
| `proyectos.html` | Listado |
| `detalle_proyecto.html` | Detalle, valuaciones, compartir |
| `proyecto_publico.html` | Vista pública por token |
| `enlace_publico_invalido.html` | Token inválido o revocado |
| `reportes/transacciones_pdf.html` | Plantilla auxiliar PDF |
| `reportes/transacciones_excel.html` | Exportación Excel |

## Plantillas de superadmin

`dashboard.html`, `usuarios.html`, `organizaciones.html`, `tasas_bcv.html`, `auditoria.html`, `partials/auditoria_snapshot.html`.

## JavaScript

| Archivo | Uso |
|---------|-----|
| `Base/base.js` | Arranque común |
| `Base/alert.js` | Mensajes flash |
| `Base/modal.js` | Modales |
| `Base/dropdown.js` | Menús |
| `Base/table-resizable.js` | Columnas de tablas |
| `Base/mobile-actions.js` | Acciones en móvil |
| `organizations/transacciones.js` | Filtros, modal, dual moneda |
| `organizations/cuentas.js` | Formulario de cuentas |
| `organizations/banks.js` | Autocompletado de bancos desde JSON |
| `organizations/categorias.js` | CRUD categorías |
| `organizations/proyectos.js` | Listado proyectos |
| `organizations/detalle_proyecto.js` | Gráficos y valuaciones |
| `organizations/proyecto_publico.js` | Vista pública |
| `superadmin_panel/superadmin.js` | Wizard, tasas, deletes con CSRF |

El rol Viewer se respeta en JS para ocultar botones; las APIs deben seguir protegidas en servidor.

## CSS

Variables y reset en `static/css/base/` (`variables.css`, `reset.css`, `layout.css`, `navbar.css`, `sidebar.css`, `modal.css`, `components.css`, `base.css`). Cada pantalla org tiene su hoja.

## Template tags

`organizations/templatetags/intcomma.py`: `intcomma` e `intcomma_rate` para miles y tasas al estilo venezolano.

## Convenciones

- Prefijo de clases: `cf-` (p. ej. `cf-input`).
- Formularios: `{% csrf_token %}`. Fetch: cabecera `X-CSRFToken`.
- Modo BCV vs real: query `view_mode` y controles en home / listados / detalle.
