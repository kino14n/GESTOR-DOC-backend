# db.py — Conexión MySQL (compat: DB_* y MYSQL*)
import os
import pymysql
from pymysql.cursors import DictCursor

# Conexión única (suficiente para apps pequeñas en Railway)
_CONN = None

def _env(name: str, fallback_name: str = None, default=None):
    """
    Lee una variable de entorno. Si no existe, intenta con fallback_name.
    """
    val = os.getenv(name)
    if (val is None or val == "") and fallback_name:
        val = os.getenv(fallback_name, default)
    return val if val not in ("", None) else default

def _get_params():
    """
    Arma los parámetros de conexión aceptando:
      - DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
      - MYSQLHOST / MYSQLPORT / MYSQLDATABASE / MYSQLUSER / MYSQLPASSWORD
    """
    host = _env("DB_HOST", "MYSQLHOST", "localhost")
    port = int(_env("DB_PORT", "MYSQLPORT", 3306))
    user = _env("DB_USER", "MYSQLUSER", "root")
    password = _env("DB_PASSWORD", "MYSQLPASSWORD", "")
    database = _env("DB_NAME", "MYSQLDATABASE", "")

    # SSL opcional si Railway lo exige en tu proyecto (normalmente no hace falta)
    ssl_ca = os.getenv("MYSQL_SSL_CA")  # ruta a CA si aplica
    ssl = {"ca": ssl_ca} if ssl_ca else None

    params = dict(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=DictCursor,
        charset="utf8mb4",
        autocommit=False,
    )
    if ssl:
        params["ssl"] = ssl
    return params

def get_conn():
    """
    Devuelve una conexión viva a MySQL. Si estaba cerrada, la reabre.
    """
    global __CONN
    if _CONN is None:
        _CONN = pymysql.connect(**_get_params())
        return _CONN
    # Mantener viva la conexión si Railway la deja idle
    try:
        _CONN.ping(reconnect=True)
    except Exception:
        _CONN = pymysql.connect(**_get_params())
    return _CONN
