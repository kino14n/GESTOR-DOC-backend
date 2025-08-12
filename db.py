
# db.py — conexión MySQL (Railway/Local) con PyMySQL
import os
import pymysql

def _env(name, fallback=""):
    mapping = {
        "DB_HOST": "MYSQLHOST",
        "DB_PORT": "MYSQLPORT",
        "DB_USER": "MYSQLUSER",
        "DB_PASS": "MYSQLPASSWORD",
        "DB_NAME": "MYSQLDATABASE",
    }
    return os.getenv(name) or os.getenv(mapping.get(name, ""), fallback)

def get_conn():
    return pymysql.connect(
        host=_env("DB_HOST", "127.0.0.1"),
        port=int(_env("DB_PORT", "3306") or "3306"),
        user=_env("DB_USER"),
        password=_env("DB_PASS"),
        database=os.getenv("MYSQL_DATABASE") or _env("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
