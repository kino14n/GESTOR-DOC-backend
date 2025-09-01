# GESTOR-DOC-backend/routes/documentos.py
import os
import re
import json
import pymysql
import requests
import boto3
from flask import Blueprint, request, jsonify, Response, g
from werkzeug.utils import secure_filename

documentos_bp = Blueprint("documentos", __name__)

# --- Cargar la configuración de todos los clientes desde el archivo JSON ---
with open('tenants.json', 'r') as f:
    TENANTS_CONFIG = json.load(f)


# --- Middleware para identificar al cliente en cada petición ---
@documentos_bp.before_request
def identify_tenant():
    # Excluimos la nueva ruta de diagnóstico del requisito de la cabecera
    if request.path.endswith('/ping-db'):
        return
    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id or tenant_id not in TENANTS_CONFIG:
        return jsonify({"error": "Cliente no válido o no especificado"}), 403
    g.tenant_config = TENANTS_CONFIG[tenant_id]
    g.tenant_id = tenant_id


# --- Funciones Auxiliares ---
def get_db_connection():
    if 'tenant_config' not in g:
        # Para la ruta de ping, usamos el primer cliente configurado como prueba
        tenant_id = list(TENANTS_CONFIG.keys())[0]
        g.tenant_config = TENANTS_CONFIG[tenant_id]

    config = g.tenant_config
    return pymysql.connect(
        host=config["db_host"],
        user=config["db_user"],
        password=config["db_pass"],
        database=config["db_name"],
        port=config.get("db_port", 3306),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=20 # Aumentamos el tiempo de espera
    )

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name='auto',
    )
    
# ... (Aquí va todo el resto de tu archivo documentos.py sin cambios) ...
# ... (upload_document, listar_documentos, eliminar_documento, etc.) ...

# --- NUEVA RUTA DE DIAGNÓSTICO AL FINAL DEL ARCHIVO ---
@documentos_bp.route("/ping-db", methods=["GET"])
def ping_db():
    """
    Ruta de diagnóstico para verificar la conexión con la base de datos.
    Intenta conectar y hacer una consulta simple.
    """
    try:
        # Usará la configuración del primer cliente en tenants.json para la prueba
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
        conn.close()
        if result:
            return jsonify({"status": "ok", "message": "Conexión a la base de datos exitosa."})
        else:
            return jsonify({"status": "error", "message": "La consulta no devolvió resultados."}), 500
    except Exception as e:
        # Si hay un error, nos lo mostrará en detalle
        return jsonify({"status": "error", "message": f"No se pudo conectar a la base de datos: {str(e)}"}), 500