from flask import Blueprint, request, jsonify, send_file
import db
import os
import requests

DOCUMENTS_FOLDER = os.path.join(os.getcwd(), 'uploads')
documentos_bp = Blueprint('documentos', __name__)

@documentos_bp.route('/search_by_code', methods=['POST'])
def search_by_code():
    data = request.get_json()
    code = data.get('code', '').strip()
    exact = data.get('exact', False)
    if not code:
        return jsonify({'error': 'Código requerido'}), 400
    conn = db.get_db()
    cursor = conn.cursor()
    if exact:
        cursor.execute("SELECT * FROM documentos WHERE codigo = %s", (code,))
    else:
        cursor.execute("SELECT * FROM documentos WHERE codigo LIKE %s", (f'{code}%',))
    rows = cursor.fetchall()
    return jsonify({'documentos': rows})

@documentos_bp.route('/resaltar', methods=['POST'])
def resaltar():
    data = request.get_json()
    pdf_path = data.get('pdf_path')
    codes = data.get('codes', [])
    if not pdf_path or not codes:
        return jsonify({'error': 'Parámetros incompletos'}), 400
    url = os.getenv('HIGHLIGHTER_URL')
    resp = requests.post(url, json={'pdf_path': pdf_path, 'codes': codes})
    if resp.status_code != 200:
        return jsonify({'error': 'Error al procesar PDF'}), 500
    tmp_path = os.path.join(DOCUMENTS_FOLDER, 'resaltado.pdf')
    with open(tmp_path, 'wb') as f:
        f.write(resp.content)
    return send_file(tmp_path, mimetype='application/pdf')
