
# Backend Buscador Docs PRO

## Configuración

1. Copia `.env.example` a `.env` y pon tus credenciales reales de BD y clave admin.
2. Sube la carpeta backend a tu servidor (Render, Railway, etc).
3. Ejecuta el script SQL en tu BD para crear tablas.

## Endpoints

- /api.php?action=documentos [GET, POST, PUT, DELETE]
- /api.php?action=upload [POST]
- /api.php?action=codigos [GET]
- /api.php?action=buscar [POST]
- /api.php?action=consulta [GET]
- /api.php?action=login [POST]

Respuestas en JSON. Consultar frontend para integración.

