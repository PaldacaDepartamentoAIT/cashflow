import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

_POSTGRES_SCHEMES = {'postgres', 'postgresql', 'pgsql'}
_MYSQL_SCHEMES = {'mysql', 'mysql2'}
_SQLITE_SCHEMES = {'sqlite', 'sqlite3'}


def _use_sqlite() -> bool:
    return os.environ.get('DJANGO_USE_SQLITE', '').lower() in ('1', 'true', 'yes')


def _database_from_url(url: str) -> dict:
    """Parsea DATABASE_URL (postgres://, mysql://, sqlite://) a settings.DATABASES."""
    parsed = urlparse(url)
    scheme = parsed.scheme.split('+')[0].lower()
    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}

    if scheme in _SQLITE_SCHEMES:
        name = unquote(parsed.path) or ':memory:'
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': name,
        }

    name = unquote(parsed.path.lstrip('/'))
    config = {
        'NAME': name,
        'USER': unquote(parsed.username) if parsed.username else '',
        'PASSWORD': unquote(parsed.password) if parsed.password else '',
        'HOST': parsed.hostname or '',
        'PORT': str(parsed.port or ''),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        'CONN_HEALTH_CHECKS': True,
    }

    if scheme in _POSTGRES_SCHEMES:
        sslmode = query.get('sslmode') or os.environ.get('DB_SSLMODE', 'prefer')
        config['ENGINE'] = 'django.db.backends.postgresql'
        config['OPTIONS'] = {'sslmode': sslmode}
        if not config['PORT']:
            config['PORT'] = '5432'
        return config

    if scheme in _MYSQL_SCHEMES:
        config['ENGINE'] = 'django.db.backends.mysql'
        config['OPTIONS'] = {'charset': 'utf8mb4'}
        if not config['PORT']:
            config['PORT'] = '3306'
        return config

    raise ValueError(
        f'Esquema de DATABASE_URL no soportado: {parsed.scheme!r}. '
        'Usa postgres://, mysql:// o sqlite://'
    )


def _mysql_from_env() -> dict:
    return {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'cashflow_db'),
        'USER': os.environ.get('DB_USER', 'RAG'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '12345'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }


_database_url = os.environ.get('DATABASE_URL', '').strip()

if _database_url:
    DATABASES = {'default': _database_from_url(_database_url)}
elif _use_sqlite():
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.environ.get('SQLITE_DB_NAME', 'test_db.sqlite3'),
            'TEST': {
                'NAME': ':memory:',
            },
        }
    }
else:
    DATABASES = {'default': _mysql_from_env()}
