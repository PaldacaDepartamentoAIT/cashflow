"""Tests de parseo de DATABASE_URL (PostgreSQL / MySQL)."""

from CashFlow.db import _database_from_url


def test_postgres_url_basica():
    cfg = _database_from_url('postgres://cashflow:s3cret@db:5432/cashflow')
    assert cfg['ENGINE'] == 'django.db.backends.postgresql'
    assert cfg['NAME'] == 'cashflow'
    assert cfg['USER'] == 'cashflow'
    assert cfg['PASSWORD'] == 's3cret'
    assert cfg['HOST'] == 'db'
    assert cfg['PORT'] == '5432'
    assert cfg['OPTIONS']['sslmode'] == 'prefer'


def test_postgres_url_sslmode_query():
    cfg = _database_from_url(
        'postgresql://u:p@10.0.0.5:5432/app?sslmode=require'
    )
    assert cfg['ENGINE'] == 'django.db.backends.postgresql'
    assert cfg['HOST'] == '10.0.0.5'
    assert cfg['OPTIONS']['sslmode'] == 'require'


def test_postgres_url_password_urlencoded():
    cfg = _database_from_url('postgres://u:p%40ss@db:5432/cashflow')
    assert cfg['PASSWORD'] == 'p@ss'


def test_mysql_url_sigue_disponible():
    cfg = _database_from_url('mysql://rag:12345@localhost:3306/cashflow_db')
    assert cfg['ENGINE'] == 'django.db.backends.mysql'
    assert cfg['NAME'] == 'cashflow_db'
    assert cfg['USER'] == 'rag'
    assert cfg['HOST'] == 'localhost'
    assert cfg['PORT'] == '3306'
    assert cfg['OPTIONS']['charset'] == 'utf8mb4'


def test_mysql_url_docker_interna():
    cfg = _database_from_url('mysql://cashflow:s3cret@db:3306/cashflow')
    assert cfg['ENGINE'] == 'django.db.backends.mysql'
    assert cfg['HOST'] == 'db'
    assert cfg['NAME'] == 'cashflow'


def test_health_endpoint(client):
    response = client.get('/health/')
    assert response.status_code == 200
    assert response.content == b'ok'
