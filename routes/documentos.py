# File: rutas_documentos.py
#
# Este archivo corresponde a la ruta ``routes/documentos.py`` del backend
# ``GESTOR-DOC``.  Incluye todas las rutas CRUD para documentos y
# configuraciones de base de datos/R2.  La versión de este archivo ha
# sido modificada para solucionar un fallo de handshake TLS con
# Cloudflare R2.  En concreto, la función ``get_s3_client`` ahora
# utiliza una configuración explícita de boto3 con firma ``s3v4`` y
# addressing_style ``virtual`` en lugar de desactivar la verificación
# TLS (``verify=False``), lo que evitaba el error pero no solucionaba
# el handshake.  Además, se ha especificado ``region_name="auto"`` para
# permitir que R2 determine la región correcta.

import os
import re
import json
import time
import datetime
import pymysql
import requests
import boto3
from botocore.client import Config
from flask import Blueprint, request, jsonify, Response, g
from werkzeug.utils import secure_filename


documentos_bp = Blueprint("documentos", __name__)

# --- Cargar la configuración de todos los clientes desde el archivo JSON ---
with open('tenants.json', 'r') as f:
    TENANTS_CONFIG = json.load(f)


# --- Middleware para identificar al cliente en cada petición ---
@documentos_bp.before_request
def identify_tenant():
    # Si la petición es un OPTIONS (pre-vuelo de CORS), la dejamos pasar
    if request.method == 'OPTIONS':
        return None

    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id or tenant_id not in TENANTS_CONFIG:
        return jsonify({"error": "Cliente no válido o no especificado"}), 403
    
    g.tenant_config = TENANTS_CONFIG[tenant_id]
    g.tenant_id = tenant_id


# --- Funciones Auxiliares ---

def get_db_connection():
    """
    Devuelve una conexión a la base de datos del cliente.
    Implementa un sistema de reintentos para manejar el "despertar" de la BD en Railway.
    """
    if 'tenant_config' not in g:
        raise Exception("Error interno: No se pudo identificar la configuración del cliente.")
    
    config = g.tenant_config
    
    max_retries = 5
    retry_delay = 2  # segundos

    for attempt in range(max_retries):
        try:
            # Intenta conectar con un timeout más largo
            conn = pymysql.connect(
                host=config["db_host"],
                user=config["db_user"],
                password=config["db_pass"],
                database=config["db_name"],
                port=config.get("db_port", 3306),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=15 
            )
            return conn  # Si la conexión es exitosa, la devuelve
        except pymysql.err.OperationalError as e:
            # Si el error es "Connection refused", espera y reintenta
            if e.args[0] == 2003 and attempt < max_retries - 1:
                print(f"Intento {attempt + 1}: No se pudo conectar a la base de datos, reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                # Si es otro error o el último intento, lanza la excepción
                raise e


def get_s3_client():
    """
    Devuelve un cliente S3 configurado para Cloudflare R2.

    La configuración utiliza ``signature_version='s3v4'`` y ``addressing_style='virtual'``
    según las recomendaciones de Cloudflare R2.  Además se omite el parámetro
    ``verify=False`` para permitir la verificación TLS y se especifica
    ``region_name='auto'`` para que R2 determine la región adecuada.
    """
    cfg = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'virtual'}
    )
    return boto3.client(
        's3',
        endpoint_url=os.getenv('R2_ENDPOINT_URL'),
        aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        region_name='auto',
        config=cfg
    )


def _codes_list(raw: str):
    if not raw:
        return []
    return [c.strip().upper() for c in raw.replace("\n", ",").replace(";", ",").replace(" ", ",").split(",") if c.strip()]




