"""
WSGI config for CashFlow project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CashFlow.settings')

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
