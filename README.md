
# GESTOR-DOC Backend listo para Railway

## Variables esperadas
- Usará `DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME` o las de Railway: `MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE`.
- `CORS_ORIGINS` (coma separada). Por defecto incluye `https://kino14n.github.io` y localhost.
- `HIGHLIGHTER_URL` (opcional).

## Deploy
1. Subir estos archivos al repo del backend.
2. Confirmar `requirements.txt` y `Procfile`.
3. En Railway, en **Settings** confirmar Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT` (si no hay Procfile).
4. Redeploy y probar `/api/ping` y `/api/routes`.
