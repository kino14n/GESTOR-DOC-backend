from flask import Blueprint, request, jsonify
import pymysql
import os

documentos_bp = Blueprint('documentos_bp', __name__)

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('MYSQLHOST'),        # mysql.railway.internal
        user=os.environ.get('MYSQLUSER'),        # root
        password=os.environ.get('MYSQLPASSWORD'),# contraseña
        database=os.environ.get('MYSQL_DATABASE'),# railway
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

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for statement in sql_script.split(';'):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
        return jsonify({"message": "Archivo SQL importado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al ejecutar script SQL: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()
from flask import Blueprint, request, jsonify
from utils.db import get_db_connection

documentos_bp = Blueprint('documentos', __name__)

# Ruta existente para listar documentos
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

# Nueva ruta para importar archivo SQL
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

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for statement in sql_script.split(';'):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
        return jsonify({"message": "Archivo SQL importado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error ejecutando script SQL: {str(e)}"}), 500
    finally:
        conn.close()
