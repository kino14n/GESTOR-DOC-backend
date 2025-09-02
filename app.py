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
    # Lee los dominios permitidos desde una variable de entorno.
    # Si no se especifica, permite cualquier origen (útil para desarrollo).
    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        expose_headers=["Content-Disposition"],
        # Permite las cabeceras estándar y nuestra cabecera personalizada.
        allow_headers=["Content-Type", "X-Tenant-ID"],
        # Flask-CORS maneja OPTIONS automáticamente.
    )

    # Registrar el blueprint que contiene todas nuestras rutas
    app.register_blueprint(documentos_bp, url_prefix="/api/documentos")

@app.route("/api/diag")
def diag():
    """Ruta de diagnóstico para verificar la versión del código."""
    import boto3 # Añade esta importación localmente
    return jsonify({
        "message": "Diagnóstico del backend.",
        "codigo_version": "4.0-final-fix",
        "boto3_version": boto3.__version__
    })

return app

# Este bloque solo se ejecuta si corres el archivo directamente (ej. python app.py)
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
