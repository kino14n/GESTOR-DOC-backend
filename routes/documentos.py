from flask import Blueprint, request, jsonify
import pymysql
import os

documentos_bp = Blueprint('documentos_bp', __name__)

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('MYSQLHOST'),        # Nombre exacto de variable en Railway
        user=os.environ.get('MYSQLUSER'),
        password=os.environ.get('MYSQLPASSWORD'),
        database=os.environ.get('MYSQL_DATABASE'),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

@documentos_bp.route('/api/documentos/importar_sql', methods=['POST'])
def importar_sql():
    if 'file' not in request.files:
        return jsonify({"error": "Archivo no enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Archivo sin nombre"}), 400

    try:
        sql_script = file.read().decode('utf-8')
    except Exception as e:
        return jsonify({"error": f"Error al leer archivo: {str(e)}"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for statement in sql_script.split(';'):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
        return jsonify({"message": "Archivo SQL importado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error ejecutando script SQL: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@documentos_bp.route('/api/documentos', methods=['GET'])
def listar_documentos():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM documentos")
            result = cursor.fetchall()
        return jsonify(result)
    finally:
        conn.close()

        from flask import jsonify
import os

@documentos_bp.route('/api/env', methods=['GET'])
def mostrar_env():
    vars_esperadas = [
        'MYSQLHOST', 'MYSQLUSER', 'MYSQLPASSWORD', 'MYSQL_DATABASE', 'MYSQLPORT', 'MYSQL_URL'
    ]
    env_vars = {var: os.environ.get(var) for var in vars_esperadas}
    return jsonify(env_vars)

@documentos_bp.route('/api/ping', methods=['GET'])
def ping():
    try:
        conn = get_db_connection()  # Esto debe ir con 4 espacios de indentación
        conn.close()                # Igual aquí, 4 espacios
        return jsonify({"message": "pong", "db": "conexión exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

