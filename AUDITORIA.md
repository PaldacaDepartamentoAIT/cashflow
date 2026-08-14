# Auditoría de Control de Gastos

**Fecha:** 14 de agosto de 2026  
**Alcance:** código de aplicación, autenticación, dominio, tasas BCV, panel superadmin, frontend, tests y despliegue (Namecheap + Docker/Coolify).  
**Método:** revisión estática del repositorio (modelos, vistas, formularios, middleware, settings, Docker y tests). No se ejecutó pentest contra un entorno en vivo.

Documentación de módulos: [`docs/README.md`](docs/README.md).

---

## 1. Resumen ejecutivo

Control de Gastos es una aplicación Django 5.2 multi-organización para flujo de caja en Venezuela: transacciones en Bs. y USD (tasa BCV y “dólares reales”), cuentas bancarias, categorías, centros de costo, proyectos compartidos y un panel exclusivo para superusuarios.

La base de dominio es sólida (dual moneda, auditoría de transacciones, enlaces públicos revocables, wizard de alta en superadmin). Los riesgos más graves no son de inyección SQL, sino de **gobernanza de acceso**, **secretos en el código** y **degradación contable silenciosa** cuando falla la tasa BCV.

| Área | Estado |
|------|--------|
| Autenticación Django / CSRF en formularios | Aceptable |
| Autorización por organización en cada request | Débil |
| Secretos y credenciales | Crítico (hay valores hardcodeados) |
| Integridad de montos / tasas | Alto (fallback a tasa 1.0) |
| Superficie pública (registro, API BCV, enlaces) | Media–alta |
| Tests | Parcial (huecos en acceso y compartir) |
| Despliegue dual MySQL vs PostgreSQL | Riesgo operativo |

---

## 2. Arquitectura observada

```
Navegador
    │
    ▼
Caddy / Traefik / Passenger
    │
    ▼
Gunicorn o LiteSpeed  →  CashFlow (settings, urls, debug)
    │
    ├── accounts/          login, registro, rol Editor|Viewer
    ├── organizations/     dominio (sesión org_id)
    ├── BCV/               scrape + histórico de tasas
    └── superadmin_panel/  solo is_superuser
    │
    ▼
SQLite (dev) | MySQL (Namecheap) | PostgreSQL (Docker/Coolify)
```

No hay org en la URL. Tras `seleccionar_organizacion`, casi todas las vistas leen `request.session['org_id']`. Solo esa vista comprueba `OrganizationAccess`.

---

## 3. Hallazgos

Severidad: **Crítico** = explotable o compromiso directo; **Alto** = impacto serio en datos o integridad; **Medio** = abuso o degradación; **Bajo** = higiene / deuda.

### Crítico

| ID | Hallazgo | Evidencia | Remediación |
|----|----------|-----------|-------------|
| C1 | Superusuario de bootstrap con contraseña fija en un script versionado | `create_superuser.py` | Eliminar credenciales del repo. Usar `createsuperuser` interactivo o variables de entorno. Rotar la clave si el script se usó en producción. |
| C2 | Fallback MySQL con usuario y contraseña débiles si no hay `DATABASE_URL` | `CashFlow/db.py` → `_mysql_from_env()` | En producción exigir `DATABASE_URL` o `DB_PASSWORD` sin default. Fallar al arrancar si faltan. |

### Alto

| ID | Hallazgo | Evidencia | Remediación |
|----|----------|-----------|-------------|
| A1 | Tras elegir org, las vistas **no revalidan** `OrganizationAccess` | `home_organizacion`, CRUD, exportaciones: `session.get('org_id')` → `Organization(id=…)` | Helper `require_org(request)` que compruebe acceso en cada vista. Al revocar un acceso, invalidar sesión o comprobar siempre. |
| A2 | Contraseña global hardcodeada para generar/listar enlaces públicos | `organizations/views.py` (`PROJECT_SHARE_PASSWORD`) | Mover a variable de entorno, o mejor: permiso de Editor + CSRF, sin password compartida. Rotar el valor actual. |
| A3 | Si no hay tasa BCV, `get_bcv_rate()` devuelve **1.0** | `organizations/views.py` | Fallar de forma visible (error de formulario / mensaje). No convertir con 1.0. |
| A4 | Registro público + cualquier Editor puede crear organizaciones | `accounts/views.py::registro`, `organizations/views.py::crear_organizacion` | Cerrar registro o exigir invitación. Dejar el alta de orgs solo en superadmin. |
| A5 | `GET /bcv/rates/` sin autenticación ni límite de tasa; errores internos en JSON 502 | `BCV/views.py::rates_api` | `@login_required` (o solo superadmin). No devolver `str(exc)`. |
| A6 | Enlace público de proyecto sin caducidad; expone transacciones de **todas** las orgs del proyecto | `proyecto_publico`, `ProjectShareLink` | `max_age` en el token, caducidad en modelo, recortar campos sensibles. |

