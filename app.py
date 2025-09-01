# app.py — Backend GESTOR-DOC (Flask + Railway)
import os
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

from routes.documentos import documentos_bp, upload_document  # alias para /upload legacy

def _parse_origins(env_value: str):
    if not env_value:
        return []
    return [o.strip() for o in env_value.split(",") if o.strip()]

def create_app() -> Flask:
    app = Flask(__name__)

    # ---- CORS ----
    default_origins = ["https://kino14n.github.io"]
    allowed_origins = _parse_origins(os.getenv("CORS_ORIGINS", ",".join(default_origins)))
    cors_cfg = {
        "origins": allowed_origins or ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Tenant-ID"],
        "supports_credentials": False,
    }
    CORS(
        app,
        resources={
            r"/api/*": cors_cfg,
            r"/upload": cors_cfg,            # alias legacy
            r"/documentos/*": cors_cfg,      # alias legacy
            r"/resaltar": {**cors_cfg, "methods": ["POST", "OPTIONS"]},
        },
        expose_headers=["Content-Disposition"],
    )

    # ---- Blueprints ----
    app.register_blueprint(documentos_bp, url_prefix="/api/documentos")

    # ---- Alias legacy (/upload y /documentos/upload) ----
    app.add_url_rule("/upload", view_func=upload_document, methods=["POST", "OPTIONS"])
    app.add_url_rule("/documentos/upload", view_func=upload_document, methods=["POST", "OPTIONS"])

    # ---- Salud / util ----
    @app.get("/api/ping")
    def ping():
        return jsonify({"ok": True})

    @app.get("/api/env")
    def env_info():
        data = {
            "CORS_ORIGINS": allowed_origins or ["*"],
            "HIGHLIGHTER_URL": os.getenv("HIGHLIGHTER_URL", ""),
            "MYSQLHOST": os.getenv("MYSQLHOST", ""),
            "MYSQLPORT": os.getenv("MYSQLPORT", ""),
            "MYSQLUSER": os.getenv("MYSQLUSER", ""),
            "MYSQLDATABASE": os.getenv("MYSQLDATABASE", ""),
        }
        return jsonify(data)

    # Proxy opcional a un resaltador HTTP (si usas uno propio fuera del blueprint)
    @app.post("/resaltar")
    def resaltar_proxy():
        url = os.getenv("HIGHLIGHTER_URL")
        if not url:
            return jsonify({"error": "HIGHLIGHTER_URL no está configurada"}), 400
        payload = request.get_json(silent=True) or {}
        try:
            r = requests.post(url, json=payload, timeout=120)
        except requests.RequestException as e:
            return jsonify({"error": f"No se pudo contactar el servicio de resaltado: {e}"}), 502
        if r.status_code != 200:
            return jsonify({"error": r.text, "status": r.status_code}), 502
        return Response(r.content, status=200, mimetype="application/pdf")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
