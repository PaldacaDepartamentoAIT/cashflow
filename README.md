# Control de Gastos - Django

Aplicación Django para el control de gastos de organizaciones (flujo de caja multi-org, Bs./USD, tasa BCV).

## Documentación

- [Índice de módulos](docs/README.md)
- [Auditoría](AUDITORIA.md)
- [Despliegue Coolify](DESPLIEGUE-COOLIFY.md)

## Diagrama de Entidad-Relación (ERD)

[Ver diagrama ER en dbdiagram.io](https://dbdiagram.io/d/Diagrama-de-entidad-relacion-6a1386b8dfb20dafcde08850)

---

## Estructura del proyecto

- `accounts/`: usuarios, login y roles Editor/Viewer.
- `organizations/`: organizaciones, cuentas, proyectos, valuaciones y transacciones.
- `BCV/`: tasas de cambio (scrape + histórico).
- `superadmin_panel/`: panel exclusivo de superusuarios.
- `CashFlow/`: configuración del proyecto Django.
- `templates/` y `static/`: UI.