### Medio

| ID | Hallazgo | Evidencia | Remediación |
|----|----------|-----------|-------------|
| M1 | Viewers pueden generar, listar y borrar enlaces públicos | `compartir_proyecto` y relacionadas **sin** `@viewer_restricted` | Añadir el decorador. |
| M2 | Rol `Profile.edit` distinto de Editor/Viewer no es Viewer en el decorador → no se bloquea escritura | `viewer_restricted` solo compara `'viewer'` | Tratar como Viewer todo lo que no sea `editor` (salvo superuser). Constraint en modelo. |
| M3 | Caché BCV en memoria por proceso (LocMem); Gunicorn con varios workers | Sin `CACHES` en settings | Redis/Memcached, o no cachear y usar solo BD. |
| M4 | Scrape BCV por regex sobre HTML; fallback a DolarAPI silencioso; la UI puede seguir diciendo “BCV” | `bcv_scrapper.py` | Loguear el fallback; mostrar la fuente real. |
| M5 | Healthcheck `/health/` no toca la base de datos | `CashFlow/urls.py` | Comprobar `SELECT 1` (con timeout corto). |
| M6 | `SECURE_SSL_REDIRECT` y HSTS en 0 por defecto en producción | `CashFlow/settings.py` | Activarlos detrás del proxy cuando el dominio tenga HTTPS. |
| M7 | Posible XSS en listado de enlaces (JS con `innerHTML` y datos del servidor) | plantilla `detalle_proyecto.html` | Escapar o usar `textContent`. |
| M8 | Superadmin puede elevar o borrar a otros superusers (salvo a sí mismo) | `guardar_usuario`, `eliminar_usuario` | Confirmación extra / no permitir quitar el último superuser. |
| M9 | Dos caminos de producción (MySQL Namecheap vs Postgres Docker) y dos `requirements*.txt` | `deploy.yml`, `Dockerfile` | Unificar motor o documentar y testear ambos en CI. |

### Bajo

| ID | Hallazgo | Evidencia |
|----|----------|-----------|
| B1 | `user_permissions` escribe un evento de debug **en cada request** autenticado | `accounts/context_processors.py` |
| B2 | `views.py` de organizations ~2500 líneas; filtros copiados en varias vistas | Deuda de mantenimiento |
| B3 | `CostCenter`, `ProjectUserAccess` y `ProjectOrganizationAccess` sin UI de negocio (solo admin) | Modelos vs producto |
| B4 | `pytest` / `pytest-django` sin pin en `requirements.txt` | Builds no reproducibles |
| B5 | Redacción de logs solo por substring en el nombre de la clave (`password`, `csrf`, `token`, `secret`) | `CashFlow/debug.py` |
| B6 | `ALLOWED_HOSTS` de producción incluye `.onrender.com` por default | `settings.py` |
| B7 | `accounts/tests.py` vacío; sin tests de IDOR de sesión ni de enlaces públicos | Cobertura |
| B8 | Señales `post_save` duplicadas en `Profile` | `accounts/models.py` |

---

## 4. Lo que está bien

- CSRF en formularios HTML y, en compartir proyecto, cabecera `X-CSRFToken`.
- Consultas vía ORM (`icontains`, filtros); no hay SQL crudo de usuario.
- Redirects con `url_has_allowed_host_and_scheme` (`_safe_next_url`, `viewer_restricted`).
- Superusers aislados del flujo de org (`SuperuserPanelMiddleware` + redirect de login). Un superadmin no puede autoeliminarse.
- Enlaces públicos: token firmado (`django.core.signing`) **y** fila en `ProjectShareLink` (revocable).
- WhiteNoise, cookies `Secure` en producción si las env vars están en 1, `SECRET_KEY` obligatoria en prod.
- Auditoría de transacciones (`TransactionAuditLog` + snapshot JSON) visible en superadmin.
- Validación de bancos contra JSON estático; RIF y número de cuenta con validadores.
- Tests de acceso a proyectos compartidos, saldo inicial dual moneda, filtros de reporte y wizard superadmin (cuentas BS/USD).

---

## 5. Autorización (detalle)

### Flujo org

1. Login → `dashboard` lista orgs vía `OrganizationAccess`.
2. `seleccionar_organizacion` **sí** exige `OrganizationAccess`.
3. El resto usa `session['org_id']` sin volver a comprobar.

La sesión Django está firmada: un atacante **no** puede poner un `org_id` arbitrario en la cookie sin `SECRET_KEY`. El fallo real es **sesión obsoleta**: si el superadmin quita el acceso, el usuario sigue operando hasta `logout` / `salir`.

### Roles

