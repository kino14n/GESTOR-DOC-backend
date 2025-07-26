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
        charset='utf8mb4', 
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
                    GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
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

# Obtener un solo documento por ID (Método GET)
@documentos_bp.route('/api/documentos/<int:doc_id>', methods=['GET'])
def obtener_documento(doc_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
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
            """, (doc_id,))
            resultado = cursor.fetchone() 
            if resultado:
                return jsonify(resultado)
            else:
                return jsonify({'error': 'Documento no encontrado'}), 404
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
                lista_codigos = [c.strip().upper() for c in codigos.replace('\n', ',').replace(';', ',').split(',') if c.strip()]
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

# Editar documento y códigos (Método PUT)
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
                cursor.execute("DELETE FROM codes WHERE document_id=%s", (doc_id,))
                lista_codigos = [c.strip().upper() for c in codigos.replace('\n', ',').replace(';', ',').split(',') if c.strip()]
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

# Eliminar documento (Método DELETE)
@documentos_bp.route('/api/documentos/<int:doc_id>', methods=['DELETE'])
def eliminar_documento(doc_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Primero, obtener la ruta del PDF para eliminar el archivo físico
            cursor.execute("SELECT path FROM documents WHERE id = %s", (doc_id,))
            doc_path = cursor.fetchone()
            if doc_path and doc_path['path']:
                file_path = os.path.join(UPLOAD_FOLDER, doc_path['path'])
                if os.path.exists(file_path):
                    os.remove(file_path) 
                    print(f"Archivo eliminado: {file_path}") 
                else:
                    print(f"Advertencia: Archivo no encontrado en {file_path}") 

            # Luego, eliminar registros de la base de datos (códigos y luego documento)
            cursor.execute("DELETE FROM codes WHERE document_id = %s", (doc_id,))
            cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        
        return jsonify({'ok': True, 'message': 'Documento eliminado correctamente'})
    except Exception as e:
        print(f"Error al eliminar documento {doc_id}: {e}") 
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        connection.close()

# Búsqueda voraz agrupada
@documentos_bp.route('/api/documentos/search', methods=['POST'])
def busqueda_voraz():
    data = request.get_json()
    texto = data.get('texto', '').strip()
    if not texto:
        return jsonify([])

    codigos = [c.strip().upper() for c in texto.replace(',', ' ').replace('\n', ' ').split() if c.strip()]
    if not codigos:
        return jsonify([])

    formato = ','.join(['%s'] * len(codigos))
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_extraidos
                FROM documents d
                LEFT JOIN codes c ON c.document_id = d.id
                WHERE c.code IN ({formato})
                GROUP BY d.id
                ORDER BY d.id DESC
            """, codigos)
            resultado = cursor.fetchall()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Buscar por código exacto (solo devuelve los códigos coincidentes)
@documentos_bp.route('/api/documentos/search_by_code', methods=['POST'])
def buscar_por_codigo():
    data = request.get_json()
    codigo = data.get('codigo', '').strip()
    if not codigo:
        return jsonify([])

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Seleccionar solo los códigos distintivos que comiencen con el patrón
            query = """
                SELECT DISTINCT c.code 
                FROM codes c
                WHERE c.code LIKE %s
                ORDER BY c.code ASC
                LIMIT 100 
            """
            like = f"{codigo}%" 
            cursor.execute(query, (like,))
            resultado = [row['code'] for row in cursor.fetchall()] 
        return jsonify(resultado) 
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# Búsqueda óptima (set cover voraz: menor número de documentos que cubren todos los códigos)
@documentos_bp.route('/api/documentos/search_optima', methods=['POST'])
def busqueda_optima():
    data = request.get_json()
    texto = data.get('codigos', '').strip()
    if not texto:
        return jsonify({'error': 'No se proporcionaron códigos'}), 400

    codigos = [c.strip().upper() for c in texto.replace(',', ' ').replace('\n', ' ').split() if c.strip()]
    codigos = list(set(codigos))
    if not codigos:
        return jsonify({'error': 'No se detectaron códigos válidos'}), 400

    formato = ','.join(['%s'] * len(codigos))
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Traer todos los documentos que tengan al menos uno de los códigos
            cursor.execute(f"""
                SELECT d.*, GROUP_CONCAT(c.code ORDER BY c.code) AS codigos_encontrados
                FROM documents d
                JOIN codes c ON c.document_id = d.id 
                WHERE c.code IN ({formato})
                GROUP BY d.id
                ORDER BY d.date DESC
            """, codigos)
            docs = cursor.fetchall()

        # 2. Armamos sets por documento
        docs_sets = []
        for doc in docs:
            codes_set = set([c.strip().upper() for c in (doc['codigos_encontrados'] or '').split(',') if c.strip()])
            docs_sets.append({
                "doc": doc,
                "codes": codes_set
            })

        codigos_faltantes = set(codigos)
        docs_seleccionados = []
        while codigos_faltantes and docs_sets:
            # Elige el doc que cubre la mayor cantidad de códigos faltantes, más reciente primero
            docs_sets.sort(key=lambda d: len(d['codes'] & codigos_faltantes), reverse=True)
            mejor_doc = docs_sets.pop(0)
            cubiertos = mejor_doc['codes'] & codigos_faltantes
            if not cubiertos:
                break
            docs_seleccionados.append({
                "documento": mejor_doc['doc'],
                "codigos_cubre": list(cubiertos)
            })
            codigos_faltantes -= cubiertos

        resultado = {
            "documentos": docs_seleccionados,
            "codigos_faltantes": list(codigos_faltantes)
        }
        return jsonify(resultado)

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