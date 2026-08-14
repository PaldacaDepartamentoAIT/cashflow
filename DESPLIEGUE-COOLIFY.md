# Guía de despliegue en Coolify (VPS Contabo)

Paso a paso para publicar **Control de Gastos** en [Coolify](https://coolify.io) sobre un VPS (Contabo u otro). Coolify se encarga del proxy (Traefik o Caddy), HTTPS (Let’s Encrypt) y de MySQL. Django se conecta a la base **solo con `DATABASE_URL`**.

> **No uses** el `docker-compose.yml` de la raíz en Coolify. Ese archivo incluye Caddy y MySQL en el mismo stack y choca con el proxy de Coolify (puertos 80/443).  
> En Coolify usa el **Dockerfile** (recomendado) o `docker-compose.coolify.yml`.

---

## 0. Requisitos

- VPS Contabo con Ubuntu 22.04/24.04, **mínimo 2 vCPU y 4 GB RAM** (8 GB recomendado).
- Dominio (o subdominio) con acceso a DNS. Ejemplo: `gastos.tudominio.com`.
- Repositorio Git (GitHub/GitLab/Gitea) con esta rama desplegable.
- Puertos **libres en el firewall del VPS y de Contabo**:
  - `22` — SSH
  - `80` / `443` — HTTP/HTTPS (Let’s Encrypt + la app)
  - `8000` — panel de Coolify (cámbialo después si quieres)

---

## 1. DNS

En el panel de tu dominio, crea un registro **A**:

| Tipo | Nombre | Valor |
|------|--------|--------|
| A | `gastos` (o `@`) | IP pública del VPS |

Espera a que resuelva (`ping gastos.tudominio.com`). Let’s Encrypt fallará si el DNS aún no apunta al servidor.

Opcional: otro A para el panel de Coolify, por ejemplo `coolify.tudominio.com`.

--- ##NOTA INTERESANTE ESTE PASO PERO ES PARA DESPUES

## 2. Instalar Coolify en el VPS

Por SSH, como root:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Al terminar, abre el panel:

```text
http://IP_DEL_VPS:8000
```

Crea el usuario administrador la primera vez.

### 2.1. Dominio del panel (opcional)

En Coolify: **Settings → Instance domain** → `https://coolify.tudominio.com`.  
Coolify emitirá el certificado. A partir de ahí entra por HTTPS, no por `:8000`.

### 2.2. Zona horaria del servidor (tasas BCV)

Las tareas programadas de Coolify usan la zona del VPS. En Venezuela:

```bash
timedatectl set-timezone America/Caracas
timedatectl
```

---

## 3. Conectar el repositorio Git

1. En Coolify: **Sources → + Add** (GitHub App, o Deploy Key si el repo es privado).
2. Autoriza la organización/repo `control-gastos-app-django`.
3. Si usas GitHub App, Coolify podrá desplegar en cada push a la rama que elijas.

---

## 4. Crear el proyecto

1. **Projects → + New**.
2. Nombre: `control-gastos`.
3. Entra al entorno **production**.

Todo lo siguiente (MySQL + app) debe vivir **en el mismo proyecto y el mismo entorno**, para compartir red Docker.
##NO CREAMOS PROYECTOS USAMOS SUIT PALDACA
---

## 5. Crear MySQL en Coolify

1. En el proyecto: **+ New → Database → MySQL**.
2. Versión: **MySQL 8** (o la que ofrezca por defecto).
3. Nombre visible: `cashflow-db`.
4. **Save** y espera a que el contenedor quede *Running*.

### 5.1. Red interna (imprescindible)

En el recurso de MySQL:

1. **Configuration → Advanced**.
2. Activa **Connect to Predefined Network**.
3. Guarda. Sin esto la app no resuelve el host de MySQL.

### 5.2. Copiar la URL interna

En la ficha de MySQL, copia **MySQL URL (internal)**. Tiene esta forma:

```text
mysql://usuario:CONTRASEÑA@mysql-XXXXXXXX:3306/mysql
```

Esa es tu `DATABASE_URL`. Django acepta `mysql://`.

- **Internal** = tráfico dentro de Docker. Es la que debes usar.
- **External** = solo si activas “Make it publicly available” (no lo hagas en producción).

Si quieres una base llamada `cashflow` en lugar de `mysql`:

1. Abre **Terminal** del recurso MySQL.
2. Ejecuta:

```bash
mysql -u root -p -e "CREATE DATABASE cashflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

3. En la URL, cambia el final `/mysql` por `/cashflow`.

### 5.3. Backups (recomendado)

En el mismo recurso: **Backups → + Add**.

- Frecuencia: `0 3 * * *` (03:00).
- Destino: local, o S3/R2 si lo tienes configurado en Coolify.

---

## 6. Crear la aplicación

En el mismo entorno: **+ New → Application**.

| Campo | Valor |
|--------|--------|
| Fuente | El GitHub App / repo de este proyecto |
| Rama | `main` (o `feat/docker-postgres-contabo` si aún no está mergeada) |
| Build Pack | **Dockerfile** |
| Base Directory | `/` |
| Dockerfile location | `/Dockerfile` |
| Port | `8081` |

**Save**. Aún no pulses Deploy.

### Alternativa: Docker Compose

Si prefieres Compose:

| Campo | Valor |
|--------|--------|
| Build Pack | **Docker Compose** |
| Docker Compose Location | `/docker-compose.coolify.yml` |

Asigna el dominio al servicio **`web`**. Coolify inyecta las variables de entorno del panel a ese servicio.

---

## 7. Variables de entorno

En la app: **Environment Variables → + Add**.  
Marca como **Runtime** (no hace falta “Build Variable”: las migraciones corren al **arrancar** el contenedor, no en el build).

Marca `SECRET_KEY` y `DATABASE_URL` como **sensitive**.

| Variable | Valor de ejemplo | Notas |
|----------|------------------|--------|
| `DJANGO_ENV` | `production` | Obligatorio |
| `DEBUG` | `0` | Nunca `1` en el VPS |
| `SECRET_KEY` | (ver abajo) | Obligatorio; sin esto Django no arranca |
| `DATABASE_URL` | URL **internal** del paso 5.2 | Host = nombre del contenedor Coolify |
| `ALLOWED_HOSTS` | `gastos.tudominio.com` | Sin `https://`. Varios: separados por coma |
| `CSRF_TRUSTED_ORIGINS` | `https://gastos.tudominio.com` | Con esquema `https://` |
| `DOMAIN` | `gastos.tudominio.com` | Se añade solo a hosts/CSRF si falta |
| `SECURE_SSL_REDIRECT` | `1` | Traefik termina TLS y manda `X-Forwarded-Proto` |
| `SESSION_COOKIE_SECURE` | `1` | |
| `CSRF_COOKIE_SECURE` | `1` | |
| `SECURE_HSTS_SECONDS` | `31536000` | Cuando HTTPS ya funcione |
| `DB_SSLMODE` | (omitir) | No aplica a MySQL en red interna |
| `TZ` | `America/Caracas` | |

Generar `SECRET_KEY` en tu PC:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Si la contraseña de MySQL tiene `@`, `:`, `/`, `#` o `?`, debe ir **codificada** en la URL (`@` → `%40`). La URL que copia Coolify ya viene escapada; no la reescribas a mano.

---

## 8. Dominio, SSL y healthcheck

### 8.1. Dominio

1. **Configuration → Domains**.
2. Añade `https://gastos.tudominio.com`.
3. El puerto de la app es **8081** (Gunicorn). Coolify enruta 443 → 8081.

### 8.2. Red de la app

**Configuration → Advanced** → activa **Connect to Predefined Network** (igual que en MySQL).  
Sin esto, `DATABASE_URL` con host `mysql-XXXX` no resuelve.

### 8.3. Healthcheck (evita 502/503)

**Configuration → Healthcheck**:

| Campo | Valor |
|--------|--------|
| Enabled | Sí |
| Method | `GET` |
| Path | `/health/` |
| Port | `8081` |
| Return code | `200` |
| Interval | `30` |
| Timeout | `5` |
| Start period | `60` |

El start period da tiempo a `migrate` + `collectstatic` del entrypoint.

---

## 9. Desplegar

1. Pulsa **Deploy**.
2. Abre **Logs** y espera a:
   - build de la imagen (varios minutos la primera vez),
   - `MySQL disponible`,
   - `migrate`,
   - `collectstatic`,
   - Gunicorn escuchando en `0.0.0.0:8081`.
3. Abre `https://gastos.tudominio.com/health/` → debe responder `ok`.
4. Abre la URL de la app y comprueba el login.

Cada `git push` a la rama configurada vuelve a desplegar (si el GitHub App / webhook está activo).

---

## 10. Crear el superusuario

En la app: **Terminal** (o Execute Command):

```bash
python manage.py createsuperuser
```

Luego entra en `/admin/` o `/superadmin/` con esa cuenta.

---

## 11. Cron de tasas BCV

No uses el servicio `bcv-cron` del compose de VPS. En Coolify:

1. App → **Scheduled Tasks → + Add**.
2. Nombre: `bcv-tasas`.
3. Command (tal cual, **sin** `docker exec`):

```bash
python manage.py bcv --strict-window
```

4. Frequency (servidor en `America/Caracas`):

```text
0 9,15 * * *
```

Si el VPS está en UTC, usa `0 13,19 * * *` (Caracas = UTC−4, sin horario de verano).

5. Timeout: `300`.
6. Container: vacío si solo hay un contenedor; si usas Compose, pon `web`.
7. Guarda. Prueba en el Terminal el mismo comando y revisa **Executions**.

---

## 12. Qué hace el contenedor al arrancar

El `docker/entrypoint.sh`:

1. Espera a que MySQL acepte conexiones (`DATABASE_URL`).
2. `python manage.py migrate --noinput`
3. `python manage.py collectstatic --noinput`
4. Arranca Gunicorn en el puerto 8081.

WhiteNoise sirve los estáticos. No hace falta Nginx dentro del contenedor.

---

## 13. Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| Build OK, arranque: `SECRET_KEY debe definirse` | Falta `SECRET_KEY` en Environment Variables. Redeploy. |
| `could not translate host name "mysql-…"` | **Connect to Predefined Network** en la app **y** en MySQL. |
| `password authentication failed` | URL internal mal copiada, o cambiaste la contraseña y no actualizaste `DATABASE_URL`. |
| 502 Bad Gateway | Puerto de Coolify ≠ `8081`. Gunicorn debe escuchar en `0.0.0.0`, no en `127.0.0.1`. |
| 503 No available server | Healthcheck mal (path `/health/`, puerto 8081) o start period corto. |
| Let’s Encrypt no emite certificado | DNS A aún no apunta al VPS; puertos 80/443 cerrados en Contabo/ufw. |
| CSRF al hacer login | `CSRF_TRUSTED_ORIGINS` debe ser `https://tu-dominio` (con `https://`). |
| Estáticos 404 | Mira en logs si `collectstatic` falló; revisa volumen `app_static` si usas Compose. |
| Deploy con el compose de la raíz | Caddy pelea por 80/443 con Traefik. Usa Dockerfile o `docker-compose.coolify.yml`. |
| `env file .env not found` | No uses `docker-compose.yml` (tiene `env_file: .env`). Las variables van en el panel. |

Logs:

- App → **Logs** (Gunicorn + Django).
- MySQL → **Logs**.
- En el VPS: `docker ps` y `docker logs <contenedor>`.

---

## 14. Actualizar la app

```bash
git push origin main
```

Coolify reconstruye y reinicia. Las migraciones se aplican solas en el entrypoint.  
Los datos de MySQL **no** se pierden: viven en el volumen del recurso Database.

Para un deploy manual: **Redeploy** en la ficha de la aplicación.

---

## 15. Resumen rápido

1. DNS A → IP del VPS.  
2. Instalar Coolify.  
3. Proyecto `control-gastos`.  
4. Recurso **MySQL** + *Connect to Predefined Network* + copiar URL internal.  
5. Recurso **Application** (Dockerfile, puerto 8081, misma red).  
6. Pegar variables (`SECRET_KEY`, `DATABASE_URL`, hosts, CSRF).  
7. Dominio `https://…` + healthcheck `/health/`.  
8. Deploy → `createsuperuser` → tarea `bcv --strict-window` a las 09:00 y 15:00.

Listo: la app queda en producción con HTTPS, MySQL por URL y deploys desde Git.