| Rol | Quién | Escritura |
|-----|--------|-----------|
| Editor | `Profile.edit = Editor` | CRUD org-scoped (`@viewer_restricted`) |
| Viewer | `Profile.edit = Viewer` | Lectura; mutaciones bloqueadas **si** la vista lleva el decorador |
| Superuser | `is_superuser` | Solo `/superadmin/`, `/admin/`, logout, `/health/` |

Huecos: compartir enlaces (sin decorador); valor de rol distinto de Editor/Viewer.

---

## 6. Integridad de datos

- Cuentas **BS**: solo montos BCV; `real_dollars` se fuerza a 0.
- Cuentas **USD**: solo `real_dollars` (+ comisión real).
- Conversión: `apply_dual_currency_amounts` y la misma regla en `TransactionForm.clean()` / `ValuationForm.clean()`.
- Comisiones se suman al egreso en KPIs y gráficos.
- **No hay FK** que impida `transaction.account.organization != transaction.organization` (el form filtra querysets; la BD no lo garantiza).
- Tasa 1.0 ante fallo BCV puede grabar equivalentes erróneos.

---

## 7. Superficie pública

| Ruta | Auth | Nota |
|------|------|------|
| `/accounts/login/` | No | Estándar |
| `/accounts/registro/` | No | Crea Editor y hace login |
| `/health/` | No | Texto `ok` |
| `/bcv/rates/` | No | JSON de tasas + paralelo |
| `/proyectos/compartido/<token>/` | No | Datos del proyecto si el enlace existe |
| `/admin/` | Staff | Superficie Django admin |

---

## 8. Tests

| Archivo | Qué cubre | Qué falta |
|---------|-----------|-----------|
| `organizations/tests.py` | Proyecto compartido, saldo inicial, banco inválido, filtros de reporte, cost center en form, viewer con espacios | Revalidación de acceso, enlaces públicos, PDF/XLSX, CRUD categorías/proyectos, modo real vs BCV |
| `superadmin_panel/tests.py` | Redirect superuser, 403, no auto-borrado, wizard BS/USD | Usuarios, tasas, auditoría, accesos |
| `BCV/tests.py` | Histórico y preferencia BCV vs DolarAPI vía `get_bcv_rate` | Scrape, fallback, parsing |
| `CashFlow/test_db_url.py` | Parseo `DATABASE_URL`, `/health/` | — |
| `accounts/tests.py` | Vacío | Registro, login superuser, roles |

`conftest.py` fuerza SQLite en memoria. No hay linter (ruff/flake8) configurado.

---

## 9. Despliegue y operaciones

- **Namecheap:** Passenger, MySQL, `requirements.txt` (`mysqlclient` + PyMySQL), GitHub Actions en `main`.
- **Docker/Coolify:** PostgreSQL por `DATABASE_URL`, `requirements-docker.txt`, Gunicorn en **8081**, Caddy o Traefik.
- `CashFlow/settings.py` y `db.py` tienen `merge=ours` en `.gitattributes`: un merge puede **tirar** cambios de settings.
- Cron BCV: crontab Namecheap vs `docker compose --profile cron` vs Scheduled Task de Coolify.
- Logs rotativos en `logs/`; `debug_event` enruta por prefijo de evento.

Ver [`docs/operaciones.md`](docs/operaciones.md) y [`DESPLIEGUE-COOLIFY.md`](DESPLIEGUE-COOLIFY.md).

---

## 10. Plan de remediación sugerido

### Inmediato

1. Quitar secretos de `create_superuser.py` y `PROJECT_SHARE_PASSWORD`; rotar si ya se usaron.
2. Producción: exigir `DATABASE_URL` / `SECRET_KEY` / `DB_PASSWORD` sin defaults.
3. Helper de org que revalide `OrganizationAccess` en cada vista.
4. No usar tasa 1.0; bloquear el alta de transacción si no hay tasa.
5. Cerrar o restringir `/accounts/registro/` y `crear_organizacion`.
6. Autenticar `/bcv/rates/`.

### Corto plazo

7. `@viewer_restricted` en compartir/revocar enlaces.
8. Caducidad de `ProjectShareLink`.
9. Rol por defecto denegado (fail-closed).
10. Tests de revocación de acceso y de enlace público.
11. Healthcheck con ping a la BD.

### Estructural

12. Extraer filtros/reportes de `organizations/views.py`.
13. Constraints de BD: cuenta y categorías de la misma org que la transacción.
14. UI o decisión de producto para centros de costo y accesos a proyectos.
15. Un solo motor de BD en producción, o CI contra ambos.

---

## 11. Conclusión

El producto cubre bien el dominio venezolano (dual moneda, BCV, proyectos, superadmin). No está lista para un VPS público **sin** cerrar registro, secretos en código, revalidación de org y el fallback de tasa 1.0. Esos cuatro puntos son el mínimo antes de tratar el resto de la deuda.
