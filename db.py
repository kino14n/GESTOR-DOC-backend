# db.py — Conexión MySQL (PyMySQL)
import os
import pymysql

def _env(key, default=""):
    return os.getenv(key, default)

def get_conn():
    host = _env("MYSQLHOST", _env("DB_HOST", "localhost"))
    port = int(_env("MYSQLPORT", _env("DB_PORT", "3306")) or 3306)
    user = _env("MYSQLUSER", _env("DB_USER", "root"))
    password = _env("MYSQLPASSWORD", _env("DB_PASS", ""))
    database = _env("MYSQLDATABASE", _env("DB_NAME", ""))

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        db=database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
