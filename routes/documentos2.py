from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import os
from .db import get_db_connection
import uuid

documentos_bp = Blueprint('documentos', __name__)

# === ENDPOINT: Listar documentos (para consultar)
@documentos_bp.route('/api/documentos', methods=['GET'])
def listar_documentos():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.name, d.date, d.path,
                       (SELECT GROUP_CONCAT(code ORDER BY code) FROM codes WHERE document_id = d.id) AS codigos_extraidos
                FROM documents d
                ORDER BY d.id DESC
            """)
            resultado = cursor.fetchall()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# === ENDPOINT: Eliminar documento
@documentos_bp.route('/api/documentos/<int:id>', methods=['DELETE'])
def eliminar_documento(id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Elimina los códigos asociados
            cursor.execute("DELETE FROM codes WHERE document_id = %s", (id,))
            # Elimina el documento
            cursor.execute("DELETE FROM documents WHERE id = %s", (id,))
        connection.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# === ENDPOINT: Subir o editar documento (PUT para editar)
@documentos_bp.route('/api/documentos/upload', methods=['POST', 'PUT'])
def upload_documento():
    id_doc = request.form.get('id')
    name = request.form.get('nombre')
    date = request.form.get('fecha')
    codes = request.form.get('codes', '').replace('\r', '').replace(';', ',').replace('\n', ',')
    codes = [c.strip() for c in codes.split(',') if c.strip()]
    file = request.files.get('file')

    if not name or not date:
        return jsonify({'error': 'Nombre y fecha obligatorios'}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Nuevo documento
            if not id_doc:
                cursor.execute("INSERT INTO documents (name, date) VALUES (%s, %s)", (name, date))
                new_id = cursor.lastrowid
            else:
                # Edición: actualiza datos básicos y borra los códigos previos
                cursor.execute("UPDATE documents SET name=%s, date=%s WHERE id=%s", (name, date, id_doc))
                cursor.execute("DELETE FROM codes WHERE document_id=%s", (id_doc,))
                new_id = id_doc

            # Inserta los códigos
            for code in codes:
                cursor.execute("INSERT INTO codes (document_id, code) VALUES (%s, %s)", (new_id, code))

            # Manejo de PDF
            if file:
                ext = file.filename.rsplit('.', 1)[-1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                uploads_dir = os.path.join(current_app.root_path, 'uploads')
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                file.save(os.path.join(uploads_dir, filename))
                cursor.execute("UPDATE documents SET path=%s WHERE id=%s", (filename, new_id))

        connection.commit()
        return jsonify({'ok': True, 'id': new_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# === ENDPOINT: Descargar PDF
@documentos_bp.route('/uploads/<path:filename>')
def descargar_pdf(filename):
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    return send_from_directory(uploads_dir, filename)

# === ENDPOINT: Buscar por código (autocomplete)
@documentos_bp.route('/api/documentos/search_by_code', methods=['POST'])
def buscar_por_codigo():
    data = request.get_json()
    codigo = data.get('codigo', '').strip()
    if not codigo:
        return jsonify([])
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT code FROM codes
                WHERE code LIKE %s
                ORDER BY code ASC
                LIMIT 10
            """, (codigo + '%',))
            resultado = [r['code'] for r in cursor.fetchall()]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

# === ENDPOINT: Búsqueda voraz agrupada (para Búsqueda Óptima)
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
            # Trae los docs que tienen al menos uno de los códigos, e incluye TODOS los códigos de ese doc en codigos_extraidos
            cursor.execute(f"""
                SELECT 
                    d.id,
                    d.name,
                    d.date,
                    d.path,
                    (SELECT GROUP_CONCAT(c2.code ORDER BY c2.code) FROM codes c2 WHERE c2.document_id = d.id) AS codigos_extraidos
                FROM documents d
                JOIN codes c ON c.document_id = d.id
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

# === ENDPOINT: Búsqueda óptima avanzada (set cover)
@documentos_bp.route('/api/documentos/search_optima', methods=['POST'])
def busqueda_optima():
    data = request.get_json()
    codigos = [c.strip().upper() for c in data.get('codigos', '').replace(',', ' ').replace('\n', ' ').split() if c.strip()]
    if not codigos:
        return jsonify({'documentos': [], 'codigos_faltantes': codigos})

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Buscar todos los documentos y los códigos que cubren
            cursor.execute("""
                SELECT 
                    d.id, d.name, d.date, d.path,
                    GROUP_CONCAT(c.code ORDER BY c.code) AS codigos
                FROM documents d
                JOIN codes c ON c.document_id = d.id
                WHERE c.code IN (%s)
                GROUP BY d.id
                ORDER BY d.id DESC
            """ % ','.join(['%s'] * len(codigos)), codigos)
            docs = cursor.fetchall()

            codigos_cubiertos = set()
            documentos = []
            for doc in docs:
                codigos_doc = set((doc['codigos'] or '').split(','))
                codigos_en_doc = codigos_doc & set(codigos)
                if codigos_en_doc:
                    documentos.append({
                        'documento': {
                            'id': doc['id'],
                            'name': doc['name'],
                            'date': doc['date'],
                            'path': doc['path']
                        },
                        'codigos_cubre': list(codigos_en_doc)
                    })
                    codigos_cubiertos.update(codigos_en_doc)
            codigos_faltantes = list(set(codigos) - codigos_cubiertos)

        return jsonify({'documentos': documentos, 'codigos_faltantes': codigos_faltantes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()
