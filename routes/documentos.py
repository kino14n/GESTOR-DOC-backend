# GESTOR-DOC-backend/routes/documentos.py
import os
import re
import pymysql
import requests
from flask import Blueprint, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename

documentos_bp = Blueprint("documentos", __name__)

# --- UPLOADS: usa volumen de Railway si existe, si no carpeta local ---
UPLOAD_FOLDER = "/data/uploads" if os.path.exists("/data/uploads") else os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------- DB helpers --------------------
def _env(name, fallback=""):
    """
    Lee variables DB_* o sus equivalentes MYSQL* que inyecta Railway.
    """
    mapping = {
        "DB_HOST": "MYSQLHOST",
        "DB_PORT": "MYSQLPORT",
        "DB_USER": "MYSQLUSER",
        "DB_PASS": "MYSQLPASSWORD",
        "DB_NAME": "MYSQLDATABASE",  # OJO: Railway usa MYSQLDATABASE (sin guión bajo)
    }
    return os.getenv(name) or os.getenv(mapping.get(name, ""), fallback)

def get_db_connection():
    """
    Acepta tanto MYSQLDATABASE como MYSQL_DATABASE (compat).
    """
    db_name = os.getenv("MYSQL_DATABASE") or _env("DB_NAME")
    return pymysql.connect(
        host=_env("DB_HOST", "127.0.0.1"),
        port=int(_env("DB_PORT", "3306") or "3306"),
        user=_env("DB_USER"),
        password=_env("DB_PASS"),
        database=db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

def _codes_list(raw: str):
    if not raw:
        return []
    return [c.strip().upper() for c in raw.replace("\n", ",").replace(";", ",").replace(" ", ",").split(",") if c.strip()]

# ==================== RUTAS ====================

# Importación de SQL (útil para seed)
@documentos_bp.route("/importar_sql", methods=["POST"])
def importar_sql():
    if "file" not in request.files:
        return jsonify({"error": "No se ha enviado ningún archivo"}), 400
    archivo = request.files["file"]
    if not archivo.filename:
        return jsonify({"error": "No se ha seleccionado ningún archivo"}), 400

    contenido = archivo.read().decode("utf-8", errors="ignore")
    sentencias = [s.strip() for s in contenido.split(";") if s.strip()]
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for s in sentencias:
                cur.execute(s)
        return jsonify({"mensaje": "SQL importado exitosamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Listado
@documentos_bp.route("", methods=["GET"])
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
        conn.close()

# Obtener uno
@documentos_bp.route("/<int:doc_id>", methods=["GET"])
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
        conn.close()

# Subir
@documentos_bp.route("/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No se envió el archivo PDF"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Archivo sin nombre"}), 400

    filename = secure_filename(f.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    f.save(file_path)

    name = request.form.get("nombre") or request.form.get("name") or filename
    date = request.form.get("fecha") or request.form.get("date")
    codigos = request.form.get("codigos") or request.form.get("codigos_extraidos")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (name, date, path) VALUES (%s, %s, %s)",
                (name, date, filename),
            )
            document_id = cur.lastrowid

            for code in _codes_list(codigos):
                cur.execute(
                    "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                    (document_id, code),
                )
        return jsonify({"ok": True, "id": document_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Editar
@documentos_bp.route("/<int:doc_id>", methods=["PUT"])
def editar_documento(doc_id):
    data = request.form or request.json or {}
    name = data.get("nombre") or data.get("name")
    date = data.get("fecha") or data.get("date")
    codigos = data.get("codigos") or data.get("codigos_extraidos")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE documents SET name=%s, date=%s WHERE id=%s", (name, date, doc_id))
            if codigos is not None:
                cur.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
                for code in _codes_list(codigos):
                    cur.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                        (doc_id, code),
                    )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Eliminar
@documentos_bp.route("/<int:doc_id>", methods=["DELETE"])
def eliminar_documento(doc_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT path FROM documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if row and row.get("path"):
                fp = os.path.join(UPLOAD_FOLDER, row["path"])
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
            cur.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        return jsonify({"ok": True, "message": "Documento eliminado correctamente"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

# Búsqueda simple por lista de códigos/nombre
@documentos_bp.route("/search", methods=["POST"])
def busqueda_voraz():
    data = request.get_json(silent=True) or {}
    texto = (data.get("texto") or "").strip()
    if not texto:
        return jsonify([])

    codigos = [c.strip().upper() for c in texto.replace(",", " ").replace("\n", " ").split() if c.strip()]
    if not codigos:
        return jsonify([])

    fmt = ",".join(["%s"] * len(codigos))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                WHERE c.code IN ({fmt})
                GROUP BY d.id
                ORDER BY d.id DESC
                """,
                codigos,
            )
            rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Sugerencias y búsqueda por código/nombre
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
            # Autocompletado por prefijo => lista de códigos
            if modo in ("prefijo", "prefix"):
                cur.execute(
                    """
                    SELECT DISTINCT c.code FROM codes c
                    WHERE UPPER(c.code) LIKE %s ORDER BY c.code LIMIT 50
                    """,
                    (codigo_buscado + "%",),
                )
                return jsonify([r["code"] for r in cur.fetchall()])

            # exacto => "="; like => LIKE con comodín
            if modo in ("exacto", "exact"):
                termino_name = codigo_buscado
                termino_code = codigo_buscado
                op = "="
            else:
                termino_name = f"%{codigo_buscado}%"
                termino_code = f"%{codigo_buscado}%"
                op = "LIKE"

            # --- INICIO DEL CÓDIGO CORREGIDO ---
            # 1. Buscar documentos con nombres coincidentes
            cur.execute(f"SELECT id FROM documents WHERE UPPER(name) {op} %s", (termino_name,))
            ids_from_name = {row["id"] for row in cur.fetchall()}

            # 2. Buscar documentos con códigos coincidentes
            cur.execute(f"SELECT document_id AS id FROM codes WHERE UPPER(code) {op} %s", (termino_code,))
            ids_from_code = {row["id"] for row in cur.fetchall()}

            # 3. Combinar los resultados (usando conjuntos para evitar duplicados)
            ids_documentos = list(ids_from_name | ids_from_code)
            # --- FIN DEL CÓDIGO CORREGIDO ---

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
                GROUP BY d.id, d.name, d.date, d.path
                ORDER BY d.id DESC
                """,
                tuple(ids_documentos),
            )
            rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Set cover voraz (óptima)
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
        conn.close()

    docs_sets = []
    for d in docs:
        codes_set = {x.strip().upper() for x in (d.get("codigos_encontrados") or "").split(",") if x.strip()}
        docs_sets.append({"doc": d, "codes": codes_set})

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

# Resaltado de PDF a través de servicio externo
@documentos_bp.route("/resaltar", methods=["POST"])
def resaltar_pdf_remoto():
    data = request.get_json(silent=True) or {}
    if "pdf_path" not in data or "codes" not in data:
        return jsonify({"error": "Faltan datos (pdf_path, codes)"}), 400

    pdf_filename = data["pdf_path"]
    codes_list = data["codes"]

    highlighter_url = os.getenv("HIGHLIGHTER_URL")
    if not highlighter_url:
        return jsonify({"error": "El servicio de resaltado no está configurado (falta HIGHLIGHTER_URL)"}), 500

    local_pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
    if not os.path.exists(local_pdf_path):
        return jsonify({"error": f"Archivo PDF no encontrado: {pdf_filename}"}), 404

    try:
        with open(local_pdf_path, "rb") as pdf_file:
            files = {"pdf_file": (pdf_filename, pdf_file, "application/pdf")}
            payload = {"specific_codes": ",".join(codes_list)}
            r = requests.post(highlighter_url, files=files, data=payload, timeout=180)
            r.raise_for_status()

        html_content = r.text
        match = re.search(r'href="(/descargar/[^"]+)"', html_content)
        if not match:
            error_match = re.search(r'<div class="flash-message error">\s*(.+?)\s*</div>', html_content, re.DOTALL)
            error_message = (error_match.group(1).strip() if error_match else "No se pudo procesar el PDF.")
            return jsonify({"error": error_message}), 500

        download_path = match.group(1)
        final_pdf_url = highlighter_url.rstrip("/") + download_path
        final_pdf_response = requests.get(final_pdf_url, stream=True, timeout=180)
        final_pdf_response.raise_for_status()

        return Response(
            final_pdf_response.content,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename=resaltado_{pdf_filename}"},
        )

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error de comunicación con el servicio de resaltado: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# Servir PDFs subidos (para "Ver PDF")
@documentos_bp.route("/files/<path:filename>", methods=["GET"])
def descargar_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False, mimetype="application/pdf")

# Utilidad/env/ping (opcionales si ya tienes /api/env y /api/ping en app.py)
@documentos_bp.route("/env", methods=["GET"])
def mostrar_env():
    keys = [
        "MYSQLHOST","MYSQLUSER","MYSQLPASSWORD","MYSQLDATABASE","MYSQLPORT","MYSQL_URL",
        "DB_HOST","DB_PORT","DB_USER","DB_PASS","DB_NAME",
    ]
    return jsonify({k: os.getenv(k) for k in keys})

@documentos_bp.route("/ping", methods=["GET"])
def ping():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"message": "pong", "db": "conexión exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500