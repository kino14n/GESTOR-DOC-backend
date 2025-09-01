# GESTOR-DOC-backend/app.py
import os
from flask import Flask, jsonify
from flask_cors import CORS
from routes.documentos import documentos_bp

def create_app() -> Flask:
    """
    Crea una instancia de la aplicación Flask configurada para un entorno multi-cliente.
    """
    app = Flask(__name__)

    origins = os.getenv("CORS_ORIGINS", "*").split(",")

    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        expose_headers=["Content-Disposition"],
        allow_headers=["Content-Type", "X-Tenant-ID"],
    )

    app.register_blueprint(documentos_bp, url_prefix="/api/documentos")

    @app.route("/api")
    def index() -> jsonify:
        """Ruta de diagnóstico para confirmar que la API se ejecuta."""
        return jsonify({
            "message": "API del Gestor de Documentos Multi-Cliente funcionando.",
            "status": "ok",
        })

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)