import os
import pymysql
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

documentos_bp = Blueprint('documentos', __name__)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    connection = pymysql.connect(
        host=os.getenv('MYSQLHOST'),
        user=os.getenv('MYSQLUSER'),
        password=os.getenv('MYSQLPASSWORD'),
        db=os.getenv('MYSQL_DATABASE'),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    return connection

# Importar SQL
@documentos_bp.route('/api/documentos/importar_sql', methods=['POST'])
def importar_sql():
    if 'file' not in request.files:
        return jsonify({'error': 'No se ha enviado ningún archivo'}), 400

    archivo = request.files['file']
    if archivo.filename == '':
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400

    contenido = archivo.read().decode('utf-8')
    sentencias = [s.strip() for s in contenido.split(';') if s.strip()]

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            for sentencia in sentencias:
                cursor.execute(sentencia)
        return jsonify({'mensaje': 'SQL importado exitosamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Listar documentos con sus códigos asociados correctamente
@documentos_bp.route('/api/documentos', methods=['GET'])
def listar_documentos():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    d.id,
                    d.name,
                    d.date,
                    d.path,
                    GROUP_CONCAT(c.code ORDER BY c.code SEPARATOR ', ') AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.id DESC
            """)
            resultado = cursor.fetchall()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Subir documento
@documentos_bp.route('/api/documentos/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió el archivo PDF'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Archivo sin nombre'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    name = request.form.get('nombre') or request.form.get('name')
    date = request.form.get('fecha') or request.form.get('date')
    codigos = request.form.get('codigos') or request.form.get('codigos_extraidos')

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Insertar documento
            cursor.execute("""
                INSERT INTO documents (name, date, path)
                VALUES (%s, %s, %s)
            """, (name, date, filename))
            document_id = cursor.lastrowid

            # 2. Insertar códigos en la tabla codes
            if codigos:
                lista_codigos = [c.strip() for c in codigos.replace('\n', ',').replace(';', ',').split(',') if c.strip()]
                for code in lista_codigos:
                    cursor.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)", 
                        (document_id, code)
                    )
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Editar documento y códigos
@documentos_bp.route('/api/documentos/<int:doc_id>', methods=['PUT'])
def editar_documento(doc_id):
    data = request.form or request.json or {}
    name = data.get('nombre') or data.get('name')
    date = data.get('fecha') or data.get('date')
    codigos = data.get('codigos') or data.get('codigos_extraidos')

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE documents SET name=%s, date=%s WHERE id=%s
            """, (name, date, doc_id))
            # Actualizar códigos
            if codigos is not None:
                # Borrar códigos antiguos
                cursor.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
                # Insertar nuevos códigos
                lista_codigos = [c.strip() for c in codigos.replace('\n', ',').replace(';', ',').split(',') if c.strip()]
                for code in lista_codigos:
                    cursor.execute(
                        "INSERT INTO codes (document_id, code) VALUES (%s, %s)", 
                        (doc_id, code)
                    )
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Búsqueda inteligente voraz (busca en codes y nombre)
@documentos_bp.route('/api/documentos/search', methods=['POST'])
def busqueda_voraz():
    data = request.get_json()
    texto = data.get('texto', '').strip()
    if not texto:
        return jsonify([])

    codigos = [c.strip().upper() for c in texto.replace(',', ' ').replace('\n', ' ').split() if c.strip()]
    if not codigos:
        return jsonify([])

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Busqueda voraz en códigos y nombre
            query = """
                SELECT 
                    d.id,
                    d.name,
                    d.date,
                    d.path,
                    GROUP_CONCAT(c.code ORDER BY c.code SEPARATOR ', ') AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                WHERE 
                    {}
                GROUP BY d.id
                ORDER BY d.id DESC
            """.format(
                " OR ".join(
                    ["c.code LIKE %s OR d.name LIKE %s OR d.path LIKE %s"] * len(codigos)
                )
            )
            params = []
            for cod in codigos:
                like = f"%{cod}%"
                params.extend([like, like, like])
            cursor.execute(query, params)
            resultado = cursor.fetchall()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Buscar por código exacto (en tabla codes)


@documentos_bp.route('/api/documentos/search_optima', methods=['POST'])
def busqueda_optima():
    data = request.get_json()
    texto = data.get('codigos', '').strip()
    if not texto:
        return jsonify({'error': 'No se proporcionaron códigos'}), 400

    # Normaliza/captura los códigos
    codigos = [c.strip().upper() for c in texto.replace(',', ' ').replace('\n', ' ').split() if c.strip()]
    codigos = list(set(codigos))  # quita duplicados
    cantidad = len(codigos)
    if cantidad == 0:
        return jsonify({'error': 'No se detectaron códigos válidos'}), 400

    formato = ','.join(['%s'] * cantidad)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Buscar en qué documentos están los códigos buscados
            cursor.execute(f"""
                SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_encontrados,
                    COUNT(DISTINCT c.code) AS encontrados
                FROM documents d
                JOIN codes c ON c.document_id = d.id
                WHERE c.code IN ({formato})
                GROUP BY d.id
                HAVING encontrados = %s
                ORDER BY d.date DESC
                LIMIT 1
            """, codigos + [cantidad])
            docs = cursor.fetchall()

            if docs:
                # Si hay un documento que tiene todos los códigos, devuélvelo
                return jsonify({
                    "tipo": "exito",
                    "mensaje": "Documento que contiene todos los códigos buscados.",
                    "documentos": docs,
                    "codigos_faltantes": []
                })
            else:
                # Si no hay, buscar qué códigos no existen en ningún documento
                cursor.execute(f"""
                    SELECT DISTINCT code FROM codes WHERE code IN ({formato})
                """, codigos)
                encontrados = [r['code'].upper() for r in cursor.fetchall()]
                faltantes = [c for c in codigos if c not in encontrados]

                # (Opcional) Traer los documentos que cubren la mayor cantidad de códigos posible
                cursor.execute(f"""
                    SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_encontrados,
                        COUNT(DISTINCT c.code) AS encontrados
                    FROM documents d
                    JOIN codes c ON c.document_id = d.id
                    WHERE c.code IN ({formato})
                    GROUP BY d.id
                    ORDER BY encontrados DESC, d.date DESC
                    LIMIT 3
                """, codigos)
                docs_parciales = cursor.fetchall()

                return jsonify({
                    "tipo": "parcial",
                    "mensaje": "Ningún documento contiene todos los códigos buscados.",
                    "documentos": docs_parciales,
                    "codigos_faltantes": faltantes
                })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


# Mostrar variables de entorno
@documentos_bp.route('/api/env', methods=['GET'])
def mostrar_env():
    vars_esperadas = [
        'MYSQLHOST', 'MYSQLUSER', 'MYSQLPASSWORD', 'MYSQL_DATABASE', 'MYSQLPORT', 'MYSQL_URL'
    ]
    env_vars = {var: os.environ.get(var) for var in vars_esperadas}
    return jsonify(env_vars)

# Ping
@documentos_bp.route('/api/ping', methods=['GET'])
def ping():
    try:
        connection = get_db_connection()
        connection.close()
        return jsonify({"message": "pong", "db": "conexión exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
