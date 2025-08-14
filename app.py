# GESTOR-DOC-backend/app.py
import os
from flask import Flask, jsonify
from flask_cors import CORS
from routes.documentos import documentos_bp

def create_app():
    """
    Crea y configura la aplicación Flask.
    Esta es la función que Gunicorn/Railway buscará.
    """
    app = Flask(__name__)

    # --- Configuración de CORS ---
    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS(app, resources={r"/api/*": {"origins": origins}})

    # --- Registro de Rutas (Blueprint) ---
    app.register_blueprint(documentos_bp, url_prefix='/api/documentos')

    # --- Ruta de Bienvenida ---
    @app.route('/')
    @app.route('/api')
    def index():
        return jsonify({
            "message": "API del Gestor de Documentos funcionando correctamente.",
            "status": "ok"
        })

    return app

# --- Bloque para Ejecución Local ---
if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)