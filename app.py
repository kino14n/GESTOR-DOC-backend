# app.py — GESTOR-DOC Backend (Flask + Railway)
import os
import requests
from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Blueprints
try:
    from routes.documentos import documentos_bp  # si está en routes/
except ImportError:
    from documentos import documentos_bp  # fallback si está en raíz

import db


# ----------------------------- Utils -----------------------------
def _parse_origins(env_value: str):
    """Convierte CORS_ORIGINS (separado por coma) en lista."""
    if not env_value:
        return []
    return [o.strip() for o in env_value.split(",") if o.strip()]


def _origin_allowed(origin: str, allowed: list[str]) -> bool:
    if not origin:
        return False
    if not allowed or "*" in allowed:
        return True
    return origin in allowed


# --------------------------- App Factory --------------------------
def create_app() -> Flask:
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ----- CORS -----
    # Orígenes por defecto (producción y local dev)
    default_origins = [
        "https://kino14n.github.io",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    allowed_origins = _parse_origins(
        os.getenv("CORS_ORIGINS", ",".join(default_origins))
    )

    # CORS automático para /api/* y /resaltar
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": allowed_origins or ["*"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
                "supports_credentials": False,
            },
            r"/resaltar": {
                "origins": allowed_origins or ["*"],
                "methods": ["POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
                "supports_credentials": False,
            },
        },
        expose_headers=["Content-Disposition"],
    )

    # Preflight universal para evitar fallos de OPTIONS si el deploy está frío
    @app.before_request
    def _handle_preflight():
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin")
            resp = make_response("", 204)
            if _origin_allowed(origin, allowed_origins):
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"
                resp.headers["Access-Control-Allow-Methods"] = (
                    "GET,POST,PUT,DELETE,OPTIONS"
                )
                req_headers = request.headers.get(
                    "Access-Control-Request-Headers", "Content-Type,Authorization"
                )
                resp.headers["Access-Control-Allow-Headers"] = req_headers
                resp.headers["Access-Control-Max-Age"] = "86400"
            return resp

    # Añade cabeceras CORS/Expose para todas las respuestas válidas
    @app.after_request
    def _add_cors_headers(resp):
        origin = request.headers.get("Origin")
        if _origin_allowed(origin, allowed_origins):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            # Para descargas (CSV/ZIP/PDF) desde el front
            resp.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        return resp

    # ----- Blueprints -----
    app.register_blueprint(documentos_bp, url_prefix="/api/documentos")

    # ----- Endpoints utilitarios -----
    @app.get("/")
    def root():
        return jsonify({"service": "gestor-doc-backend", "ok": True})

    @app.get("/api/ping")
    def ping():
        return jsonify({"ok": True})

    @app.get("/api/env")
    def env_info():
        """Diagnóstico (NO expongas en producción si no es necesario)."""
        data = {
            "DB_HOST": os.getenv("DB_HOST", os.getenv("MYSQLHOST", "")),
            "DB_PORT": os.getenv("DB_PORT", os.getenv("MYSQLPORT", "")),
            "DB_NAME": os.getenv("DB_NAME", os.getenv("MYSQLDATABASE", "")),
            "DB_USER": os.getenv("DB_USER", os.getenv("MYSQLUSER", "")),
            "CORS_ORIGINS": allowed_origins or ["*"],
            "HIGHLIGHTER_URL": os.getenv("HIGHLIGHTER_URL", ""),
        }
        return jsonify(data)

    @app.get("/api/routes")
    def routes():
        return jsonify({"routes": [str(r) for r in app.url_map.iter_rules()]})

    @app.get("/api/test-db")
    def test_db():
        try:
            conn = db.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total FROM documentos")
                row = cur.fetchone()
                total = row["total"] if isinstance(row, dict) else row[0]
            return jsonify({"status": "ok", "total_documentos": int(total)})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # ----- Proxy de resaltado de PDF -----
    @app.post("/resaltar")
    def resaltar_proxy():
        highlighter = os.getenv("HIGHLIGHTER_URL")
        if not highlighter:
            return jsonify({"error": "HIGHLIGHTER_URL no está configurada"}), 400

        try:
            payload = request.get_json(force=True, silent=False) or {}
        except Exception:
            payload = {}

        try:
            r = requests.post(highlighter, json=payload, timeout=120)
        except requests.RequestException as e:
            return (
                jsonify(
                    {"error": f"No se pudo contactar el servicio de resaltado: {e}"}
                ),
                502,
            )

        if r.status_code != 200:
            try:
                err = r.json()
            except Exception:
                err = {"error": r.text}
            return (
                jsonify(
                    {
                        "error": err.get("error", "Error en servicio de resaltado"),
                        "status": r.status_code,
                    }
                ),
                502,
            )

        return Response(r.content, status=200, mimetype="application/pdf")

    return app


# Instancia para Gunicorn / Railway
app = create_app()

if __name__ == "__main__":
    # Ejecución local
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
