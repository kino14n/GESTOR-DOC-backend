from flask import Blueprint, request, jsonify
import os
import pymysql

documentos_bp = Blueprint('documentos', __name__)

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

@documentos_bp.route('/api/documentos', methods=['GET'])
def listar_documentos():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM documentos")
            resultado = cursor.fetchall()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

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
        connection = get_db_connection()
        connection.close()
        return jsonify({"message": "pong", "db": "conexión exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
