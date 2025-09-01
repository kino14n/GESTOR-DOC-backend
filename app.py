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

    # --- CONFIGURACIÓN DE CORS MEJORADA ---
    # Lee la variable de entorno CORS_ORIGINS. Si no existe, permite todo (*).
    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        expose_headers=["Content-Disposition"],
        # Permite las cabeceras necesarias, incluyendo la de identificación del cliente.
        allow_headers=["Content-Type", "X-Tenant-ID"],
    )

    # Registrar el blueprint para manejar las rutas de documentos
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
    # Permite especificar el puerto vía variable de entorno, default 5001
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)