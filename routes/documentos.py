
# routes/documentos.py — GESTOR-DOC
import os
import pymysql
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

documentos_bp = Blueprint("documentos", __name__)

# Carpeta de uploads (relativa al working dir en Railway)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------- DB helpers --------------------
def _env(name, fallback=""):
    mapping = {
        "DB_HOST": "MYSQLHOST",
        "DB_PORT": "MYSQLPORT",
        "DB_USER": "MYSQLUSER",
        "DB_PASS": "MYSQLPASSWORD",
        "DB_NAME": "MYSQLDATABASE",
    }
    return os.getenv(name) or os.getenv(mapping.get(name, ""), fallback)

def get_db_connection():
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

# ==================== RUTAS ====================

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

@documentos_bp.route("", methods=["GET"])
@documentos_bp.route("/", methods=["GET"])
def listar_documentos():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id,
                    d.name,
                    d.date,
                    d.path,
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

@documentos_bp.route("/<int:doc_id>", methods=["GET"])
def obtener_documento(doc_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id,
                    d.name,
                    d.date,
                    d.path,
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

    name = request.form.get("nombre") or request.form.get("name")
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

            if codigos:
                lista = [
                    c.strip().upper()
                    for c in codigos.replace("\n", ",").replace(";", ",").split(",")
                    if c.strip()
                ]
                for code in lista:
                    cur.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                        (document_id, code),
                    )
        return jsonify({"ok": True, "id": document_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

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
                lista = [
                    c.strip().upper()
                    for c in codigos.replace("\n", ",").replace(";", ",").split(",")
                    if c.strip()
                ]
                for code in lista:
                    cur.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)",
                        (doc_id, code),
                    )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

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

@documentos_bp.route("/search_by_code", methods=["POST"])
def buscar_por_codigo():
    data = request.get_json(silent=True) or {}
    codigo = (data.get("codigo") or "").strip().upper()
    modo = (data.get("modo") or "like").lower()

    if not codigo:
        return jsonify([])

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if modo in ("prefijo", "prefix"):
                cur.execute(
                    """
                    SELECT DISTINCT c.code
                    FROM codes c
                    WHERE UPPER(c.code) LIKE %s
                    ORDER BY c.code
                    LIMIT 50
                    """, (codigo + "%",),
                )
                return jsonify([r["code"] for r in cur.fetchall()])

            if modo == "exacto":
                where = "UPPER(c.code) = %s"
                val = (codigo,)
            else:
                where = "UPPER(c.code) LIKE %s"
                val = ("%" + codigo + "%",)

            cur.execute(
                f"""
                SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                WHERE {where}
                GROUP BY d.id
                ORDER BY d.id DESC
                """, val,
            )
            rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
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
                """, pedidos,
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

@documentos_bp.route("/env", methods=["GET"])
def mostrar_env():
    vars_esperadas = [
        "MYSQLHOST","MYSQLUSER","MYSQLPASSWORD","MYSQLDATABASE","MYSQLPORT","MYSQL_URL",
        "DB_HOST","DB_PORT","DB_USER","DB_PASS","DB_NAME",
    ]
    env_vars = {v: os.getenv(v) for v in vars_esperadas}
    return jsonify(env_vars)

@documentos_bp.route("/ping", methods=["GET"])
def ping():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"message": "pong", "db": "conexión exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
