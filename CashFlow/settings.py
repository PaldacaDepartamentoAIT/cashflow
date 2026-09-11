"""
Django settings for CashFlow.

Entorno por defecto: desarrollo (`DJANGO_ENV=development`).
En producción: `DJANGO_ENV=production` y variables de entorno para BD y SECRET_KEY.
"""
import os
from pathlib import Path

# Entorno: development | production
DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').lower()
IS_DEVELOPMENT = DJANGO_ENV == 'development'

# En desarrollo, SQLite por defecto (sin MySQL). Para MySQL local: DJANGO_USE_SQLITE=0
if IS_DEVELOPMENT:
    os.environ.setdefault('DJANGO_USE_SQLITE', '1')

from .db import DATABASES

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Seguridad
# -----------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-dev-only-change-in-production',
)

DEBUG = os.environ.get('DEBUG', '1' if IS_DEVELOPMENT else '0').lower() in ('1', 'true', 'yes')

if IS_DEVELOPMENT:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
else:
    ALLOWED_HOSTS = [
        h.strip()
        for h in os.environ.get(
            'ALLOWED_HOSTS',
            'localhost,127.0.0.1,.onrender.com,cashflow.cpaldaca.com,dev.cpaldaca.com',
        ).split(',')
        if h.strip()
    ]


CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost,http://127.0.0.1',
    ).split(',')
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# -----------------------------------------------------------------------------
# Aplicaciones
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'organizations',
    'BCV',
    'superadmin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'superadmin_panel.middleware.SuperuserPanelMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'CashFlow.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'superadmin_panel.context_processors.superadmin_panel',
                'accounts.context_processors.user_permissions',
                'organizations.context_processors.estado_cuentas',
            ],
        },
    },
]

WSGI_APPLICATION = 'CashFlow.wsgi.application'

# -----------------------------------------------------------------------------
# Base de datos (definida en db.py)
# -----------------------------------------------------------------------------
# DATABASES importado arriba

# -----------------------------------------------------------------------------
# Validación de contraseñas
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -----------------------------------------------------------------------------
# Internacionalización
# -----------------------------------------------------------------------------
LANGUAGE_CODE = 'es-ve'

TIME_ZONE = 'America/Caracas'

USE_I18N = True

USE_TZ = True

# -----------------------------------------------------------------------------
# Archivos estáticos
# -----------------------------------------------------------------------------
STATIC_URL = '/static/'

# Origen de estáticos del proyecto (CSS/JS en static/)
STATICFILES_DIRS = [BASE_DIR / 'static']

# Destino de collectstatic (no debe ser la misma carpeta que STATICFILES_DIRS)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Django 5.1 eliminó STATICFILES_STORAGE/DEFAULT_FILE_STORAGE: el almacenamiento
# se configura ahora en STORAGES (los ajustes viejos no pueden coexistir con él).
if IS_DEVELOPMENT:
    # Sirve desde static/ sin ejecutar collectstatic en cada cambio
    WHITENOISE_USE_FINDERS = True
    _STATIC_BACKEND = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    WHITENOISE_USE_FINDERS = False
    _STATIC_BACKEND = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STORAGES = {
    # Punto de cambio a S3: DJANGO_DEFAULT_FILE_STORAGE=storages.backends.s3.S3Storage
    'default': {
        'BACKEND': os.environ.get(
            'DJANGO_DEFAULT_FILE_STORAGE',
            'django.core.files.storage.FileSystemStorage',
        ),
    },
    'staticfiles': {'BACKEND': _STATIC_BACKEND},
}

# -----------------------------------------------------------------------------
# Archivos de medios (fotos adjuntas de transacciones)
# -----------------------------------------------------------------------------
# En Docker/Coolify DJANGO_MEDIA_ROOT debe apuntar a un volumen persistente
# (/app/media): si no, las fotos se pierden en cada despliegue.
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Fotos de transacciones: tope por transacción, objetivo de peso por archivo ya
# comprimido y tamaño máximo aceptado en la subida (antes de recomprimir).
TRANSACTION_PHOTOS_MAX = int(os.environ.get('TRANSACTION_PHOTOS_MAX', '10'))
TRANSACTION_PHOTO_TARGET_BYTES = int(os.environ.get('TRANSACTION_PHOTO_TARGET_BYTES', str(40 * 1024)))
TRANSACTION_PHOTO_MAX_UPLOAD_BYTES = int(os.environ.get('TRANSACTION_PHOTO_MAX_UPLOAD_BYTES', str(15 * 1024 * 1024)))

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

