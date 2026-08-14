# Módulo accounts

Gestión de identidad: login, logout, registro y rol por perfil.

Rutas montadas en `/accounts/`.

## Modelo

`Profile` (`accounts/models.py`):

- `OneToOneField` a `django.contrib.auth.User`
- `edit`: `Editor` (default) o `Viewer`

Al crear un `User`, una señal `post_save` crea el perfil. Hay una segunda señal que vuelve a guardar el perfil en cada `User.save()` (redundante).

`Profile` no está registrado en `accounts/admin.py`; se edita desde el panel superadmin.

## Rutas

| URL | Vista | Auth |
|-----|-------|------|
| `/accounts/login/` | `LoginView` | Pública; si ya hay sesión, redirige |
| `/accounts/logout/` | `LogoutView` de Django | POST + CSRF (navbar) |
| `/accounts/registro/` | `registro` | Pública |

`LoginView` (`accounts/views.py`):

- Formulario `LoginForm` (`AuthenticationForm`).
- Superuser → `superadmin_dashboard`.
- Resto → `LOGIN_REDIRECT_URL` (`dashboard`).
- Oculta navbar y sidebar.

`registro`:

- `RegistroForm` (`UserCreationForm`).
- Crea usuario, hace `login()` y redirige a `dashboard`.
- El perfil nace **Editor**, así que puede crear organizaciones si esa vista sigue abierta.

## Rol Editor / Viewer

### Decorador `viewer_restricted`

`accounts/decorators.py`. Si el usuario autenticado tiene rol `viewer` (minúsculas, con `strip`) y **no** es superuser: mensaje de error y redirect al referer seguro o al dashboard.

No bloquea a quien tenga un valor raro en `edit` (solo compara `viewer`). Las vistas que mutan deben llevar este decorador **y** `@login_required`.

Uso típico: `organizations/views.py` (guardar/eliminar transacciones, cuentas, categorías, proyectos, valuaciones, crear org).

### Context processor `user_permissions`

Inyecta en todas las plantillas:

- `user_is_viewer`
- `user_is_editor`
- `user_role`

Los superusers salen siempre como editores. `base.html` expone el rol a JavaScript (`window.userRole`, etc.) para ocultar acciones en el cliente; la autorización real es el decorador.

Cada request autenticado emite `debug_event("context_processor.permissions", ...)`.

## Formularios

- `LoginForm`: `AuthenticationForm` sin campos extra.
- `RegistroForm`: `UserCreationForm` (validadores de `AUTH_PASSWORD_VALIDATORS`).

## Plantillas

- `templates/accounts/login.html`
- `templates/accounts/registro.html`
- Estilos: `static/css/accounts/auth.css`

## Tests

`accounts/tests.py` está vacío. El comportamiento de `viewer_restricted` (rol con espacios) se prueba en `organizations/tests.py`.
