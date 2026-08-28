# Control de Gastos - Django

Este proyecto es una aplicación de Django para el control de gastos de organizaciones.

## Diagrama de Entidad-Relación (ERD)

Puedes visualizar el esquema de la base de datos en dbdiagram.io siguiendo este enlace:

[Ver Diagrama ER en dbdiagram.io](https://dbdiagram.io/d/Diagrama-de-entidad-relacion-6a1386b8dfb20dafcde08850)

---

## Estructura del Proyecto

- `accounts/`: Gestión de usuarios y perfiles.
- `organizations/`: Modelos principales de organizaciones, cuentas, proyectos, valuaciones y transacciones.
- `CashFlow/`: Configuración del proyecto Django.
- `templates/`: Plantillas HTML.

## Respaldos

Las fotos adjuntas de las transacciones se guardan en `MEDIA_ROOT` (en Docker, el volumen
`media_data` montado en `/app/media`), **no** en la base de datos. Una restauración que solo
recupere el dump de MySQL/MariaDB dejará las galerías rotas: el procedimiento de respaldo debe
incluir también ese volumen.