# -----------------------------------------------------------------------------
# Correo saliente (SMTP autenticado: MXroute)
# -----------------------------------------------------------------------------
# No hace falta un proveedor tipo SendGrid/Mailgun: basta un buzon SMTP propio.
# MXroute usa la direccion completa como EMAIL_HOST_USER (p. ej. no-reply@dominio.com),
# puerto 587 con STARTTLS o 465 con SSL. En un VPS suele estar bloqueado el 25, no el
# 587/465. El dominio necesita SPF y DKIM de MXroute publicados en DNS.
# En desarrollo se imprime por consola salvo que se defina EMAIL_BACKEND.
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if IS_DEVELOPMENT
    else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
# Django los trata como mutuamente excluyentes (lanza ValueError si ambos son
# True). Como EMAIL_USE_TLS viene activado por defecto, basta poner
# EMAIL_USE_SSL=1 para el puerto 465: aqui se desactiva el TLS solo.
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', '0').lower() in ('1', 'true', 'yes')
EMAIL_USE_TLS = (
    False if EMAIL_USE_SSL
    else os.environ.get('EMAIL_USE_TLS', '1').lower() in ('1', 'true', 'yes')
)
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@localhost')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Validez del enlace de restablecimiento de contrasena, en segundos (1 hora).
PASSWORD_RESET_TIMEOUT = int(os.environ.get('PASSWORD_RESET_TIMEOUT', '3600'))

# Maximo de solicitudes de restablecimiento por sesion dentro de la ventana.
PASSWORD_RESET_MAX_INTENTOS = int(os.environ.get('PASSWORD_RESET_MAX_INTENTOS', '5'))
PASSWORD_RESET_VENTANA_SEGUNDOS = int(os.environ.get('PASSWORD_RESET_VENTANA_SEGUNDOS', '3600'))

# -----------------------------------------------------------------------------
# Desarrollo
# -----------------------------------------------------------------------------
if IS_DEVELOPMENT:
    # Cookies menos estrictas en local (HTTP)
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    INTERNAL_IPS = ['127.0.0.1', '::1']

LOG_LEVEL = os.environ.get('DJANGO_LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
LOG_DIR = Path(os.environ.get('DJANGO_LOG_DIR', BASE_DIR / 'logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{levelname}] {name}: {message}',
            'style': '{',
        },
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {module}:{lineno} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'app_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'app.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'verbose',
            'level': LOG_LEVEL,
        },
        'server_errors_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'server_errors.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 10,
            'encoding': 'utf-8',
            'formatter': 'verbose',
            'level': 'ERROR',
        },
        'transactions_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'transactions.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 10,
            'encoding': 'utf-8',
            'formatter': 'verbose',
            'level': LOG_LEVEL,
        },
        'application_errors_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'application_errors.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 10,
            'encoding': 'utf-8',
            'formatter': 'verbose',
            'level': 'WARNING',
        },
        'cron_bcv_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'cron_bcv.log',
            'maxBytes': 1024 * 1024 * 2,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'verbose',
            'level': 'INFO',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'server_errors_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console', 'server_errors_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'cashflow.debug': {
            'handlers': ['console', 'app_file', 'application_errors_file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'cashflow.transactions': {
            'handlers': ['console', 'transactions_file', 'application_errors_file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'cashflow.errors': {
            # Solo 'server_errors_file': los eventos WARNING+ ya llegan una vez a
            # 'console'/'application_errors_file' a través del logger de origen
            # (cashflow.debug/transactions/accounts) en debug_event(); incluirlos
            # también aquí duplicaba cada entrada WARNING+ en esos dos destinos.
            'handlers': ['server_errors_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'cashflow.accounts': {
            'handlers': ['console', 'app_file', 'application_errors_file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'cashflow.cron.bcv': {
            'handlers': ['cron_bcv_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Log de consultas SQL en consola (opcional: DJANGO_SQL_LOG=1)
if IS_DEVELOPMENT and os.environ.get('DJANGO_SQL_LOG', '').lower() in ('1', 'true', 'yes'):
    LOGGING['loggers']['django.db.backends'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    }

# Default primary key field type to avoid warnings
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