def _parse_date(raw: str) -> str | None:
    """
    Intenta convertir la fecha recibida en varios formatos a ISO (YYYY-MM-DD).
    Si no logra parsear, devuelve None.
    """
    if not raw:
        return None

    raw = raw.strip()

    # Lista de formatos aceptados
    formatos = [
        "%Y-%m-%d",  # 2025-02-04
        "%d/%m/%Y",  # 04/02/2025
        "%d-%m-%Y",  # 04-02-2025
        "%m/%d/%Y",  # 02/04/2025
        "%m-%d-%Y",  # 02-04-2025
    ]

    for fmt in formatos:
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")  # Normalizamos a ISO
        except ValueError:
            continue

    return None


# ==================== RUTAS CRUD y Búsqueda ====================

@documentos_bp.route("/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No se envió el archivo PDF"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Archivo sin nombre"}), 400

    tenant_id = g.tenant_id
    filename = secure_filename(f.filename)
    object_key = f"{tenant_id}/{filename}"
    bucket_name = os.getenv("R2_BUCKET_NAME")
    s3 = get_s3_client()

    try:
        s3.upload_fileobj(f, bucket_name, object_key, ExtraArgs={'ContentType': f.content_type})
    except Exception as e:
        print(f"Error al subir a R2: {str(e)}")
        return jsonify({"error": "Error interno al guardar el archivo."}), 500

    name = request.form.get("nombre") or request.form.get("name") or filename
    # Intenta obtener y convertir la fecha a ISO; si no es válida, devolverá None
    raw_date = request.form.get("fecha") or request.form.get("date") or ""
    date_iso = _parse_date(raw_date)
    codigos = request.form.get("codigos") or request.form.get("codigos_extraidos")

    # Validar fecha: la columna 'date' en la BD es NOT NULL, por lo que se requiere una fecha válida
    if date_iso is None:
        return jsonify({"error": "Formato de fecha no válido; utilice YYYY-MM-DD o DD/MM/YYYY"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (name, date, path) VALUES (%s, %s, %s)",
                (name, date_iso, object_key),
            )
            document_id = cur.lastrowid
            if codigos:
                for code in _codes_list(codigos):
                    cur.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                        (document_id, code),
                    )
        return jsonify({"ok": True, "id": document_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/", methods=["GET"])
def listar_documentos():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id, d.name, d.date, d.path,
                    GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.id DESC
                """
            )
            rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/ ", methods=["GET"])
def obtener_documento(doc_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id, d.name, d.date, d.path,
                    GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                WHERE d.id = %s
                GROUP BY d.id
                """,
                (doc_id,),
            )
            row = cur.fetchone()
        if row:
            return jsonify(row)
        return jsonify({"error": "Documento no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/ ", methods=["PUT"])
def editar_documento(doc_id):
    name = request.form.get("nombre") or request.form.get("name")
    # Intenta convertir la fecha a ISO; puede ser opcional, pero si no se especifica se mantendrá
    raw_date = request.form.get("fecha") or request.form.get("date") or ""
    date_iso = _parse_date(raw_date) if raw_date else None
    codigos = request.form.get("codigos") or request.form.get("codigos_extraidos")

    new_object_key = None
    old_object_key = None
    
    # 1. Lógica para manejar la actualización del archivo PDF
    if "file" in request.files:
        new_file = request.files["file"]
        if new_file and new_file.filename:
            tenant_id = g.tenant_id
            filename = secure_filename(new_file.filename)
            new_object_key = f"{tenant_id}/{filename}"
            bucket_name = os.getenv("R2_BUCKET_NAME")
            s3 = get_s3_client()
            
            try:
                # Primero, subimos el nuevo archivo a R2
                s3.upload_fileobj(new_file, bucket_name, new_object_key, ExtraArgs={'ContentType': new_file.content_type})
            except Exception as e:
                print(f"Error al subir el nuevo archivo a R2 durante la edición: {str(e)}")
                return jsonify({"error": "No se pudo actualizar el archivo en el almacenamiento."}), 500

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Si subimos un archivo nuevo, necesitamos borrar el antiguo de R2
            if new_object_key:
                # Obtenemos la ruta (key) del archivo antiguo ANTES de actualizar la BD
                cur.execute("SELECT path FROM documents WHERE id=%s", (doc_id,))
                result = cur.fetchone()
                if result:
                    old_object_key = result.get('path')

            # 2. Construir la consulta SQL dinámicamente
            sql_parts = ["name=%s"]
            params = [name]
            # Si se proporcionó una fecha (ya convertida), añadir al SET
            if date_iso is not None:
                sql_parts.append("date=%s")
                params.append(date_iso)
            # Si se subió un archivo, actualizar también el path
            if new_object_key:
                sql_parts.append("path=%s")
                params.append(new_object_key)

            params.append(doc_id)
            query = f"UPDATE documents SET {', '.join(sql_parts)} WHERE id=%s"
            cur.execute(query, tuple(params))

            # 3. Actualizar los códigos (lógica sin cambios)
            if codigos is not None:
                cur.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
                for code in _codes_list(codigos):
                    cur.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                        (doc_id, code),
                    )
        # 4. Si todo salió bien en la BD y reemplazamos un archivo, borrar el antiguo de R2
        if old_object_key and old_object_key != new_object_key:
            try:
                s3 = get_s3_client()
                s3.delete_object(Bucket=os.getenv("R2_BUCKET_NAME"), Key=old_object_key)
            except Exception as e:
                # Si falla el borrado, solo lo registramos, no revertimos la operación
                print(f"ADVERTENCIA: No se pudo borrar el archivo antiguo '{old_object_key}' de R2: {e}")

        return jsonify({"ok": True})
    except Exception as e:
        # Si hay un error con la BD, debemos borrar el nuevo archivo que ya subimos a R2
        if new_object_key:
            try:
                s3 = get_s3_client()
                s3.delete_object(Bucket=os.getenv("R2_BUCKET_NAME"), Key=new_object_key)
            except:
                pass  # Ignorar error de borrado en cascada
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/ ", methods=["DELETE"])
def eliminar_documento(doc_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT path FROM documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if row and row.get("path"):
                try:
                    s3 = get_s3_client()
                    s3.delete_object(Bucket=os.getenv("R2_BUCKET_NAME"), Key=row["path"])
                except Exception as e:
                    print(f"Advertencia: No se pudo eliminar de R2 el objeto {row['path']}: {e}")
            
            cur.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        return jsonify({"ok": True, "message": "Documento eliminado correctamente"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/search_by_code", methods=["POST"])
def buscar_por_codigo():
    data = request.get_json(silent=True) or {}
    codigo_buscado = (data.get("codigo") or "").strip().upper()
    modo = (data.get("modo") or "like").lower()

    if not codigo_buscado:
        return jsonify([])

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if modo in ("prefijo", "prefix"):
                cur.execute(
                    "SELECT DISTINCT c.code FROM codes c WHERE UPPER(c.code) LIKE %s ORDER BY c.code LIMIT 50",
                    (codigo_buscado + "%",),
                )
                return jsonify([r["code"] for r in cur.fetchall()])

            op = "=" if modo in ("exacto", "exact") else "LIKE"
            termino = codigo_buscado if op == "=" else f"%{codigo_buscado}%"

            cur.execute(f"SELECT id FROM documents WHERE UPPER(name) {op} %s", (termino,))
            ids_from_name = {row["id"] for row in cur.fetchall()}

            cur.execute(f"SELECT document_id AS id FROM codes WHERE UPPER(code) {op} %s", (termino,))
            ids_from_code = {row["id"] for row in cur.fetchall()}

            ids_documentos = list(ids_from_name | ids_from_code)

            if not ids_documentos:
                return jsonify([])

            placeholders = ",".join(["%s"] * len(ids_documentos))
            cur.execute(
                f"""
                SELECT 
                    d.id, d.name, d.date, d.path,
                    COALESCE(GROUP_CONCAT(c.code ORDER BY c.code), 'N/A') AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON d.id = c.document_id
                WHERE d.id IN ({placeholders})
                GROUP BY d.id
                ORDER BY d.id DESC
                """,
                tuple(ids_documentos),
            )
            rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.open:
            conn.close()


@documentos_bp.route("/search_optima", methods=["POST"])
def busqueda_optima():
    data = request.get_json(silent=True) or {}
    texto = (data.get("codigos") or data.get("texto") or "").strip()
    if not texto:
        return jsonify({"error": "No se proporcionaron códigos"}), 400

    pedidos = list({c.strip().upper() for c in texto.replace(",", " ").replace("\n", " ").split() if c.strip()})
    if not pedidos:
        return jsonify({"error": "No se detectaron códigos válidos"}), 400

    fmt = ",".join(["%s"] * len(pedidos))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT d.*, GROUP_CONCAT(DISTINCT UPPER(c.code)) AS codigos_encontrados
                FROM documents d
                JOIN codes c ON c.document_id = d.id
                WHERE UPPER(c.code) IN ({fmt})
                GROUP BY d.id
                ORDER BY d.date DESC
                """,
                pedidos,
            )
            docs = cur.fetchall()
    finally:
        if conn and conn.open:
            conn.close()

    docs_sets = [{"doc": d, "codes": {x.strip().upper() for x in (d.get("codigos_encontrados") or "").split(",") if x.strip()}} for d in docs]
    
    faltantes = set(pedidos)
    seleccionados = []
    while faltantes and docs_sets:
        docs_sets.sort(key=lambda d: len(d["codes"] & faltantes), reverse=True)
        best = docs_sets.pop(0)
        cubre = best["codes"] & faltantes
        if not cubre:
            break
        seleccionados.append({"documento": best["doc"], "codigos_cubre": sorted(list(cubre))})
        faltantes -= cubre

    return jsonify({"documentos": seleccionados, "codigos_faltantes": sorted(list(faltantes))})


@documentos_bp.route("/resaltar", methods=["POST"])
def resaltar_pdf_remoto():
    data = request.get_json(silent=True) or {}
    pdf_path = data.get("pdf_path")
    codes_list = data.get("codes")

    if not pdf_path or not codes_list:
        return jsonify({"error": "Faltan datos (pdf_path, codes)"}), 400

    highlighter_url = os.getenv("HIGHLIGHTER_URL")
    if not highlighter_url:
        return jsonify({"error": "El servicio de resaltado no está configurado"}), 500

    s3 = get_s3_client()
    bucket_name = os.getenv("R2_BUCKET_NAME")
    try:
        pdf_object = s3.get_object(Bucket=bucket_name, Key=pdf_path)
        pdf_content = pdf_object['Body'].read()
    except Exception as e:
        print(f"Error descargando de R2 el objeto {pdf_path}: {e}")
        return jsonify({"error": f"Archivo PDF no encontrado en el almacenamiento: {pdf_path}"}), 404

    try:
        files = {"pdf_file": (os.path.basename(pdf_path), pdf_content, "application/pdf")}
        payload = {"specific_codes": ",".join(codes_list)}
        
        r = requests.post(highlighter_url, files=files, data=payload, timeout=180)
        r.raise_for_status()

        html_content = r.text
        match = re.search(r'href="(/descargar/[^\"]+)"', html_content)
        if not match:
            error_match = re.search(r'\s*(.+?)\s*', html_content, re.DOTALL)
            error_message = (error_match.group(1).strip() if error_match else "No se pudo procesar el PDF.")
            return jsonify({"error": error_message}), 500

        download_path = match.group(1)
        final_pdf_url = highlighter_url.rstrip("/") + download_path
        final_pdf_response = requests.get(final_pdf_url, stream=True, timeout=180)
        final_pdf_response.raise_for_status()

        return Response(
            final_pdf_response.content,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename=resaltado_{os.path.basename(pdf_path)}"},
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error de comunicación con el servicio de resaltado: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500