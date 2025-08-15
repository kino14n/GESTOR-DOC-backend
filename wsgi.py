# wsgi.py — Punto de entrada gunicorn
try:
    from app import create_app
    app = create_app()
except Exception:
    from app import app as app  # fallback si alguien usa app directa
