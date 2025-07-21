from flask import Blueprint, request, jsonify
from utils.db import get_db_connection

documentos_bp = Blueprint('documentos', __name__)

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
