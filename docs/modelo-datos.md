# Modelo de datos

Diagrama ER publicado: [dbdiagram.io](https://dbdiagram.io/d/Diagrama-de-entidad-relacion-6a1386b8dfb20dafcde08850).  
Regenerar DBML: `python generate_dbml.py`.

## Diagrama lógico

```
User ──1:1── Profile (edit: Editor|Viewer)
  │
  └── OrganizationAccess ── Organization
                                │
                                ├── Account (BS|USD, datos bancarios)
                                ├── Category
                                ├── CostCenter (único por org+código)
                                ├── Project
                                │     ├── Valuation (montos duales)
                                │     ├── ProjectOrganizationAccess (otras orgs)
                                │     ├── ProjectUserAccess (usuarios)
                                │     └── ProjectShareLink (token público)
                                └── Transaction
                                      ├── M2M categories
                                      ├── FK account, cost_center, project, valuation
                                      └── TransactionAuditLog (snapshot JSON)
ExchangeRateHistory (BCV)  — independiente del resto
```

## Entidades (`organizations`)

### Organization

Nombre de la empresa/unidad. No tiene dueño en el modelo: el acceso es solo por `OrganizationAccess`.

### OrganizationAccess

`unique_together (user, organization)`. Es la fuente de verdad de “este usuario entra a esta org”.

### Account

Cuenta bancaria de una org.

- `currency`: `BS` o `USD` (define qué campos de transacción aplican).
- Banco: `bank_code`, `bank_name` validados contra `static/json/bancos.json` / `bancos_usd.json`.
- Identificación: `rif`, `account_number`, `holder`, `name`.

No hay unicidad de número de cuenta a nivel BD.

### Category

Etiqueta de gasto/ingreso por org: `name`, `description`, `color` (hex, 7 caracteres). Relación **M2M** con transacciones (migración 0013).

### CostCenter

`code` + `name`, único por organización. Se usa en filtros y en el formulario de transacción. **No hay pantallas CRUD** en la app; se gestiona por Django admin.

### Project

Pertenece a una org dueña. Puede compartirse:

- `ProjectOrganizationAccess`: otra organización registra movimientos en el mismo proyecto.
- `ProjectUserAccess`: el usuario debe tener esta fila para ver el proyecto en listados/detalle (además del acceso a alguna org relacionada).

### Valuation

Presupuesto o meta del proyecto: `amount_usd`, `amount_bs`, `daily_rate`. El detalle de proyecto calcula un % de avance con las transacciones de crédito.

### Transaction

Movimiento de caja.

| Grupo | Campos |
|-------|--------|
| Cabecera | `date`, `description`, `notes`, `reference_number`, `status` (`completado` / `pendiente`) |
| Dimensiones | `organization`, `account`, `categories` (M2M), `cost_center`, `project`, `valuation` |
| BCV | `amount_bs`, `amount_usd`, `daily_rate`, `bank_fee_bs`, `bank_fee_usd` |
| Real | `real_dollars`, `bank_fee_real_usd` |

Signo: positivo = ingreso, negativo = egreso (las agregaciones usan `__gt=0` / `__lt=0`). Las comisiones se suman al egreso en KPIs.

No hay constraint SQL que exija que `account.organization` coincida con `transaction.organization`.

### TransactionAuditLog

Alta, edición o borrado. Guarda `snapshot` JSON (montos, categorías, cuenta, etc.), `user`, `timestamp`. Si se borra la transacción, el FK queda `SET_NULL` y permanece `transaction_description`.

### ProjectShareLink

Token único firmado (`django.core.signing`) más fila en BD para poder **revocar** el enlace. Sin campo de expiración.

## Entidades (`accounts`)

### Profile

`OneToOne` con `User`. Campo `edit`: `Editor` (default) o `Viewer`. Se crea con señales `post_save` al crear el usuario.

## Entidades (`BCV`)

### ExchangeRateHistory

`unique_together (rate_date, source, currency)`.

- `source`: `bcv` | `dolarapi`
- `currency`: `USD` | `EUR`
- `rate`, `fetched_at` (`auto_now`), `raw_label`

## Entidades (`superadmin_panel`)

Ninguna: el panel reutiliza los modelos anteriores.
