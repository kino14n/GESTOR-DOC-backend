from flask import Blueprint, request, jsonify
import pymysql
import os

documentos_bp = Blueprint('documentos_bp', __name__)

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('MYSQLHOST'),        # mysql.railway.internal o tu host MySQL
        user=os.environ.get('MYSQLUSER'),        # root u otro usuario
        password=os.environ.get('MYSQLPASSWORD'),# contraseña
        database=os.environ.get('MYSQL_DATABASE'),# nombre base de datos
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

# Ruta para listar documentos (opcional)
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
