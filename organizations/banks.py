import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


def _json_dir():
    return Path(settings.BASE_DIR) / 'static' / 'json'


@lru_cache(maxsize=1)
def load_bancos_bs():
    path = _json_dir() / 'bancos.json'
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_bancos_usd():
    path = _json_dir() / 'bancos_usd.json'
    with path.open(encoding='utf-8') as handle:
        data = json.load(handle)
    return data.get('bancos', [])


def get_banco_bs_by_codigo(codigo):
    codigo = (codigo or '').strip()
    for bank in load_bancos_bs():
        if bank.get('codigo') == codigo:
            return bank
    return None


def get_banco_usd_by_nombre(nombre):
    nombre = (nombre or '').strip()
    for bank in load_bancos_usd():
        if bank.get('nombre') == nombre:
            return bank
    return None


def validate_bank_for_currency(currency, bank_code, bank_name):
    currency = (currency or '').upper()
    bank_code = (bank_code or '').strip()
    bank_name = (bank_name or '').strip()

    if currency == 'BS':
        bank = get_banco_bs_by_codigo(bank_code)
        if not bank:
            raise ValidationError(
                'Seleccione un banco válido en bolívares. El código de banco indicado no corresponde a '
                'ninguna entidad bancaria registrada en el sistema.'
            )
        return bank['codigo'], bank['nombre']

    if currency in ('USD', 'EUR'):
        bank = get_banco_usd_by_nombre(bank_name)
        if not bank:
            moneda = 'dólares' if currency == 'USD' else 'euros'
            raise ValidationError(
                f'Seleccione un banco válido en {moneda}. El nombre de banco indicado no corresponde a '
                'ninguna entidad registrada para cuentas en moneda extranjera.'
            )
        return '', bank['nombre']

    raise ValidationError(
        'La moneda de la cuenta no es válida: debe ser Bolívares (BS), Dólares (USD) o Euros (EUR).'
    )


def build_account_display_name(bank_name, account_number, currency):
    suffix = account_number[-4:] if len(account_number) >= 4 else account_number
    label = f'{bank_name} ···{suffix}'
    if currency in ('USD', 'EUR'):
        return f'{label} ({currency})'
    return label
